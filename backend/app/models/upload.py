from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


def _new_uuid() -> str:
    return str(uuid.uuid4())


class WeeksRange(BaseModel):
    start: str  # ISO date "YYYY-MM-DD"
    end: str


# ---------------------------------------------------------------------------
# Internal record (stored in Redis)
# ---------------------------------------------------------------------------

class UploadRecord(BaseModel):
    upload_id: str = Field(default_factory=_new_uuid)
    session_id: str
    filename: str
    rows: int
    weeks_range: WeeksRange
    channels: list[str]
    channel_count: int
    total_spend_per_channel: dict[str, float]
    # Redis key where raw CSV bytes live
    raw_csv_key: str


# ---------------------------------------------------------------------------
# API response shape
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    rows: int
    weeks_range: WeeksRange
    channels: list[str]
    channel_count: int
    total_spend_per_channel: dict[str, float]
