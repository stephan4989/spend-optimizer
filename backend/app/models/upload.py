from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


def _new_uuid() -> str:
    return str(uuid.uuid4())


class DateRange(BaseModel):
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
    date_range: DateRange
    granularity: str          # 'daily' | 'weekly' | 'monthly'
    channels: list[str]
    channel_count: int
    total_spend_per_channel: dict[str, float]
    raw_csv_key: str
    column_renames: dict[str, str] = Field(default_factory=dict)
    sparse_channels: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API response shape
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    rows: int
    date_range: DateRange
    granularity: str          # 'daily' | 'weekly' | 'monthly'
    channels: list[str]
    channel_count: int
    total_spend_per_channel: dict[str, float]
    column_renames: dict[str, str] = Field(default_factory=dict)
    sparse_channels: list[str] = Field(default_factory=list)
