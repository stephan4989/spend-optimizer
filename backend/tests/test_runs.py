"""
Integration tests for:
  POST   /api/v1/sessions/{sid}/runs
  GET    /api/v1/sessions/{sid}/runs
  GET    /api/v1/sessions/{sid}/runs/{rid}
  GET    /api/v1/sessions/{sid}/runs/{rid}/results
"""
from __future__ import annotations

import io
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.dependencies import get_session_repo, get_upload_repo, get_run_repo
from app.models.results import ModelDiagnostics, ResponseCurveData, RunResults
from app.models.run import RunStatus

pytestmark = pytest.mark.asyncio

FAKE_TASK_ID = "celery-task-fake-uuid"


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

async def _make_client(session_repo, upload_repo, run_repo) -> AsyncClient:
    app.dependency_overrides[get_session_repo] = lambda: session_repo
    app.dependency_overrides[get_upload_repo] = lambda: upload_repo
    app.dependency_overrides[get_run_repo] = lambda: run_repo
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _make_csv(n_rows: int = 52, channels: list[str] | None = None) -> bytes:
    channels = channels or ["tv", "paid_search", "social"]
    dates = pd.date_range("2024-01-01", periods=n_rows, freq="W-MON")
    data = {"week": dates.strftime("%Y-%m-%d").tolist()}
    for ch in channels:
        data[ch] = [10_000.0] * n_rows
    data["acquisitions"] = [500.0] * n_rows
    buf = io.StringIO()
    pd.DataFrame(data).to_csv(buf, index=False)
    return buf.getvalue().encode()


async def _create_session(client: AsyncClient) -> str:
    r = await client.post("/api/v1/sessions")
    return r.json()["session_id"]


async def _upload_csv(client: AsyncClient, sid: str, channels: list[str] | None = None) -> str:
    csv_bytes = _make_csv(channels=channels)
    r = await client.post(
        f"/api/v1/sessions/{sid}/uploads",
        headers={"X-Session-ID": sid},
        files={"file": ("spend.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()["upload_id"]


def _make_run_body(upload_id: str, **kwargs) -> dict:
    return {
        "upload_id": upload_id,
        "run_label": "Germany Q1 2024",
        "total_budget": 300_000.0,
        **kwargs,
    }


def _make_results(run_id: str) -> RunResults:
    curve = ResponseCurveData(
        spend_points=[0.0, 50_000.0, 100_000.0],
        acquisitions=[0.0, 1_200.0, 2_000.0],
        ci_lower=[0.0, 1_000.0, 1_800.0],
        ci_upper=[0.0, 1_400.0, 2_200.0],
    )
    return RunResults(
        run_id=run_id,
        run_label="Germany Q1 2024",
        channels=["tv", "paid_search"],
        response_curves={"tv": curve, "paid_search": curve},
        prior_allocation={"tv": 150_000.0, "paid_search": 150_000.0},
        optimized_allocation={"tv": 180_000.0, "paid_search": 120_000.0},
        prior_total_acquisitions=4_800.0,
        optimized_total_acquisitions=5_200.0,
        lift_pct=8.33,
        model_diagnostics=ModelDiagnostics(r_hat_max=1.01, ess_bulk_min=400),
    )


# ---------------------------------------------------------------------------
# POST /runs — happy path
# ---------------------------------------------------------------------------

async def test_create_run_queues_celery_task(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid)

        with patch("app.api.runs._dispatch_fit_model", return_value=FAKE_TASK_ID) as mock_dispatch:
            resp = await client.post(
                f"/api/v1/sessions/{sid}/runs",
                headers={"X-Session-ID": sid},
                json=_make_run_body(uid),
            )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["celery_task_id"] == FAKE_TASK_ID
    assert "run_id" in body
    mock_dispatch.assert_called_once()


async def test_create_run_persists_to_redis(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid)

        with patch("app.api.runs._dispatch_fit_model", return_value=FAKE_TASK_ID):
            resp = await client.post(
                f"/api/v1/sessions/{sid}/runs",
                headers={"X-Session-ID": sid},
                json=_make_run_body(uid),
            )

    run_id = resp.json()["run_id"]
    run = await run_repo.get(run_id)
    assert run is not None
    assert run.run_label == "Germany Q1 2024"
    assert run.total_budget == 300_000.0


async def test_create_run_adds_to_session(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid)

        with patch("app.api.runs._dispatch_fit_model", return_value=FAKE_TASK_ID):
            resp = await client.post(
                f"/api/v1/sessions/{sid}/runs",
                headers={"X-Session-ID": sid},
                json=_make_run_body(uid),
            )

    run_id = resp.json()["run_id"]
    session = await session_repo.get(sid)
    assert run_id in session.run_ids


async def test_create_run_with_channel_subset(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid, channels=["tv", "paid_search", "social"])

        with patch("app.api.runs._dispatch_fit_model", return_value=FAKE_TASK_ID) as mock_dispatch:
            resp = await client.post(
                f"/api/v1/sessions/{sid}/runs",
                headers={"X-Session-ID": sid},
                json=_make_run_body(uid, channel_names=["tv", "paid_search"]),
            )

    assert resp.status_code == 202
    payload_sent = mock_dispatch.call_args[0][0]
    assert payload_sent["channel_names"] == ["tv", "paid_search"]


async def test_create_run_with_constraints(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid)

        body = _make_run_body(uid, channel_constraints={
            "tv": {"min_fraction": 0.1, "max_fraction": 0.5}
        })
        with patch("app.api.runs._dispatch_fit_model", return_value=FAKE_TASK_ID):
            resp = await client.post(
                f"/api/v1/sessions/{sid}/runs",
                headers={"X-Session-ID": sid},
                json=body,
            )

    assert resp.status_code == 202


# ---------------------------------------------------------------------------
# POST /runs — validation failures
# ---------------------------------------------------------------------------

async def test_create_run_unknown_upload(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)

        resp = await client.post(
            f"/api/v1/sessions/{sid}/runs",
            headers={"X-Session-ID": sid},
            json=_make_run_body("nonexistent-upload-id"),
        )

    assert resp.status_code == 404


async def test_create_run_unknown_channels(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid, channels=["tv", "search"])

        resp = await client.post(
            f"/api/v1/sessions/{sid}/runs",
            headers={"X-Session-ID": sid},
            json=_make_run_body(uid, channel_names=["tv", "search", "nonexistent"]),
        )

    assert resp.status_code == 422
    assert "nonexistent" in resp.json()["detail"]


async def test_create_run_cross_session_upload_rejected(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid1 = await _create_session(client)
        sid2 = await _create_session(client)
        uid = await _upload_csv(client, sid1)  # upload belongs to sid1

        resp = await client.post(
            f"/api/v1/sessions/{sid2}/runs",
            headers={"X-Session-ID": sid2},
            json=_make_run_body(uid),
        )

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /runs — list
# ---------------------------------------------------------------------------

async def test_list_runs_empty(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)

        resp = await client.get(
            f"/api/v1/sessions/{sid}/runs",
            headers={"X-Session-ID": sid},
        )

    assert resp.status_code == 200
    assert resp.json()["runs"] == []


async def test_list_runs_contains_created_run(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid)

        with patch("app.api.runs._dispatch_fit_model", return_value=FAKE_TASK_ID):
            create_resp = await client.post(
                f"/api/v1/sessions/{sid}/runs",
                headers={"X-Session-ID": sid},
                json=_make_run_body(uid),
            )
        run_id = create_resp.json()["run_id"]

        list_resp = await client.get(
            f"/api/v1/sessions/{sid}/runs",
            headers={"X-Session-ID": sid},
        )

    runs = list_resp.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["run_id"] == run_id
    assert runs[0]["status"] == "queued"


async def test_list_runs_multiple(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid)

        with patch("app.api.runs._dispatch_fit_model", return_value=FAKE_TASK_ID):
            for label in ["UK", "DE", "FR"]:
                await client.post(
                    f"/api/v1/sessions/{sid}/runs",
                    headers={"X-Session-ID": sid},
                    json=_make_run_body(uid, run_label=label),
                )

        list_resp = await client.get(
            f"/api/v1/sessions/{sid}/runs",
            headers={"X-Session-ID": sid},
        )

    assert len(list_resp.json()["runs"]) == 3


# ---------------------------------------------------------------------------
# GET /runs/{run_id} — single run detail
# ---------------------------------------------------------------------------

async def test_get_run_detail(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid)

        with patch("app.api.runs._dispatch_fit_model", return_value=FAKE_TASK_ID):
            create_resp = await client.post(
                f"/api/v1/sessions/{sid}/runs",
                headers={"X-Session-ID": sid},
                json=_make_run_body(uid),
            )
        run_id = create_resp.json()["run_id"]

        detail_resp = await client.get(
            f"/api/v1/sessions/{sid}/runs/{run_id}",
            headers={"X-Session-ID": sid},
        )

    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["run_id"] == run_id
    assert body["run_label"] == "Germany Q1 2024"
    assert body["celery_task_id"] == FAKE_TASK_ID


async def test_get_run_not_found(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)

        resp = await client.get(
            f"/api/v1/sessions/{sid}/runs/nonexistent-run",
            headers={"X-Session-ID": sid},
        )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /runs/{run_id}/results
# ---------------------------------------------------------------------------

async def test_get_results_when_completed(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid)

        with patch("app.api.runs._dispatch_fit_model", return_value=FAKE_TASK_ID):
            create_resp = await client.post(
                f"/api/v1/sessions/{sid}/runs",
                headers={"X-Session-ID": sid},
                json=_make_run_body(uid),
            )
        run_id = create_resp.json()["run_id"]

        # Manually mark as completed and store results (simulates Celery worker finishing)
        await run_repo.update_status(run_id, RunStatus.completed, progress_pct=100)
        results = _make_results(run_id)
        await run_repo.save_results(run_id, results)

        resp = await client.get(
            f"/api/v1/sessions/{sid}/runs/{run_id}/results",
            headers={"X-Session-ID": sid},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run_id
    assert body["lift_pct"] == 8.33
    assert "tv" in body["response_curves"]
    assert "prior_allocation" in body
    assert "optimized_allocation" in body


async def test_get_results_while_fitting_returns_409(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)
        uid = await _upload_csv(client, sid)

        with patch("app.api.runs._dispatch_fit_model", return_value=FAKE_TASK_ID):
            create_resp = await client.post(
                f"/api/v1/sessions/{sid}/runs",
                headers={"X-Session-ID": sid},
                json=_make_run_body(uid),
            )
        run_id = create_resp.json()["run_id"]

        resp = await client.get(
            f"/api/v1/sessions/{sid}/runs/{run_id}/results",
            headers={"X-Session-ID": sid},
        )

    assert resp.status_code == 409
    assert "queued" in resp.json()["detail"]


async def test_get_results_run_not_found(session_repo, upload_repo, run_repo):
    async with await _make_client(session_repo, upload_repo, run_repo) as client:
        sid = await _create_session(client)

        resp = await client.get(
            f"/api/v1/sessions/{sid}/runs/ghost-run/results",
            headers={"X-Session-ID": sid},
        )

    assert resp.status_code == 404
