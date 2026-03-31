"""
Shared pytest fixtures for all tests.

Uses fakeredis so tests run without a live Redis instance.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
import fakeredis.aioredis as fake_aioredis

from app.config import Settings
from app.repositories.redis_session_repo import RedisSessionRepository
from app.repositories.redis_run_repo import RedisRunRepository, RedisUploadRepository


TEST_TTL = 3600  # 1 hour — long enough that tests never hit expiry


@pytest.fixture
def settings() -> Settings:
    return Settings(
        REDIS_URL="redis://localhost:6379/0",  # won't be used (fakeredis overrides)
        SESSION_TTL_SECONDS=TEST_TTL,
        MAX_FILE_BYTES=10 * 1024 * 1024,
        CORS_ORIGINS="http://localhost:5173",
    )


@pytest_asyncio.fixture
async def redis_client():
    """In-memory Redis substitute — isolated per test."""
    client = fake_aioredis.FakeRedis(decode_responses=False)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def session_repo(redis_client):
    return RedisSessionRepository(client=redis_client, ttl_seconds=TEST_TTL)


@pytest_asyncio.fixture
async def upload_repo(redis_client):
    return RedisUploadRepository(client=redis_client, ttl_seconds=TEST_TTL)


@pytest_asyncio.fixture
async def run_repo(redis_client):
    return RedisRunRepository(client=redis_client, ttl_seconds=TEST_TTL)
