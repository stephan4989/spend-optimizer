"""
Extract time-series model analytics from a fitted Meridian model
using Meridian's own Analyzer and ModelDiagnostics APIs.

  extract_model_fit             — actual vs full predicted (Analyzer.expected_vs_actual_data)
                                  formula: ŷ = tau_g + mu_t + Σ(beta_m × Hill(Adstock(x_m))) + gamma_c × z
  extract_channel_contributions — per-channel media contributions + proper baseline
                                  baseline = ŷ(media=0) = tau_g + mu_t + gamma_c × z
  extract_fit_metrics           — R², MAPE, wMAPE from ModelDiagnostics.predictive_accuracy_table()
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from app.mmm.schemas import FitResult

logger = logging.getLogger(__name__)


def extract_model_fit(
    df: pd.DataFrame,
    fit_result: FitResult,
) -> dict:
    """
    Use Analyzer.expected_vs_actual_data() to get the full model prediction.

    Returns:
      dates, actual, predicted_mean, predicted_lower, predicted_upper, baseline_mean

    Falls back to manual media-only sum if Analyzer is unavailable.
    """
    date_col = "date" if "date" in df.columns else "week"
    dates = df[date_col].astype(str).tolist()
    actual = df["acquisitions"].to_numpy(dtype=float).tolist()

    try:
        from meridian.analysis import analyzer as analyzer_lib

        az = analyzer_lib.Analyzer(fit_result.mmm)
        # Returns xarray Dataset with dims (metric, geo, time) or similar.
        # expected_outcome returns (n_chains, n_draws, n_geos, n_times) tensor.
        expected = az.expected_outcome(
            use_posterior=True,
            aggregate_geos=True,
            aggregate_times=False,
            inverse_transform_outcome=True,
        )
        # Shape after geo aggregation: (n_chains, n_draws, n_times)
        vals = np.array(expected)
        if vals.ndim == 4:
            vals = vals[:, :, 0, :]   # take geo=0
        # Flatten chains × draws → n_samples
        n_chains, n_draws, n_times = vals.shape
        flat = vals.reshape(n_chains * n_draws, n_times)

        return {
            "dates": dates,
            "actual": actual,
            "predicted_mean": flat.mean(axis=0).tolist(),
            "predicted_lower": np.percentile(flat, 10, axis=0).tolist(),
            "predicted_upper": np.percentile(flat, 90, axis=0).tolist(),
        }

    except Exception as exc:
        logger.warning("Analyzer.expected_outcome failed (%s) — falling back to manual media sum", exc)
        return _manual_model_fit(df, fit_result, dates, actual)


def _manual_model_fit(
    df: pd.DataFrame,
    fit_result: FitResult,
    dates: list[str],
    actual: list[float],
) -> dict:
    """
    Fallback: predicted = Σ(beta_m × Hill(Adstock(x_m))) across channels.
    Excludes intercept/trend — gap to actual is the baseline.
    """
    posterior = fit_result.posterior
    n_samples = posterior.n_samples
    n_times = len(df)
    total = np.zeros((n_samples, n_times))

    for i, ch in enumerate(fit_result.channel_names):
        spend = df[ch].to_numpy(dtype=float)
        scale = fit_result.max_weekly_spend.get(ch) or 1.0
        spend_norm = spend / scale
        alpha = posterior.alpha[:, i]
        ec = posterior.ec[:, i]
        slope_p = posterior.slope[:, i]
        beta = posterior.beta[:, i]

        adstocked = np.zeros((n_samples, n_times))
        adstocked[:, 0] = spend_norm[0]
        for t in range(1, n_times):
            adstocked[:, t] = spend_norm[t] + alpha * adstocked[:, t - 1]

        a_n = np.power(np.maximum(adstocked, 0.0), slope_p[:, np.newaxis])
        e_n = np.power(np.maximum(ec[:, np.newaxis], 1e-12), slope_p[:, np.newaxis])
        hill = a_n / (e_n + a_n + 1e-12)
        total += beta[:, np.newaxis] * hill * fit_result.kpi_scale

    return {
        "dates": dates,
        "actual": actual,
        "predicted_mean": total.mean(axis=0).tolist(),
        "predicted_lower": np.percentile(total, 10, axis=0).tolist(),
        "predicted_upper": np.percentile(total, 90, axis=0).tolist(),
    }


def extract_channel_contributions(
    df: pd.DataFrame,
    fit_result: FitResult,
) -> dict:
    """
    Per-channel media contributions + baseline over time.

    Tries Analyzer.expected_vs_actual_data() which returns:
      expected = tau_g + mu_t + Σ(beta_m × Hill(Adstock)) + gamma_c × z
      baseline = tau_g + mu_t + gamma_c × z  (media = 0)
      media_contribution = expected - baseline

    Falls back to manual adstock loop with residual baseline.
    """
    date_col = "date" if "date" in df.columns else "week"
    dates = df[date_col].astype(str).tolist()

    try:
        from meridian.analysis import analyzer as analyzer_lib

        az = analyzer_lib.Analyzer(fit_result.mmm)

        # Per-channel incremental contribution: use expected_outcome with one channel
        # active at a time is expensive. Instead use the data from expected_vs_actual
        # for baseline and fall through to manual per-channel for the breakdown.
        # Baseline: expected_outcome with media zeroed = counterfactual
        # Meridian Analyzer doesn't expose zero-media counterfactual directly via
        # a simple flag, so we use the manual posterior for per-channel and
        # use Analyzer only to get the proper aggregate baseline.
        expected_full = az.expected_outcome(
            use_posterior=True,
            aggregate_geos=True,
            aggregate_times=False,
            inverse_transform_outcome=True,
        )
        vals = np.array(expected_full)
        if vals.ndim == 4:
            vals = vals[:, :, 0, :]
        n_chains, n_draws, n_times = vals.shape
        expected_flat = vals.reshape(n_chains * n_draws, n_times)
        expected_mean = expected_flat.mean(axis=0)

    except Exception as exc:
        logger.warning("Analyzer.expected_outcome failed for contributions (%s) — using residual baseline", exc)
        expected_mean = None
        n_times = len(df)

    # Manual per-channel adstock contributions
    posterior = fit_result.posterior
    n_samples = posterior.n_samples
    if n_times is None:
        n_times = len(df)

    contributions: dict[str, list[float]] = {}
    for i, ch in enumerate(fit_result.channel_names):
        spend = df[ch].to_numpy(dtype=float)
        scale = fit_result.max_weekly_spend.get(ch) or 1.0
        spend_norm = spend / scale
        alpha = posterior.alpha[:, i]
        ec = posterior.ec[:, i]
        slope_p = posterior.slope[:, i]
        beta = posterior.beta[:, i]

        adstocked = np.zeros((n_samples, n_times))
        adstocked[:, 0] = spend_norm[0]
        for t in range(1, n_times):
            adstocked[:, t] = spend_norm[t] + alpha * adstocked[:, t - 1]

        a_n = np.power(np.maximum(adstocked, 0.0), slope_p[:, np.newaxis])
        e_n = np.power(np.maximum(ec[:, np.newaxis], 1e-12), slope_p[:, np.newaxis])
        hill = a_n / (e_n + a_n + 1e-12)
        contrib = beta[:, np.newaxis] * hill * fit_result.kpi_scale
        contributions[ch] = contrib.mean(axis=0).tolist()

    total_media = sum(np.array(v) for v in contributions.values())

    if expected_mean is not None:
        # Baseline = full model prediction - media contributions
        # ŷ = baseline + media → baseline = ŷ - Σ(media_m)
        baseline = np.maximum(expected_mean - total_media, 0.0).tolist()
    else:
        # Residual fallback: baseline = actual - media
        actual_arr = df["acquisitions"].to_numpy(dtype=float)
        baseline = np.maximum(actual_arr - total_media, 0.0).tolist()

    return {"dates": dates, "contributions": contributions, "baseline": baseline}


def extract_fit_metrics(fit_result: FitResult) -> dict:
    """
    Extract R², MAPE, wMAPE using Meridian's ModelDiagnostics API.
    Returns dict with r_squared, mape, wmape (all may be None on failure).
    """
    try:
        from meridian.analysis import model_diagnostics as md_lib

        md = md_lib.ModelDiagnostics(fit_result.mmm)
        table = md.predictive_accuracy_table()
        # table is an xarray Dataset or DataFrame — extract scalars
        arr = np.array(table)
        # Columns are typically: R-squared, MAPE, wMAPE (order may vary)
        # Access by variable name to be safe
        r_sq = float(table["r_squared"].values) if "r_squared" in table else None
        mape = float(table["mape"].values) if "mape" in table else None
        wmape = float(table["wmape"].values) if "wmape" in table else None
        return {"r_squared": r_sq, "mape": mape, "wmape": wmape}
    except Exception as exc:
        logger.warning("Could not extract fit metrics (%s)", exc)
        return {"r_squared": None, "mape": None, "wmape": None}
