from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_run_repo, require_session
from app.models.results import RunResults
from app.models.run import RunStatus
from app.models.session import SessionRecord
from app.repositories.base import AbstractRunRepository

router = APIRouter()


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
