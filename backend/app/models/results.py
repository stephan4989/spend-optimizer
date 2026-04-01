from __future__ import annotations

from pydantic import BaseModel


class ResponseCurveData(BaseModel):
    spend_points: list[float]
    acquisitions: list[float]
    ci_lower: list[float]
    ci_upper: list[float]


class ModelDiagnostics(BaseModel):
    r_hat_max: float
    ess_bulk_min: int
    waic: float | None = None


class ModelFitData(BaseModel):
    """Actual KPI vs model posterior-predictive mean + credible interval."""
    dates: list[str]
    actual: list[float]
    predicted_mean: list[float]
    predicted_lower: list[float]   # 10th percentile
    predicted_upper: list[float]   # 90th percentile


class ContributionData(BaseModel):
    """Per-channel media contributions over time (time-series adstock)."""
    dates: list[str]
    contributions: dict[str, list[float]]   # channel → per-period values
    baseline: list[float]                   # actual - sum(channel_contributions), floored at 0


class RunResults(BaseModel):
    run_id: str
    run_label: str
    channels: list[str]
    response_curves: dict[str, ResponseCurveData]
    prior_allocation: dict[str, float]       # per-period spend
    optimized_allocation: dict[str, float]   # per-period spend
    prior_total_acquisitions: float
    optimized_total_acquisitions: float
    lift_pct: float
    model_diagnostics: ModelDiagnostics
    planning_period_label: str = "Quarterly"
    n_periods: int = 13
    # Time-series analytics — optional so existing serialised results still load
    model_fit: ModelFitData | None = None
    contributions: ContributionData | None = None
