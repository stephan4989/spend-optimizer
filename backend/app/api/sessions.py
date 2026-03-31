from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.config import Settings, get_settings
from app.dependencies import get_session_repo, require_session
from app.models.session import SessionCreateResponse, SessionMeResponse, SessionRecord
from app.repositories.base import AbstractSessionRepository

router = APIRouter()


@router.post(
    "/sessions",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new anonymous session",
)
async def create_session(
    settings: Annotated[Settings, Depends(get_settings)],
    session_repo: Annotated[AbstractSessionRepository, Depends(get_session_repo)],
) -> SessionCreateResponse:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.SESSION_TTL_SECONDS)
    session = SessionRecord(
        created_at=now,
        expires_at=expires_at,
        ttl_seconds=settings.SESSION_TTL_SECONDS,
    )
    await session_repo.create(session)
    return SessionCreateResponse(
        session_id=session.session_id,
        created_at=session.created_at,
        expires_at=session.expires_at,
        ttl_seconds=session.ttl_seconds,
    )


@router.get(
    "/sessions/me",
    response_model=SessionMeResponse,
    summary="Get metadata for the current session",
)
async def get_session_me(
    current_session: Annotated[SessionRecord, Depends(require_session)],
) -> SessionMeResponse:
    return SessionMeResponse(
        session_id=current_session.session_id,
        created_at=current_session.created_at,
        expires_at=current_session.expires_at,
        ttl_seconds=current_session.ttl_seconds,
        run_count=len(current_session.run_ids),
    )
