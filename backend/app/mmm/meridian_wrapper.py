"""
Thin wrapper around Google Meridian for national (single-geo) MMM fitting.

This module is intentionally isolated — it is the only place in the codebase
that imports from 'meridian'. All other code interacts with FitResult /
PosteriorSamples only.

Meridian requires Python 3.10+ and TensorFlow 2.19+ (Linux). It runs inside
the Docker worker container. Attempting to import this on macOS will raise
MeridianUnavailableError, which is caught in the Celery task.
"""
from __future__ import annotations

import logging
from typing import Callable

import numpy as np
import pandas as pd

from app.mmm.schemas import FitResult, PosteriorSamples
from app.models.run import MeridianConfig

logger = logging.getLogger(__name__)


class MeridianUnavailableError(RuntimeError):
    """Raised when the meridian package is not installed in this environment."""


def _import_meridian():
    """Lazy import — raises MeridianUnavailableError if not installed."""
    try:
        import meridian as _meridian_pkg
        # Verify it's the Google MMM library (not the unrelated 'meridian' PyPI package)
        if not hasattr(_meridian_pkg, "model"):
            raise ImportError("Wrong 'meridian' package installed — expected google-meridian.")
        return _meridian_pkg
    except ImportError as exc:
        raise MeridianUnavailableError(
            "Google Meridian is not installed. "
            "Run inside Docker where TensorFlow 2.19+ is available. "
            f"Original error: {exc}"
        ) from exc


def _build_input_data(
    df: pd.DataFrame,
    channel_names: list[str],
    granularity: str = "weekly",
    media_scale: dict[str, float] | None = None,
    kpi_scale: float = 1.0,
    trend_values: np.ndarray | None = None,
):
    """
    Convert a tidy DataFrame into a Meridian InputData object.

    DataFrame columns expected:
        date           — ISO date string (YYYY-MM-DD), any granularity
        <channel_n>    — spend per period per channel (float)
        acquisitions   — KPI count per period (float)

    granularity: 'daily' | 'weekly' | 'monthly'

    media_scale: per-channel normalization divisors (typically max observed spend).
        The `media` array is divided by these values so that it lives in [0, 1].
        Meridian's default priors for the Hill EC parameter assume normalized media;
        passing raw dollar spend (e.g. $50k–$200k) pushes every observation past the
        saturation point and produces flat curves.  `media_spend` is kept in raw
        dollars because it is used only for budget attribution, not curve estimation.

    Returns a meridian.data.InputData instance.
    """
    import xarray as xr
    mer = _import_meridian()
    from meridian.data import input_data as id_lib

    n_times = len(df)
    n_channels = len(channel_names)

    # Support both old 'week' and new normalised 'date' column name
    date_col = "date" if "date" in df.columns else "week"
    time_coords = df[date_col].tolist()

    # KPI: (n_geos=1, n_times) — normalized by kpi_scale so values are ~O(1).
    # Meridian's beta prior assumes KPI in a "small" range; acquisitions in the
    # hundreds/thousands cause beta to be underestimated (~1).  Divide here,
    # then multiply back in response_curves.py after sampling.
    kpi_values = (df["acquisitions"].to_numpy(dtype=float) / kpi_scale).reshape(1, n_times)
    kpi = xr.DataArray(
        kpi_values,
        name="kpi",
        dims=["geo", "time"],
        coords={"geo": ["national"], "time": time_coords},
    )

    # Raw spend array in dollars: (n_times, n_channels)
    raw_spend = df[channel_names].to_numpy(dtype=float)

    # Normalize media to [0, 1] per channel so Meridian's Hill priors are well-scaled.
    # Without normalization, spend values in the $10k–$200k range make the posterior
    # EC << actual spend everywhere, causing flat saturated curves.
    if media_scale is not None:
        scale_vec = np.array([media_scale[ch] for ch in channel_names], dtype=float)
        # Avoid division by zero for zero-spend channels
        scale_vec = np.where(scale_vec > 0, scale_vec, 1.0)
        normalized_spend = raw_spend / scale_vec[np.newaxis, :]
    else:
        normalized_spend = raw_spend

    media_values = normalized_spend.reshape(1, n_times, n_channels)
    spend_values = raw_spend.reshape(1, n_times, n_channels)

    # Media (normalized): (n_geos=1, n_media_times, n_channels)
    # Meridian requires the time dim to be named 'media_time' for media arrays
    media = xr.DataArray(
        media_values,
        name="media",
        dims=["geo", "media_time", "media_channel"],
        coords={
            "geo": ["national"],
            "media_time": time_coords,
            "media_channel": channel_names,
        },
    )

    # media_spend stays in raw dollars — used for budget attribution only
    media_spend = xr.DataArray(
        spend_values,
        name="media_spend",
        dims=["geo", "time", "media_channel"],
        coords={
            "geo": ["national"],
            "time": time_coords,
            "media_channel": channel_names,
        },
    )

    # Population: constant 1.0 for a national model
    population = xr.DataArray(
        np.ones((1,), dtype=float),
        name="population",
        dims=["geo"],
        coords={"geo": ["national"]},
    )

    # Controls: linear trend standardised to mean=0, std=1 as Meridian requires.
    # Shape: (n_geos=1, n_times, n_controls=1)
    controls = None
    control_names = None
    if trend_values is not None:
        controls = xr.DataArray(
            trend_values.reshape(1, n_times, 1),
            name="controls",
            dims=["geo", "time", "control_variable"],
            coords={
                "geo": ["national"],
                "time": time_coords,
                "control_variable": ["trend"],
            },
        )
        control_names = ["trend"]

    kwargs = dict(
        kpi=kpi,
        kpi_type="non_revenue",
        media=media,
        media_spend=media_spend,
        population=population,
    )
    if controls is not None:
        kwargs["controls"] = controls

    return id_lib.InputData(**kwargs)


def _extract_posterior(mmm, channel_names: list[str]) -> PosteriorSamples:
    """
    Extract and flatten posterior samples from the fitted Meridian model.

    Meridian stores samples in az.InferenceData with dims (chain, draw, ...).
    We flatten chain x draw → n_samples for downstream use.

    Expected posterior variables:
        alpha  : (chain, draw, media_channel)         — adstock decay
        ec     : (chain, draw, media_channel)         — hill saturation
        slope  : (chain, draw, media_channel)         — hill slope
        beta_gm: (chain, draw, geo, media_channel)    — channel beta
    """
    posterior = mmm.inference_data.posterior

    def flat(var_name: str) -> np.ndarray:
        """Stack chain + draw dims → (n_samples, ...)."""
        arr = posterior[var_name].values  # (chain, draw, ...)
        # Reshape: merge first two dims
        shape = arr.shape
        return arr.reshape(shape[0] * shape[1], *shape[2:])

    alpha = flat("alpha_m")                 # (n_samples, n_channels)
    ec = flat("ec_m")                       # (n_samples, n_channels)
    slope = flat("slope_m")                 # (n_samples, n_channels)
    beta_gm = flat("beta_gm")              # (n_samples, n_geos, n_channels)
    beta = beta_gm[:, 0, :]                # take geo=0 (national) → (n_samples, n_channels)

    # Intercept: tau_g shape (n_samples, n_geos) — take geo=0
    tau = None
    try:
        tau_g = flat("tau_g")              # (n_samples, n_geos)
        tau = tau_g[:, 0]                  # (n_samples,)
    except Exception:
        logger.warning("tau_g not found in posterior — intercept will be excluded from baseline")

    # Trend coefficient: gamma_c shape (n_samples, n_controls) — take control=0
    gamma_trend = None
    try:
        gamma_c = flat("gamma_c")          # (n_samples, n_controls)
        gamma_trend = gamma_c[:, 0]        # (n_samples,)
    except Exception:
        pass  # no controls fitted — expected when trend not passed

    return PosteriorSamples(
        alpha=alpha,
        ec=ec,
        slope=slope,
        beta=beta,
        channel_names=channel_names,
        tau=tau,
        gamma_trend=gamma_trend,
    )


def _compute_diagnostics(mmm) -> tuple[float, int]:
    """
    Compute R-hat (convergence) and bulk ESS (effective sample size).
    Returns (r_hat_max, ess_bulk_min).
    """
    try:
        import arviz as az
        summary = az.summary(mmm.inference_data, var_names=["alpha_m", "ec_m", "slope_m", "beta_gm"])
        r_hat_max = float(summary["r_hat"].max())
        ess_bulk_min = int(summary["ess_bulk"].min())
        return r_hat_max, ess_bulk_min
    except Exception as exc:
        logger.warning("Could not compute diagnostics: %s", exc)
        return float("nan"), 0


class MeridianWrapper:

    def __init__(self, config: MeridianConfig) -> None:
        self.config = config

    def fit(
        self,
        df: pd.DataFrame,
        channel_names: list[str],
        granularity: str = "weekly",
        progress_callback: Callable[[int], None] | None = None,
    ) -> FitResult:
        """
        Fit the Meridian model on the provided DataFrame.

        progress_callback receives integers 0–100 indicating % complete.
        Blocks until MCMC sampling finishes (called inside Celery worker).
        """
        _import_meridian()  # fail fast if not installed

        from meridian.model import model as model_lib

        if progress_callback:
            progress_callback(5)

        logger.info(
            "Building InputData: %d weeks, %d channels", len(df), len(channel_names)
        )
        # Normalise media by max observed spend per channel (→ [0, 1]).
        # Normalise KPI by its mean (→ ~1).
        # Meridian's priors assume both inputs are in a "small" numeric range;
        # raw dollar spend ($10k–$200k) and raw acquisitions (700–4500) both
        # cause prior-dominated posteriors and produce wrong curve scales.
        max_weekly_spend = {ch: float(df[ch].max()) for ch in channel_names}
        kpi_scale = float(df["acquisitions"].mean()) or 1.0

        # Linear trend control: normalise to [0,1] then standardise to mean=0, std=1
        # as Meridian requires. Lets the model separate structural growth from media ROI.
        n_times = len(df)
        raw_trend = np.arange(n_times, dtype=float) / max(n_times - 1, 1)
        trend_std = raw_trend - raw_trend.mean()
        if raw_trend.std() > 0:
            trend_std = trend_std / raw_trend.std()

        input_data = _build_input_data(
            df,
            channel_names,
            granularity=granularity,
            media_scale=max_weekly_spend,
            kpi_scale=kpi_scale,
            trend_values=trend_std,
        )

        if progress_callback:
            progress_callback(10)

        logger.info(
            "Fitting Meridian: n_chains=%d, n_warmup=%d, n_samples=%d",
            self.config.n_chains,
            self.config.n_warmup,
            self.config.n_samples,
        )
        # Build ModelConfig — enable AKS (Automatic Knot Selection) if requested.
        # AKS fits a piecewise linear spline over time to capture seasonal patterns
        # without needing extra CSV columns. Adds parameters → slightly longer fit.
        try:
            from meridian.model import model_config as mc_lib
            model_cfg_kwargs = {}
            if self.config.enable_aks:
                model_cfg_kwargs["enable_aks"] = True
                logger.info("fit_model: AKS seasonality enabled")
            model_cfg = mc_lib.ModelConfig(**model_cfg_kwargs) if model_cfg_kwargs else None
        except Exception as exc:
            logger.warning("Could not build ModelConfig (%s) — using defaults", exc)
            model_cfg = None

        mmm_kwargs = {"input_data": input_data}
        if model_cfg is not None:
            mmm_kwargs["model_config"] = model_cfg

        mmm = model_lib.Meridian(**mmm_kwargs)
        mmm.sample_posterior(
            n_chains=self.config.n_chains,
            n_adapt=self.config.n_warmup,
            n_burnin=self.config.n_warmup,
            n_keep=self.config.n_samples,
        )

        if progress_callback:
            progress_callback(75)

        logger.info("Sampling complete. Extracting posterior samples.")
        posterior = _extract_posterior(mmm, channel_names)
        r_hat_max, ess_bulk_min = _compute_diagnostics(mmm)

        if progress_callback:
            progress_callback(80)

        return FitResult(
            mmm=mmm,
            channel_names=channel_names,
            n_time_periods=len(df),
            posterior=posterior,
            max_weekly_spend=max_weekly_spend,
            kpi_scale=kpi_scale,
            r_hat_max=r_hat_max,
            ess_bulk_min=ess_bulk_min,
            trend_values=trend_std,
        )
