from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Internal record (stored in Redis)
# ---------------------------------------------------------------------------

class SessionRecord(BaseModel):
    session_id: str = Field(default_factory=_new_uuid)
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime
    ttl_seconds: int
    run_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API response shapes
# ---------------------------------------------------------------------------

class SessionCreateResponse(BaseModel):
    session_id: str
    created_at: datetime
    expires_at: datetime
    ttl_seconds: int


class SessionMeResponse(BaseModel):
    session_id: str
    created_at: datetime
    expires_at: datetime
    ttl_seconds: int
    run_count: int
