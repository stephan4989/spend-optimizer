from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.config import Settings, get_settings
from app.core.csv_validator import validate_csv
from app.dependencies import get_upload_repo, require_session
from app.models.session import SessionRecord
from app.models.upload import UploadRecord, UploadResponse, WeeksRange
from app.repositories.base import AbstractUploadRepository

router = APIRouter()


@router.post(
    "/sessions/{session_id}/uploads",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a CSV spend file for a session",
)
async def upload_csv(
    session_id: str,
    file: Annotated[UploadFile, File(description="Weekly spend CSV file")],
    current_session: Annotated[SessionRecord, Depends(require_session)],
    upload_repo: Annotated[AbstractUploadRepository, Depends(get_upload_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadResponse:
    # Guard: session_id in path must match the authenticated session
    if current_session.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session ID mismatch.",
        )

    # Read file bytes
    raw_bytes = await file.read()

    # Enforce file size limit
    if len(raw_bytes) > settings.MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(raw_bytes)} bytes). Maximum is {settings.MAX_FILE_BYTES} bytes (10 MB).",
        )

    # Validate CSV content
    validated = validate_csv(raw_bytes, filename=file.filename or "upload.csv")

    # Build and persist the upload record
    record = UploadRecord(
        session_id=session_id,
        filename=file.filename or "upload.csv",
        rows=validated.rows,
        weeks_range=WeeksRange(start=validated.week_start, end=validated.week_end),
        channels=validated.channels,
        channel_count=len(validated.channels),
        total_spend_per_channel=validated.total_spend_per_channel,
        raw_csv_key="",  # set below after upload_id is known
    )
    record.raw_csv_key = f"upload:{record.upload_id}:raw"
    await upload_repo.save(record, raw_bytes)

    return UploadResponse(
        upload_id=record.upload_id,
        filename=record.filename,
        rows=record.rows,
        weeks_range=record.weeks_range,
        channels=record.channels,
        channel_count=record.channel_count,
        total_spend_per_channel=record.total_spend_per_channel,
    )
