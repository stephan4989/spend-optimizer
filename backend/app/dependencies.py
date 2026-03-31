"""
FastAPI dependency providers.

To switch from Redis to PostgreSQL:
  1. Implement Sql* repository classes in app/repositories/sql_stubs/
  2. Replace the return values of the three provider functions below
  3. No other files need changing
"""
from __future__ import annotations

from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.models.session import SessionRecord
from app.repositories.base import (
    AbstractRunRepository,
    AbstractSessionRepository,
    AbstractUploadRepository,
)
from app.repositories.redis_run_repo import RedisRunRepository, RedisUploadRepository
from app.repositories.redis_session_repo import RedisSessionRepository


# ---------------------------------------------------------------------------
# Redis client (shared, reused across requests)
# ---------------------------------------------------------------------------

_redis_client: aioredis.Redis | None = None


async def get_redis(settings: Annotated[Settings, Depends(get_settings)]) -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    return _redis_client


# ---------------------------------------------------------------------------
# Repository providers — swap these to migrate storage backend
# ---------------------------------------------------------------------------

async def get_session_repo(
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AbstractSessionRepository:
    return RedisSessionRepository(client=redis, ttl_seconds=settings.SESSION_TTL_SECONDS)


async def get_upload_repo(
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AbstractUploadRepository:
    return RedisUploadRepository(client=redis, ttl_seconds=settings.SESSION_TTL_SECONDS)


async def get_run_repo(
    redis: Annotated[aioredis.Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AbstractRunRepository:
    return RedisRunRepository(client=redis, ttl_seconds=settings.SESSION_TTL_SECONDS)


# ---------------------------------------------------------------------------
# Session guard — resolves + validates X-Session-ID on protected routes
# ---------------------------------------------------------------------------

async def require_session(
    x_session_id: Annotated[str | None, Header()] = None,
    session_repo: AbstractSessionRepository = Depends(get_session_repo),
) -> SessionRecord:
    if x_session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Session-ID header.",
        )
    session = await session_repo.get(x_session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired.",
        )
    return session
