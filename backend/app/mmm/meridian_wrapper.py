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


def _build_input_data(df: pd.DataFrame, channel_names: list[str]):
    """
    Convert a tidy DataFrame into a Meridian InputData object.

    DataFrame columns expected:
        week           — ISO date string (YYYY-MM-DD)
        <channel_n>    — weekly spend per channel (float)
        acquisitions   — weekly KPI count (float)

    Returns a meridian.data.InputData instance.
    """
    import xarray as xr
    mer = _import_meridian()
    from meridian.data import input_data as id_lib

    n_times = len(df)
    n_channels = len(channel_names)

    time_coords = df["week"].tolist()

    # KPI: (n_geos=1, n_times) — name must match what Meridian expects
    kpi_values = df["acquisitions"].to_numpy(dtype=float).reshape(1, n_times)
    kpi = xr.DataArray(
        kpi_values,
        name="kpi",
        dims=["geo", "time"],
        coords={"geo": ["national"], "time": time_coords},
    )

    # Media spend: (n_geos=1, n_times, n_channels)
    spend_values = df[channel_names].to_numpy(dtype=float).reshape(1, n_times, n_channels)
    media = xr.DataArray(
        spend_values,
        name="media",
        dims=["geo", "time", "media_channel"],
        coords={
            "geo": ["national"],
            "time": time_coords,
            "media_channel": channel_names,
        },
    )

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

    return id_lib.InputData(
        kpi=kpi,
        kpi_type="non_revenue",
        media=media,
        media_spend=media_spend,
        population=population,
    )


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

    alpha = flat("alpha")                   # (n_samples, n_channels)
    ec = flat("ec")                         # (n_samples, n_channels)
    slope = flat("slope")                   # (n_samples, n_channels)
    beta_gm = flat("beta_gm")              # (n_samples, n_geos, n_channels)
    beta = beta_gm[:, 0, :]                # take geo=0 (national) → (n_samples, n_channels)

    return PosteriorSamples(
        alpha=alpha,
        ec=ec,
        slope=slope,
        beta=beta,
        channel_names=channel_names,
    )


def _compute_diagnostics(mmm) -> tuple[float, int]:
    """
    Compute R-hat (convergence) and bulk ESS (effective sample size).
    Returns (r_hat_max, ess_bulk_min).
    """
    try:
        import arviz as az
        summary = az.summary(mmm.inference_data, var_names=["alpha", "ec", "slope", "beta_gm"])
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
        input_data = _build_input_data(df, channel_names)

        if progress_callback:
            progress_callback(10)

        logger.info(
            "Fitting Meridian: n_chains=%d, n_warmup=%d, n_samples=%d",
            self.config.n_chains,
            self.config.n_warmup,
            self.config.n_samples,
        )
        mmm = model_lib.Meridian(input_data=input_data)
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

        max_weekly_spend = {ch: float(df[ch].max()) for ch in channel_names}

        return FitResult(
            mmm=mmm,
            channel_names=channel_names,
            n_time_periods=len(df),
            posterior=posterior,
            max_weekly_spend=max_weekly_spend,
            r_hat_max=r_hat_max,
            ess_bulk_min=ess_bulk_min,
        )
