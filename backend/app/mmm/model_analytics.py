"""
Extract time-series model analytics from a fitted Meridian model.

  extract_model_fit           — actual KPI vs predicted (intercept + trend + media)
  extract_channel_contributions — per-channel adstock contributions + proper baseline
                                   (intercept + linear trend, not a residual)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from app.mmm.schemas import FitResult

logger = logging.getLogger(__name__)


def _channel_adstock_contributions(
    df: pd.DataFrame,
    fit_result: FitResult,
) -> np.ndarray:
    """
    Compute (n_samples, n_times) array of total media contributions across channels.
    Shared by both extract_model_fit and extract_channel_contributions to avoid
    duplicating the inner loop.
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

    return total  # (n_samples, n_times)


def _baseline_contribution(
    fit_result: FitResult,
    n_times: int,
) -> np.ndarray:
    """
    Compute (n_samples, n_times) array for the baseline component:
        baseline = (tau_g + gamma_trend * trend_values) * kpi_scale

    tau_g is the intercept (KPI when all media = 0).
    gamma_trend * trend captures structural growth/decline.
    Both are in normalised KPI units, so multiply back by kpi_scale.

    Falls back gracefully if tau_g or gamma_trend were not extracted.
    """
    posterior = fit_result.posterior
    n_samples = posterior.n_samples
    baseline = np.zeros((n_samples, n_times))

    if posterior.tau is not None:
        # tau: (n_samples,) → broadcast to (n_samples, n_times)
        baseline += posterior.tau[:, np.newaxis] * fit_result.kpi_scale

    if posterior.gamma_trend is not None and fit_result.trend_values is not None:
        # gamma_trend: (n_samples,), trend_values: (n_times,)
        trend_contrib = (
            posterior.gamma_trend[:, np.newaxis]
            * fit_result.trend_values[np.newaxis, :]
            * fit_result.kpi_scale
        )
        baseline += trend_contrib

    return baseline  # (n_samples, n_times)


def extract_model_fit(
    df: pd.DataFrame,
    fit_result: FitResult,
) -> dict:
    """
    Compute actual vs model-predicted time series.

    Predicted = intercept + trend + sum(channel contributions).
    CI is the 10/90 percentile across posterior samples.
    """
    date_col = "date" if "date" in df.columns else "week"
    dates = df[date_col].astype(str).tolist()
    actual = df["acquisitions"].to_numpy(dtype=float).tolist()

    n_times = len(df)
    media_contrib = _channel_adstock_contributions(df, fit_result)
    baseline_contrib = _baseline_contribution(fit_result, n_times)
    predicted = media_contrib + baseline_contrib  # (n_samples, n_times)

    return {
        "dates": dates,
        "actual": actual,
        "predicted_mean": predicted.mean(axis=0).tolist(),
        "predicted_lower": np.percentile(predicted, 10, axis=0).tolist(),
        "predicted_upper": np.percentile(predicted, 90, axis=0).tolist(),
    }


def extract_channel_contributions(
    df: pd.DataFrame,
    fit_result: FitResult,
) -> dict:
    """
    Compute per-channel media contributions + intercept/trend baseline over time.

    Baseline is properly estimated from tau_g (intercept) and gamma_trend
    (linear trend coefficient), not a residual subtraction.
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

        alpha = posterior.alpha[:, i]
        ec = posterior.ec[:, i]
        slope_p = posterior.slope[:, i]
        beta = posterior.beta[:, i]

        adstocked = np.zeros((n_samples, n_times))
        adstocked[:, 0] = spend_norm[0]
        for t in range(1, n_times):
            adstocked[:, t] = spend_norm[t] + alpha * adstocked[:, t - 1]

        a_safe = np.maximum(adstocked, 0.0)
        a_n = np.power(a_safe, slope_p[:, np.newaxis])
        e_n = np.power(np.maximum(ec[:, np.newaxis], 1e-12), slope_p[:, np.newaxis])
        hill = a_n / (e_n + a_n + 1e-12)

        contrib = beta[:, np.newaxis] * hill * fit_result.kpi_scale
        contributions[ch] = contrib.mean(axis=0).tolist()

    # Baseline: posterior mean of (intercept + trend) — not a residual
    baseline_samples = _baseline_contribution(fit_result, n_times)
    baseline = np.maximum(baseline_samples.mean(axis=0), 0.0).tolist()

    return {"dates": dates, "contributions": contributions, "baseline": baseline}
