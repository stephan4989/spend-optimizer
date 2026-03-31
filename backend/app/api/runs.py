from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_run_repo, get_session_repo, get_upload_repo, require_session
from app.models.run import (
    RunCreate,
    RunCreateResponse,
    RunDetail,
    RunListResponse,
    RunRecord,
    RunStatus,
    RunSummary,
)
from app.models.session import SessionRecord
from app.repositories.base import (
    AbstractRunRepository,
    AbstractSessionRepository,
    AbstractUploadRepository,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Celery dispatch helper — isolated so tests can patch it cleanly
# ---------------------------------------------------------------------------

def _dispatch_fit_model(payload: dict) -> str:
    """Enqueue the fit_model Celery task. Returns the Celery task ID.
    Set MOCK_MMM=1 to use the mock task (no Meridian/Linux required)."""
    import os
    if os.getenv("MOCK_MMM") == "1":
        from app.tasks.fit_model_mock import fit_model
    else:
        from app.tasks.fit_model import fit_model
    result = fit_model.delay(payload)
    return result.id


# ---------------------------------------------------------------------------
# POST /sessions/{session_id}/runs
# ---------------------------------------------------------------------------

@router.post(
    "/sessions/{session_id}/runs",
    response_model=RunCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create and queue a new model run",
)
async def create_run(
    session_id: str,
    body: RunCreate,
    current_session: Annotated[SessionRecord, Depends(require_session)],
    session_repo: Annotated[AbstractSessionRepository, Depends(get_session_repo)],
    upload_repo: Annotated[AbstractUploadRepository, Depends(get_upload_repo)],
    run_repo: Annotated[AbstractRunRepository, Depends(get_run_repo)],
) -> RunCreateResponse:
    if current_session.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session ID mismatch.")

    # Validate the upload exists and belongs to this session
    upload = await upload_repo.get_record(body.upload_id)
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Upload '{body.upload_id}' not found or expired.",
        )
    if upload.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Upload does not belong to this session.",
        )

    # Resolve channel_names — default to all channels in the upload
    channel_names = body.channel_names if body.channel_names else upload.channels

    # Validate requested channels exist in the upload
    unknown = set(channel_names) - set(upload.channels)
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown channels: {sorted(unknown)}. Available: {upload.channels}",
        )

    # Create run record
    run = RunRecord(
        session_id=session_id,
        upload_id=body.upload_id,
        run_label=body.run_label,
        total_budget=body.total_budget,
        channel_constraints=body.channel_constraints,
        meridian_config=body.meridian_config,
    )
    await run_repo.create(run)
    await session_repo.add_run_id(session_id, run.run_id)

    # Build the Celery payload (JSON-safe)
    celery_payload = {
        "run_id": run.run_id,
        "session_id": session_id,
        "upload_id": body.upload_id,
        "channel_names": channel_names,
        "total_budget": body.total_budget,
        "granularity": upload.granularity,
        "channel_constraints": {
            ch: c.model_dump() for ch, c in body.channel_constraints.items()
        },
        "meridian_config": body.meridian_config.model_dump(),
    }

    task_id = _dispatch_fit_model(celery_payload)
    await run_repo.update_status(run.run_id, RunStatus.queued, celery_task_id=task_id)

    return RunCreateResponse(
        run_id=run.run_id,
        session_id=session_id,
        run_label=run.run_label,
        status=RunStatus.queued,
        created_at=run.created_at,
        celery_task_id=task_id,
    )


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/runs
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}/runs",
    response_model=RunListResponse,
    summary="List all model runs for a session",
)
async def list_runs(
    session_id: str,
    current_session: Annotated[SessionRecord, Depends(require_session)],
    run_repo: Annotated[AbstractRunRepository, Depends(get_run_repo)],
) -> RunListResponse:
    if current_session.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session ID mismatch.")

    records = await run_repo.list_for_session(session_id, current_session.run_ids)
    runs = [
        RunSummary(
            run_id=r.run_id,
            run_label=r.run_label,
            status=r.status,
            created_at=r.created_at,
            completed_at=r.completed_at,
            progress_pct=r.progress_pct,
            error_message=r.error_message,
        )
        for r in records
    ]
    return RunListResponse(runs=runs)


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/runs/{run_id}
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}/runs/{run_id}",
    response_model=RunDetail,
    summary="Get detail for a single model run",
)
async def get_run(
    session_id: str,
    run_id: str,
    current_session: Annotated[SessionRecord, Depends(require_session)],
    run_repo: Annotated[AbstractRunRepository, Depends(get_run_repo)],
) -> RunDetail:
    if current_session.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session ID mismatch.")

    run = await run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    if run.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Run does not belong to this session.")

    return RunDetail(
        run_id=run.run_id,
        run_label=run.run_label,
        status=run.status,
        created_at=run.created_at,
        completed_at=run.completed_at,
        progress_pct=run.progress_pct,
        error_message=run.error_message,
        session_id=run.session_id,
        celery_task_id=run.celery_task_id,
    )
