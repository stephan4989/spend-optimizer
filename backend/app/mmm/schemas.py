"""
Internal dataclasses for the MMM layer.

These are not Pydantic models — they live in memory inside the Celery worker
and are never serialized to Redis directly. Only the final RunResults (in
app/models/results.py) gets persisted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PosteriorSamples:
    """
    Flattened posterior arrays extracted from the Meridian InferenceData.

    All arrays have shape (n_samples, n_channels) where
    n_samples = n_chains * n_keep (e.g. 4 * 1000 = 4000).

    alpha      : geometric adstock decay parameter ∈ [0, 1)
    ec         : hill saturation half-point (units = adstocked spend)
    slope      : hill function slope (controls curvature)
    beta       : channel-level scaling coefficient (contribution per hill unit)
    tau        : geo-level intercept (n_samples,) — baseline when all media = 0
    gamma_trend: linear trend coefficient (n_samples,) — None if no trend control
    """
    alpha: np.ndarray         # (n_samples, n_channels)
    ec: np.ndarray            # (n_samples, n_channels)
    slope: np.ndarray         # (n_samples, n_channels)
    beta: np.ndarray          # (n_samples, n_channels)
    channel_names: list[str]
    tau: np.ndarray | None = None          # (n_samples,)
    gamma_trend: np.ndarray | None = None  # (n_samples,)

    @property
    def n_samples(self) -> int:
        return self.alpha.shape[0]

    @property
    def n_channels(self) -> int:
        return self.alpha.shape[1]


@dataclass
class FitResult:
    """Everything the downstream steps need after Meridian finishes."""
    # Raw Meridian model object — held in worker memory, never serialized
    mmm: object
    channel_names: list[str]
    n_time_periods: int
    # Extracted and flattened posterior samples, ready for curve computation
    posterior: PosteriorSamples
    # Max observed weekly spend per channel — used to set curve x-axis range
    max_weekly_spend: dict[str, float]
    # Mean KPI used to normalize acquisitions before fitting — multiply back
    # into response curve contributions to return real acquisition units
    kpi_scale: float
    # Diagnostics extracted from the posterior
    r_hat_max: float
    ess_bulk_min: int
    # Standardised trend values passed as control variable (n_times,)
    # Stored here so model_analytics can reconstruct trend contribution
    trend_values: np.ndarray | None = None


@dataclass
class MMMJobPayload:
    """Serialized over Celery (JSON). Must contain only JSON-safe types."""
    run_id: str
    session_id: str
    upload_id: str
    channel_names: list[str]
    total_budget: float
    channel_constraints: dict  # dict[str, ChannelConstraint.model_dump()]
    meridian_config: dict      # MeridianConfig.model_dump()
