"""
Integration tests for POST /api/v1/sessions/{session_id}/uploads.
"""
from __future__ import annotations

import io

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.dependencies import get_session_repo, get_upload_repo, get_run_repo


pytestmark = pytest.mark.asyncio


async def _make_client(session_repo, upload_repo, run_repo) -> AsyncClient:
    app.dependency_overrides[get_session_repo] = lambda: session_repo
    app.dependency_overrides[get_upload_repo] = lambda: upload_repo
    app.dependency_overrides[get_run_repo] = lambda: run_repo
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _make_csv(
    n_rows: int = 52,
    channels: list[str] | None = None,
    include_week: bool = True,
    include_acquisitions: bool = True,
    negative_spend: bool = False,
) -> bytes:
    if channels is None:
        channels = ["tv", "paid_search", "social"]

    dates = pd.date_range("2024-01-01", periods=n_rows, freq="W-MON")
    data: dict = {}
    if include_week:
        data["week"] = dates.strftime("%Y-%m-%d")
    for ch in channels:
        data[ch] = [(-1000 if negative_spend else 10000)] * n_rows
    if include_acquisitions:
        data["acquisitions"] = [500] * n_rows

    df = pd.DataFrame(data)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode()


async def _create_session(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/sessions")
    return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

async def test_upload_valid_csv(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        csv_bytes = _make_csv(n_rows=52, channels=["tv", "paid_search", "social"])

        resp = await client.post(
            f"/api/v1/sessions/{sid}/uploads",
            headers={"X-Session-ID": sid},
            files={"file": ("spend.csv", csv_bytes, "text/csv")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert "upload_id" in body
    assert body["rows"] == 52
    assert set(body["channels"]) == {"tv", "paid_search", "social"}
    assert body["channel_count"] == 3
    assert body["weeks_range"]["start"] == "2024-01-01"
    for ch in ["tv", "paid_search", "social"]:
        assert body["total_spend_per_channel"][ch] == 520000.0


async def test_upload_stores_raw_bytes(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        csv_bytes = _make_csv()

        resp = await client.post(
            f"/api/v1/sessions/{sid}/uploads",
            headers={"X-Session-ID": sid},
            files={"file": ("spend.csv", csv_bytes, "text/csv")},
        )

    upload_id = resp.json()["upload_id"]
    raw = await upload_repo.get_raw_csv(upload_id)
    assert raw == csv_bytes


# ---------------------------------------------------------------------------
# Validation failures — 422
# ---------------------------------------------------------------------------

async def test_upload_missing_week_column(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        csv_bytes = _make_csv(include_week=False)

        resp = await client.post(
            f"/api/v1/sessions/{sid}/uploads",
            headers={"X-Session-ID": sid},
            files={"file": ("spend.csv", csv_bytes, "text/csv")},
        )

    assert resp.status_code == 422
    assert "week" in resp.json()["detail"]


async def test_upload_missing_acquisitions_column(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        csv_bytes = _make_csv(include_acquisitions=False)

        resp = await client.post(
            f"/api/v1/sessions/{sid}/uploads",
            headers={"X-Session-ID": sid},
            files={"file": ("spend.csv", csv_bytes, "text/csv")},
        )

    assert resp.status_code == 422
    assert "acquisitions" in resp.json()["detail"]


async def test_upload_too_few_rows(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        csv_bytes = _make_csv(n_rows=8)

        resp = await client.post(
            f"/api/v1/sessions/{sid}/uploads",
            headers={"X-Session-ID": sid},
            files={"file": ("spend.csv", csv_bytes, "text/csv")},
        )

    assert resp.status_code == 422
    assert "8" in resp.json()["detail"]


async def test_upload_too_many_channels(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        channels = [f"ch_{i}" for i in range(11)]  # 11 channels — over limit
        csv_bytes = _make_csv(channels=channels)

        resp = await client.post(
            f"/api/v1/sessions/{sid}/uploads",
            headers={"X-Session-ID": sid},
            files={"file": ("spend.csv", csv_bytes, "text/csv")},
        )

    assert resp.status_code == 422
    assert "11" in resp.json()["detail"]


async def test_upload_negative_spend(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        csv_bytes = _make_csv(negative_spend=True)

        resp = await client.post(
            f"/api/v1/sessions/{sid}/uploads",
            headers={"X-Session-ID": sid},
            files={"file": ("spend.csv", csv_bytes, "text/csv")},
        )

    assert resp.status_code == 422
    assert "negative" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Auth failures
# ---------------------------------------------------------------------------

async def test_upload_no_session_header(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        csv_bytes = _make_csv()

        resp = await client.post(
            f"/api/v1/sessions/{sid}/uploads",
            files={"file": ("spend.csv", csv_bytes, "text/csv")},
        )

    assert resp.status_code == 401


async def test_upload_session_id_mismatch(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid1 = await _create_session(client)
        sid2 = await _create_session(client)
        csv_bytes = _make_csv()

        # Authenticated as sid2 but posting to sid1's path
        resp = await client.post(
            f"/api/v1/sessions/{sid1}/uploads",
            headers={"X-Session-ID": sid2},
            files={"file": ("spend.csv", csv_bytes, "text/csv")},
        )

    assert resp.status_code == 403
