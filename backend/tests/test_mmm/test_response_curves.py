"""
Unit tests for response curve extraction.

These tests do NOT require Meridian to be installed — they construct synthetic
PosteriorSamples directly and verify the curve math.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.mmm.schemas import FitResult, PosteriorSamples
from app.mmm.response_curves import (
    _hill_adstock_contribution,
    extract_response_curves,
    _N_POINTS,
)


def _make_posterior(
    n_samples: int = 200,
    n_channels: int = 3,
    alpha: float = 0.5,
    ec: float = 50000.0,
    slope: float = 2.0,
    beta: float = 0.001,
) -> PosteriorSamples:
    """Synthetic posterior with constant (non-random) values for deterministic tests."""
    channels = [f"ch_{i}" for i in range(n_channels)]
    return PosteriorSamples(
        alpha=np.full((n_samples, n_channels), alpha),
        ec=np.full((n_samples, n_channels), ec),
        slope=np.full((n_samples, n_channels), slope),
        beta=np.full((n_samples, n_channels), beta),
        channel_names=channels,
    )


def _make_fit_result(n_channels: int = 3) -> FitResult:
    posterior = _make_posterior(n_channels=n_channels)
    channels = posterior.channel_names
    return FitResult(
        mmm=None,
        channel_names=channels,
        n_time_periods=52,
        posterior=posterior,
        max_weekly_spend={ch: 100_000.0 for ch in channels},
        r_hat_max=1.01,
        ess_bulk_min=400,
    )


# ---------------------------------------------------------------------------
# hill_adstock_contribution
# ---------------------------------------------------------------------------

def test_contribution_at_zero_spend_is_zero():
    spend = np.array([0.0, 50000.0, 100000.0])
    alpha = np.full((10,), 0.5)
    ec = np.full((10,), 50000.0)
    slope = np.full((10,), 2.0)
    beta = np.full((10,), 0.001)

    contrib = _hill_adstock_contribution(spend, alpha, ec, slope, beta)
    # At spend=0, adstocked=0, hill=0, contribution=0
    assert contrib[:, 0].max() == pytest.approx(0.0, abs=1e-12)


def test_contribution_monotonically_increasing():
    """More spend → more contribution (diminishing returns but always increasing)."""
    spend = np.linspace(0, 200_000, 50)
    alpha = np.full((100,), 0.5)
    ec = np.full((100,), 50_000.0)
    slope = np.full((100,), 2.0)
    beta = np.full((100,), 0.001)

    contrib = _hill_adstock_contribution(spend, alpha, ec, slope, beta)
    mean_contrib = contrib.mean(axis=0)
    diffs = np.diff(mean_contrib)
    assert (diffs >= 0).all(), "Response curve should be non-decreasing"


def test_contribution_asymptotes():
    """At very high spend the curve should flatten (Hill saturation)."""
    spend_low = np.array([100_000.0])
    spend_high = np.array([10_000_000.0])
    alpha = np.full((50,), 0.5)
    ec = np.full((50,), 50_000.0)
    slope = np.full((50,), 2.0)
    beta = np.full((50,), 1.0)

    c_low = _hill_adstock_contribution(spend_low, alpha, ec, slope, beta).mean()
    c_high = _hill_adstock_contribution(spend_high, alpha, ec, slope, beta).mean()

    # High spend should be close to asymptote (beta * 1), much more than low
    # but not dramatically so
    ratio = c_high / c_low
    assert ratio < 2.0, "Curve should be saturating — high spend not dramatically larger"
    assert ratio > 1.0, "High spend should still be larger"


def test_ci_bounds_are_wider_with_variance():
    """When posterior has variance, CI bands should be wider than the mean."""
    n_samples = 500
    n_channels = 2
    rng = np.random.default_rng(42)

    # Add variance to alpha and beta
    posterior = PosteriorSamples(
        alpha=rng.uniform(0.3, 0.7, (n_samples, n_channels)),
        ec=rng.uniform(40_000, 60_000, (n_samples, n_channels)),
        slope=rng.uniform(1.5, 2.5, (n_samples, n_channels)),
        beta=rng.uniform(0.0005, 0.0015, (n_samples, n_channels)),
        channel_names=["ch_0", "ch_1"],
    )
    fit = FitResult(
        mmm=None,
        channel_names=["ch_0", "ch_1"],
        n_time_periods=52,
        posterior=posterior,
        max_weekly_spend={"ch_0": 100_000.0, "ch_1": 80_000.0},
        r_hat_max=1.01,
        ess_bulk_min=400,
    )

    curves = extract_response_curves(fit)
    for ch, curve in curves.items():
        acq = np.array(curve.acquisitions)
        lo = np.array(curve.ci_lower)
        hi = np.array(curve.ci_upper)
        # CI should bracket the mean (ignore spend=0 where all are 0)
        mid = len(acq) // 2
        assert lo[mid] <= acq[mid], f"{ch}: ci_lower should be <= mean at mid-point"
        assert hi[mid] >= acq[mid], f"{ch}: ci_upper should be >= mean at mid-point"
        assert hi[mid] > lo[mid], f"{ch}: CI should have positive width"


# ---------------------------------------------------------------------------
# extract_response_curves
# ---------------------------------------------------------------------------

def test_extract_returns_all_channels():
    fit = _make_fit_result(n_channels=3)
    curves = extract_response_curves(fit)
    assert set(curves.keys()) == set(fit.channel_names)


def test_extract_curve_has_correct_length():
    fit = _make_fit_result()
    curves = extract_response_curves(fit, n_points=50)
    for curve in curves.values():
        assert len(curve.spend_points) == 50
        assert len(curve.acquisitions) == 50
        assert len(curve.ci_lower) == 50
        assert len(curve.ci_upper) == 50


def test_extract_spend_starts_at_zero():
    fit = _make_fit_result()
    curves = extract_response_curves(fit)
    for curve in curves.values():
        assert curve.spend_points[0] == pytest.approx(0.0)


def test_extract_spend_ends_at_1_5x_max():
    fit = _make_fit_result()
    curves = extract_response_curves(fit)
    for ch, curve in curves.items():
        expected_max = fit.max_weekly_spend[ch] * 1.5
        assert curve.spend_points[-1] == pytest.approx(expected_max, rel=1e-6)
