"""
Response curve extraction from fitted Meridian posterior samples.

For each channel we sweep weekly spend from 0 to 1.5× the maximum observed
weekly spend. At each spend level we compute the expected steady-state
contribution using the Hill-Adstock model:

    Adstock(s) = s / (1 - α)          [geometric decay at steady state]
    Hill(x)    = x^n / (EC^n + x^n)
    contrib    = β × Hill(Adstock(s))

We compute this for every posterior sample and then aggregate to the mean
(for the optimiser) and the 10th/90th percentiles (for CI ribbons in the UI).
"""
from __future__ import annotations

import numpy as np

from app.mmm.schemas import FitResult, PosteriorSamples
from app.models.results import ResponseCurveData


_N_POINTS = 100         # number of spend grid points per channel
_CURVE_FACTOR = 1.5     # sweep up to 1.5× max observed weekly spend
_CI_LOWER = 10          # percentile for lower CI band
_CI_UPPER = 90          # percentile for upper CI band


def _hill_adstock_contribution(
    spend: np.ndarray,    # shape (n_points,)
    alpha: np.ndarray,    # shape (n_samples,)
    ec: np.ndarray,       # shape (n_samples,)
    slope: np.ndarray,    # shape (n_samples,)
    beta: np.ndarray,     # shape (n_samples,)
) -> np.ndarray:
    """
    Compute contribution for a range of spend levels across all posterior samples.

    Returns array of shape (n_samples, n_points).

    Steady-state adstock assumes the channel has been running at spend level `s`
    long enough for the geometric decay to converge. This is a reasonable
    approximation for response-curve visualisation.
    """
    # spend:  (n_points,)
    # alpha:  (n_samples,) — broadcast to (n_samples, n_points)
    s = spend[np.newaxis, :]                     # (1, n_points)
    a = alpha[:, np.newaxis]                     # (n_samples, 1)
    e = ec[:, np.newaxis]                        # (n_samples, 1)
    n = slope[:, np.newaxis]                     # (n_samples, 1)
    b = beta[:, np.newaxis]                      # (n_samples, 1)

    # Steady-state adstocked spend (clip alpha away from 1 to avoid div/0)
    a_safe = np.clip(a, 0.0, 0.999)
    adstocked = s / (1.0 - a_safe)              # (n_samples, n_points)

    # Hill saturation
    adstocked_n = adstocked ** n
    ec_n = e ** n
    hill = adstocked_n / (ec_n + adstocked_n + 1e-12)  # (n_samples, n_points)

    return b * hill                              # (n_samples, n_points)


def extract_response_curves(
    fit_result: FitResult,
    n_points: int = _N_POINTS,
) -> dict[str, ResponseCurveData]:
    """
    Compute per-channel response curves from posterior samples.

    Returns a dict mapping channel name → ResponseCurveData with spend grid,
    mean acquisitions, and CI lower/upper arrays.
    """
    posterior: PosteriorSamples = fit_result.posterior
    curves: dict[str, ResponseCurveData] = {}

    for i, channel in enumerate(fit_result.channel_names):
        max_spend = fit_result.max_weekly_spend[channel]
        # Always include spend=0 and extend slightly beyond max observed
        spend_grid = np.linspace(0.0, max_spend * _CURVE_FACTOR, n_points)

        # The Hill/adstock model was estimated on media normalized to [0, 1]
        # (divided by max_weekly_spend).  We must apply the same normalization
        # before evaluating the curve; the x-axis (spend_grid) stays in dollars
        # for the optimizer and UI, but the model only sees the normalized values.
        scale = max_spend if max_spend > 0 else 1.0
        spend_normalized = spend_grid / scale

        contrib = _hill_adstock_contribution(
            spend=spend_normalized,
            alpha=posterior.alpha[:, i],
            ec=posterior.ec[:, i],
            slope=posterior.slope[:, i],
            beta=posterior.beta[:, i],
        )  # (n_samples, n_points)

        # Back-transform from normalized KPI units to real acquisitions
        kpi_scale = getattr(fit_result, "kpi_scale", 1.0)
        contrib_real = contrib * kpi_scale

        curves[channel] = ResponseCurveData(
            spend_points=spend_grid.tolist(),
            acquisitions=contrib_real.mean(axis=0).tolist(),
            ci_lower=np.percentile(contrib_real, _CI_LOWER, axis=0).tolist(),
            ci_upper=np.percentile(contrib_real, _CI_UPPER, axis=0).tolist(),
        )

    return curves
