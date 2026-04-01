from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class RunStatus(str, Enum):
    queued = "queued"
    fitting = "fitting"
    optimizing = "optimizing"
    completed = "completed"
    failed = "failed"


class ChannelConstraint(BaseModel):
    min_fraction: float = 0.0
    max_fraction: float = 1.0


class MeridianConfig(BaseModel):
    n_chains: int = 4
    n_warmup: int = 500
    n_samples: int = 1000
    roi_mu: float | None = None
    roi_sigma: float | None = None
    enable_aks: bool = False   # Automatic Knot Selection — fits spline over time to capture seasonality


# ---------------------------------------------------------------------------
# Request body for POST /runs
# ---------------------------------------------------------------------------

class RunCreate(BaseModel):
    upload_id: str
    run_label: str
    total_budget: float          # per-period budget (week / day / month)
    planning_period_label: str = "Quarterly"   # e.g. "Quarterly", "Annual"
    n_periods: int = 13          # number of data periods in the planning window
    # If omitted, all channels from the upload are used
    channel_names: list[str] | None = None
    channel_constraints: dict[str, ChannelConstraint] = Field(default_factory=dict)
    meridian_config: MeridianConfig = Field(default_factory=MeridianConfig)


# ---------------------------------------------------------------------------
# Internal record (stored in Redis)
# ---------------------------------------------------------------------------

class RunRecord(BaseModel):
    run_id: str = Field(default_factory=_new_uuid)
    session_id: str
    upload_id: str
    run_label: str
    status: RunStatus = RunStatus.queued
    created_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    progress_pct: int = 0
    error_message: str | None = None
    celery_task_id: str | None = None
    total_budget: float          # per-period budget
    planning_period_label: str = "Quarterly"
    n_periods: int = 13
    channel_constraints: dict[str, ChannelConstraint] = Field(default_factory=dict)
    meridian_config: MeridianConfig = Field(default_factory=MeridianConfig)


# ---------------------------------------------------------------------------
# API response shapes
# ---------------------------------------------------------------------------

class RunSummary(BaseModel):
    run_id: str
    run_label: str
    status: RunStatus
    created_at: datetime
    completed_at: datetime | None
    progress_pct: int
    error_message: str | None


class RunDetail(RunSummary):
    session_id: str
    celery_task_id: str | None


class RunListResponse(BaseModel):
    runs: list[RunSummary]


class RunCreateResponse(BaseModel):
    run_id: str
    session_id: str
    run_label: str
    status: RunStatus
    created_at: datetime
    celery_task_id: str | None
