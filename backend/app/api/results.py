from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_run_repo, require_session
from app.models.results import RunResults
from app.models.run import ChannelConstraint, RunStatus
from app.models.session import SessionRecord
from app.repositories.base import AbstractRunRepository

router = APIRouter()


class ScenarioRequest(BaseModel):
    total_budget: float
    channel_constraints: dict[str, ChannelConstraint] = {}


class ScenarioResult(BaseModel):
    total_budget: float
    optimized_allocation: dict[str, float]
    optimized_total_acquisitions: float
    prior_total_acquisitions: float
    lift_pct: float


@router.get(
    "/sessions/{session_id}/runs/{run_id}/results",
    response_model=RunResults,
    summary="Get results for a completed model run",
)
async def get_results(
    session_id: str,
    run_id: str,
    current_session: Annotated[SessionRecord, Depends(require_session)],
    run_repo: Annotated[AbstractRunRepository, Depends(get_run_repo)],
) -> RunResults:
    if current_session.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session ID mismatch.")

    run = await run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    if run.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Run does not belong to this session.")

    if run.status != RunStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run status is '{run.status.value}'. Results are only available when status is 'completed'.",
        )

    results = await run_repo.get_results(run_id)
    if results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run is marked completed but results were not found. This is unexpected.",
        )

    return results


@router.post(
    "/sessions/{session_id}/runs/{run_id}/optimise",
    response_model=ScenarioResult,
    summary="Re-run budget optimisation with a new budget or constraints (no refitting)",
)
async def optimise_scenario(
    session_id: str,
    run_id: str,
    body: ScenarioRequest,
    current_session: Annotated[SessionRecord, Depends(require_session)],
    run_repo: Annotated[AbstractRunRepository, Depends(get_run_repo)],
) -> ScenarioResult:
    if current_session.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session ID mismatch.")

    if body.total_budget <= 0:
        raise HTTPException(status_code=422, detail="total_budget must be > 0.")

    run = await run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    if run.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Run does not belong to this session.")
    if run.status != RunStatus.completed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run is not completed yet.")

    results = await run_repo.get_results(run_id)
    if results is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Results not found.")

    from app.mmm.budget_optimizer import compute_total_acquisitions, optimize_budget

    optimized_allocation = optimize_budget(
        results.response_curves,
        body.total_budget,
        body.channel_constraints or None,
    )
    optimized_acq = compute_total_acquisitions(results.response_curves, optimized_allocation)

    # Prior = same historical proportions scaled to new budget
    total_prior_weight = sum(results.prior_allocation.values())
    if total_prior_weight > 0:
        prior_at_new_budget = {
            ch: v / total_prior_weight * body.total_budget
            for ch, v in results.prior_allocation.items()
        }
    else:
        equal = body.total_budget / len(results.channels)
        prior_at_new_budget = {ch: equal for ch in results.channels}

    prior_acq = compute_total_acquisitions(results.response_curves, prior_at_new_budget)
    lift_pct = round((optimized_acq - prior_acq) / max(prior_acq, 1) * 100, 2)

    return ScenarioResult(
        total_budget=body.total_budget,
        optimized_allocation={ch: round(v, 2) for ch, v in optimized_allocation.items()},
        optimized_total_acquisitions=round(optimized_acq, 1),
        prior_total_acquisitions=round(prior_acq, 1),
        lift_pct=lift_pct,
    )
