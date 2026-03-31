"""
Integration tests for POST /api/v1/sessions and GET /api/v1/sessions/me.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.dependencies import get_session_repo, get_upload_repo, get_run_repo


pytestmark = pytest.mark.asyncio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _make_client(session_repo, upload_repo, run_repo) -> AsyncClient:
    app.dependency_overrides[get_session_repo] = lambda: session_repo
    app.dependency_overrides[get_upload_repo] = lambda: upload_repo
    app.dependency_overrides[get_run_repo] = lambda: run_repo
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_create_session(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        resp = await client.post("/api/v1/sessions")

    assert resp.status_code == 201
    body = resp.json()
    assert "session_id" in body
    assert body["ttl_seconds"] > 0
    assert "expires_at" in body


async def test_get_session_me(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        create_resp = await client.post("/api/v1/sessions")
        session_id = create_resp.json()["session_id"]

        me_resp = await client.get(
            "/api/v1/sessions/me",
            headers={"X-Session-ID": session_id},
        )

    assert me_resp.status_code == 200
    body = me_resp.json()
    assert body["session_id"] == session_id
    assert body["run_count"] == 0


async def test_get_session_me_missing_header(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        resp = await client.get("/api/v1/sessions/me")

    assert resp.status_code == 401


async def test_get_session_me_invalid_session(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        resp = await client.get(
            "/api/v1/sessions/me",
            headers={"X-Session-ID": "nonexistent-uuid"},
        )

    assert resp.status_code == 404


async def test_health_check(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
