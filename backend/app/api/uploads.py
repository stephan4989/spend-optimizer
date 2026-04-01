from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.config import Settings, get_settings
from app.core.csv_validator import validate_csv
from app.dependencies import get_upload_repo, require_session
from app.models.session import SessionRecord
from app.models.upload import DateRange, UploadRecord, UploadResponse
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
    file: Annotated[UploadFile, File(description="Spend data CSV (daily, weekly or monthly)")],
    current_session: Annotated[SessionRecord, Depends(require_session)],
    upload_repo: Annotated[AbstractUploadRepository, Depends(get_upload_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadResponse:
    if current_session.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session ID mismatch.",
        )

    raw_bytes = await file.read()

    if len(raw_bytes) > settings.MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(raw_bytes)} bytes). Maximum is {settings.MAX_FILE_BYTES} bytes (10 MB).",
        )

    validated = validate_csv(raw_bytes, filename=file.filename or "upload.csv")

    record = UploadRecord(
        session_id=session_id,
        filename=file.filename or "upload.csv",
        rows=validated.rows,
        date_range=DateRange(start=validated.date_start, end=validated.date_end),
        granularity=validated.granularity,
        channels=validated.channels,
        channel_count=len(validated.channels),
        total_spend_per_channel=validated.total_spend_per_channel,
        column_renames=validated.column_renames,
        sparse_channels=validated.sparse_channels,
        raw_csv_key="",
    )
    record.raw_csv_key = f"upload:{record.upload_id}:raw"
    # Store the normalised CSV (with remapped columns) so the model receives clean data
    normalised_bytes = validated.df.to_csv(index=False).encode()
    await upload_repo.save(record, normalised_bytes)

    return UploadResponse(
        upload_id=record.upload_id,
        filename=record.filename,
        rows=record.rows,
        date_range=record.date_range,
        granularity=record.granularity,
        channels=record.channels,
        channel_count=record.channel_count,
        total_spend_per_channel=record.total_spend_per_channel,
        column_renames=record.column_renames,
        sparse_channels=record.sparse_channels,
    )
