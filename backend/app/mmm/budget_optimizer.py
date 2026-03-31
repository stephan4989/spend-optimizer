"""
Budget allocation optimizer.

Given pre-computed per-channel response curves (spend → acquisitions) and a
total budget, find the channel spend allocation that maximises total expected
acquisitions subject to:

  1. sum(spend_c for c in channels) == total_budget
  2. spend_c >= total_budget * min_fraction_c   (optional per-channel floor)
  3. spend_c <= total_budget * max_fraction_c   (optional per-channel ceiling)

We use scipy.optimize.minimize with method='SLSQP' and interpolate the
response curves at each candidate spend level via numpy.interp.
"""
from __future__ import annotations

import logging

import numpy as np
from scipy.optimize import minimize

from app.models.results import ResponseCurveData
from app.models.run import ChannelConstraint

logger = logging.getLogger(__name__)

_DEFAULT_CONSTRAINT = ChannelConstraint(min_fraction=0.0, max_fraction=1.0)


def _interp_response(curve: ResponseCurveData, spend: float) -> float:
    """
    Linear interpolation of the response curve at a given spend level.

    Clamps to the curve endpoints so extrapolation is safe for the optimiser.
    """
    return float(
        np.interp(
            spend,
            curve.spend_points,
            curve.acquisitions,
        )
    )


def optimize_budget(
    response_curves: dict[str, ResponseCurveData],
    total_budget: float,
    channel_constraints: dict[str, ChannelConstraint] | None = None,
) -> dict[str, float]:
    """
    Return the optimal spend allocation per channel.

    Parameters
    ----------
    response_curves:
        Mapping channel → ResponseCurveData (from extract_response_curves).
    total_budget:
        Total spend to allocate across all channels.
    channel_constraints:
        Optional per-channel fraction bounds. Defaults to [0, 1] for all channels.

    Returns
    -------
    dict mapping channel name → optimal spend (floats sum to total_budget).
    """
    if channel_constraints is None:
        channel_constraints = {}

    channels = list(response_curves.keys())
    n = len(channels)

    if n == 0:
        return {}

    if total_budget <= 0:
        return {ch: 0.0 for ch in channels}

    # Starting point: equal split
    x0 = np.full(n, total_budget / n)

    def neg_total_acquisitions(x: np.ndarray) -> float:
        return -sum(
            _interp_response(response_curves[ch], x[i])
            for i, ch in enumerate(channels)
        )

    # Gradient via finite differences (scipy default for SLSQP)
    equality = {
        "type": "eq",
        "fun": lambda x: x.sum() - total_budget,
    }

    bounds = []
    for ch in channels:
        constraint = channel_constraints.get(ch, _DEFAULT_CONSTRAINT)
        lb = max(0.0, total_budget * constraint.min_fraction)
        ub = min(total_budget, total_budget * constraint.max_fraction)
        # Guard: lb must not exceed ub
        if lb > ub:
            lb = 0.0
            ub = total_budget
        bounds.append((lb, ub))

    result = minimize(
        neg_total_acquisitions,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=[equality],
        options={"ftol": 1e-9, "maxiter": 1000},
    )

    if not result.success:
        logger.warning("Budget optimisation did not fully converge: %s", result.message)

    optimal = {ch: float(result.x[i]) for i, ch in enumerate(channels)}

    # Normalise to ensure exact budget sum despite floating-point drift
    total = sum(optimal.values())
    if total > 0:
        optimal = {ch: v / total * total_budget for ch, v in optimal.items()}

    return optimal


def compute_prior_allocation(
    df,
    channel_names: list[str],
    total_budget: float,
) -> dict[str, float]:
    """
    Derive the 'prior' (historical) allocation by applying historical spend
    proportions to the new total budget.

    If all historical spend is zero (unlikely), falls back to equal split.
    """
    historical_totals = {ch: float(df[ch].sum()) for ch in channel_names}
    grand_total = sum(historical_totals.values())

    if grand_total == 0:
        equal = total_budget / len(channel_names)
        return {ch: equal for ch in channel_names}

    return {ch: (historical_totals[ch] / grand_total) * total_budget for ch in channel_names}


def compute_total_acquisitions(
    response_curves: dict[str, ResponseCurveData],
    allocation: dict[str, float],
) -> float:
    """
    Estimate total acquisitions for a given budget allocation by summing
    the interpolated response at each channel's allocated spend.
    """
    return sum(
        _interp_response(response_curves[ch], spend)
        for ch, spend in allocation.items()
        if ch in response_curves
    )
