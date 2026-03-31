"""
Unit tests for the budget optimizer.

These tests do NOT require Meridian — they work with pre-computed response
curves and verify the scipy SLSQP optimisation logic directly.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.mmm.budget_optimizer import (
    optimize_budget,
    compute_prior_allocation,
    compute_total_acquisitions,
)
from app.models.results import ResponseCurveData
from app.models.run import ChannelConstraint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _linear_curve(channel: str, slope: float, max_spend: float = 500_000.0) -> ResponseCurveData:
    """Simple linear response: acquisitions = slope * spend. Easy to reason about."""
    spend = np.linspace(0, max_spend, 100)
    return ResponseCurveData(
        spend_points=spend.tolist(),
        acquisitions=(slope * spend).tolist(),
        ci_lower=(slope * spend * 0.9).tolist(),
        ci_upper=(slope * spend * 1.1).tolist(),
    )


def _concave_curve(channel: str, ec: float = 100_000.0, max_spend: float = 500_000.0) -> ResponseCurveData:
    """Concave diminishing-returns curve: acquisitions = sqrt(spend/ec)."""
    spend = np.linspace(0, max_spend, 100)
    acq = np.sqrt(spend / ec)
    return ResponseCurveData(
        spend_points=spend.tolist(),
        acquisitions=acq.tolist(),
        ci_lower=(acq * 0.9).tolist(),
        ci_upper=(acq * 1.1).tolist(),
    )


# ---------------------------------------------------------------------------
# optimize_budget
# ---------------------------------------------------------------------------

def test_budget_sum_equals_total():
    """Allocated spend must always sum to exactly the total budget."""
    curves = {
        "tv": _concave_curve("tv", ec=80_000),
        "search": _concave_curve("search", ec=50_000),
        "social": _concave_curve("social", ec=30_000),
    }
    total = 300_000.0
    result = optimize_budget(curves, total)

    assert sum(result.values()) == pytest.approx(total, rel=1e-6)


def test_budget_all_channels_get_spend():
    """With concave curves and no constraints, every channel should get some spend."""
    curves = {
        "tv": _concave_curve("tv", ec=80_000),
        "search": _concave_curve("search", ec=50_000),
        "social": _concave_curve("social", ec=30_000),
    }
    result = optimize_budget(curves, 300_000.0)
    for ch, spend in result.items():
        assert spend > 0, f"Channel {ch} should receive non-zero spend"


def test_budget_higher_roi_gets_more_with_linear_curves():
    """
    With linear curves, the optimiser should allocate all budget to the
    highest-slope channel (since it has constant marginal returns).
    """
    curves = {
        "high_roi": _linear_curve("high_roi", slope=0.01),   # 1 acq per $100
        "low_roi": _linear_curve("low_roi", slope=0.001),    # 1 acq per $1000
    }
    result = optimize_budget(curves, 200_000.0)
    # With linear curves, optimum is corner solution: all to high_roi
    assert result["high_roi"] > result["low_roi"]


def test_budget_respects_min_fraction_constraint():
    curves = {
        "tv": _concave_curve("tv"),
        "search": _concave_curve("search"),
    }
    constraints = {
        "tv": ChannelConstraint(min_fraction=0.4, max_fraction=1.0),
        "search": ChannelConstraint(min_fraction=0.0, max_fraction=1.0),
    }
    total = 200_000.0
    result = optimize_budget(curves, total, constraints)

    assert result["tv"] >= total * 0.4 - 1.0  # allow tiny float tolerance


def test_budget_respects_max_fraction_constraint():
    curves = {
        "tv": _concave_curve("tv", ec=200_000),  # very efficient
        "search": _concave_curve("search", ec=50_000),
    }
    constraints = {
        "tv": ChannelConstraint(min_fraction=0.0, max_fraction=0.3),
        "search": ChannelConstraint(min_fraction=0.0, max_fraction=1.0),
    }
    total = 200_000.0
    result = optimize_budget(curves, total, constraints)

    assert result["tv"] <= total * 0.3 + 1.0  # allow tiny float tolerance


def test_budget_zero_total():
    curves = {"tv": _concave_curve("tv"), "search": _concave_curve("search")}
    result = optimize_budget(curves, 0.0)
    assert all(v == 0.0 for v in result.values())


def test_budget_single_channel():
    curves = {"tv": _concave_curve("tv")}
    total = 100_000.0
    result = optimize_budget(curves, total)
    assert result["tv"] == pytest.approx(total, rel=1e-6)


def test_budget_empty_curves():
    result = optimize_budget({}, 100_000.0)
    assert result == {}


# ---------------------------------------------------------------------------
# compute_prior_allocation
# ---------------------------------------------------------------------------

def test_prior_allocation_proportional():
    import pandas as pd
    df = pd.DataFrame({
        "week": ["2024-01-01"] * 4,
        "tv": [100_000.0] * 4,        # 50% of total
        "search": [100_000.0] * 4,    # 50% of total
        "acquisitions": [1000.0] * 4,
    })
    result = compute_prior_allocation(df, ["tv", "search"], total_budget=200_000.0)

    assert result["tv"] == pytest.approx(100_000.0, rel=1e-6)
    assert result["search"] == pytest.approx(100_000.0, rel=1e-6)


def test_prior_allocation_unequal():
    import pandas as pd
    df = pd.DataFrame({
        "week": ["2024-01-01"] * 4,
        "tv": [300_000.0] * 4,        # 75%
        "search": [100_000.0] * 4,    # 25%
        "acquisitions": [1000.0] * 4,
    })
    result = compute_prior_allocation(df, ["tv", "search"], total_budget=400_000.0)

    assert result["tv"] == pytest.approx(300_000.0, rel=1e-6)
    assert result["search"] == pytest.approx(100_000.0, rel=1e-6)


def test_prior_allocation_sums_to_budget():
    import pandas as pd
    df = pd.DataFrame({
        "week": ["2024-01-01"] * 52,
        "tv": np.random.uniform(10_000, 100_000, 52).tolist(),
        "search": np.random.uniform(5_000, 50_000, 52).tolist(),
        "social": np.random.uniform(2_000, 20_000, 52).tolist(),
        "acquisitions": [500.0] * 52,
    })
    total = 500_000.0
    result = compute_prior_allocation(df, ["tv", "search", "social"], total)
    assert sum(result.values()) == pytest.approx(total, rel=1e-6)


# ---------------------------------------------------------------------------
# compute_total_acquisitions
# ---------------------------------------------------------------------------

def test_compute_total_acquisitions():
    curves = {
        "tv": _linear_curve("tv", slope=0.01),       # $50k → 500 acq
        "search": _linear_curve("search", slope=0.02),  # $50k → 1000 acq
    }
    allocation = {"tv": 50_000.0, "search": 50_000.0}
    total = compute_total_acquisitions(curves, allocation)
    assert total == pytest.approx(1500.0, rel=1e-3)
