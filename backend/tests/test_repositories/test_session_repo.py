"""
Unit tests for RedisSessionRepository.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.session import SessionRecord


pytestmark = pytest.mark.asyncio


async def test_create_and_get(session_repo):
    now = datetime.now(timezone.utc)
    session = SessionRecord(
        created_at=now,
        expires_at=now + timedelta(hours=4),
        ttl_seconds=14400,
    )
    await session_repo.create(session)

    fetched = await session_repo.get(session.session_id)
    assert fetched is not None
    assert fetched.session_id == session.session_id
    assert fetched.run_ids == []


async def test_get_missing_returns_none(session_repo):
    result = await session_repo.get("nonexistent-id")
    assert result is None


async def test_add_run_id(session_repo):
    now = datetime.now(timezone.utc)
    session = SessionRecord(
        created_at=now,
        expires_at=now + timedelta(hours=4),
        ttl_seconds=14400,
    )
    await session_repo.create(session)
    await session_repo.add_run_id(session.session_id, "run-abc")
    await session_repo.add_run_id(session.session_id, "run-xyz")

    fetched = await session_repo.get(session.session_id)
    assert "run-abc" in fetched.run_ids
    assert "run-xyz" in fetched.run_ids


async def test_delete(session_repo):
    now = datetime.now(timezone.utc)
    session = SessionRecord(
        created_at=now,
        expires_at=now + timedelta(hours=4),
        ttl_seconds=14400,
    )
    await session_repo.create(session)
    await session_repo.delete(session.session_id)

    assert await session_repo.get(session.session_id) is None
