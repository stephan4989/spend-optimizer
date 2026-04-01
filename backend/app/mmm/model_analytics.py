"""
Extract time-series model analytics from a fitted Meridian model.

Two functions:

  extract_model_fit     — actual KPI vs posterior-predictive mean + CI band
  extract_contributions — per-channel media contributions over time using
                          proper time-series adstock (not steady-state)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from app.mmm.schemas import FitResult

logger = logging.getLogger(__name__)


def extract_model_fit(
    mmm,
    df: pd.DataFrame,
    kpi_scale: float,
) -> dict:
    """
    Extract actual vs predicted time series from the posterior predictive.

    Returns dict keys: dates, actual, predicted_mean, predicted_lower, predicted_upper.
    Falls back to actual for all prediction fields if posterior_predictive is unavailable.
    """
    date_col = "date" if "date" in df.columns else "week"
    dates = df[date_col].astype(str).tolist()
    actual = df["acquisitions"].to_numpy(dtype=float).tolist()

    try:
        pp = mmm.inference_data.posterior_predictive
        # Shape: (chain, draw, geo, time) — take national geo index 0
        kpi_pp = pp["kpi"].values[:, :, 0, :]   # (chain, draw, time)
        n_chains, n_draws, _ = kpi_pp.shape
        kpi_flat = kpi_pp.reshape(n_chains * n_draws, -1) * kpi_scale

        return {
            "dates": dates,
            "actual": actual,
            "predicted_mean": kpi_flat.mean(axis=0).tolist(),
            "predicted_lower": np.percentile(kpi_flat, 10, axis=0).tolist(),
            "predicted_upper": np.percentile(kpi_flat, 90, axis=0).tolist(),
        }
    except Exception as exc:
        logger.warning("Could not extract posterior_predictive (%s) — using actual as fallback", exc)
        return {
            "dates": dates,
            "actual": actual,
            "predicted_mean": actual,
            "predicted_lower": actual,
            "predicted_upper": actual,
        }


def extract_channel_contributions(
    df: pd.DataFrame,
    fit_result: FitResult,
) -> dict:
    """
    Compute per-channel media contributions over time.

    Uses proper recursive geometric adstock at each time step rather than the
    steady-state approximation used for response curves. Averages over all
    posterior samples to produce a single expected contribution per period.

    Returns dict keys: dates, contributions (channel → list[float]).
    """
    date_col = "date" if "date" in df.columns else "week"
    dates = df[date_col].astype(str).tolist()

    posterior = fit_result.posterior
    n_samples = posterior.n_samples
    n_times = len(df)

    contributions: dict[str, list[float]] = {}

    for i, ch in enumerate(fit_result.channel_names):
        spend = df[ch].to_numpy(dtype=float)
        scale = fit_result.max_weekly_spend.get(ch) or 1.0
        spend_norm = spend / scale

        alpha = posterior.alpha[:, i]    # (n_samples,)
        ec = posterior.ec[:, i]
        slope_p = posterior.slope[:, i]
        beta = posterior.beta[:, i]

        # Recursive adstock: adstocked[t] = spend_norm[t] + alpha * adstocked[t-1]
        # Vectorised over samples: (n_samples, n_times)
        adstocked = np.zeros((n_samples, n_times))
        adstocked[:, 0] = spend_norm[0]
        for t in range(1, n_times):
            adstocked[:, t] = spend_norm[t] + alpha * adstocked[:, t - 1]

        # Hill saturation
        a_safe = np.maximum(adstocked, 0.0)
        a_n = np.power(a_safe, slope_p[:, np.newaxis])
        e_n = np.power(np.maximum(ec[:, np.newaxis], 1e-12), slope_p[:, np.newaxis])
        hill = a_n / (e_n + a_n + 1e-12)

        # Back-transform to real acquisition units
        contrib = beta[:, np.newaxis] * hill * fit_result.kpi_scale
        contributions[ch] = contrib.mean(axis=0).tolist()

    # Baseline = actual KPI minus the sum of all channel contributions, floored at 0.
    # This captures intercept, trend, seasonality — everything not attributed to paid media.
    actual = df["acquisitions"].to_numpy(dtype=float)
    total_media = np.zeros(n_times)
    for ch_contrib in contributions.values():
        total_media += np.array(ch_contrib)
    baseline = np.maximum(actual - total_media, 0.0).tolist()

    return {"dates": dates, "contributions": contributions, "baseline": baseline}
