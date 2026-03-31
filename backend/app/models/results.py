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


class RunResults(BaseModel):
    run_id: str
    run_label: str
    channels: list[str]
    response_curves: dict[str, ResponseCurveData]
    prior_allocation: dict[str, float]
    optimized_allocation: dict[str, float]
    prior_total_acquisitions: float
    optimized_total_acquisitions: float
    lift_pct: float
    model_diagnostics: ModelDiagnostics
