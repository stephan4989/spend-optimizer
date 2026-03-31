"""
Unit tests for RedisRunRepository and RedisUploadRepository.
"""
from __future__ import annotations

import pytest

from app.models.run import MeridianConfig, RunRecord, RunStatus
from app.models.upload import UploadRecord, WeeksRange
from app.models.results import ModelDiagnostics, ResponseCurveData, RunResults


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# UploadRepository tests
# ---------------------------------------------------------------------------

def _make_upload(session_id: str = "sess-1") -> tuple[UploadRecord, bytes]:
    record = UploadRecord(
        session_id=session_id,
        filename="test.csv",
        rows=52,
        weeks_range=WeeksRange(start="2024-01-01", end="2024-12-30"),
        channels=["tv", "search"],
        channel_count=2,
        total_spend_per_channel={"tv": 100000.0, "search": 50000.0},
        raw_csv_key="",  # filled by repo
    )
    raw = b"week,tv,search,acquisitions\n2024-01-01,1000,500,100\n"
    return record, raw


async def test_upload_save_and_get(upload_repo):
    record, raw = _make_upload()
    record.raw_csv_key = f"upload:{record.upload_id}:raw"
    await upload_repo.save(record, raw)

    fetched = await upload_repo.get_record(record.upload_id)
    assert fetched is not None
    assert fetched.filename == "test.csv"
    assert fetched.channels == ["tv", "search"]

    fetched_raw = await upload_repo.get_raw_csv(record.upload_id)
    assert fetched_raw == raw


async def test_upload_delete(upload_repo):
    record, raw = _make_upload()
    record.raw_csv_key = f"upload:{record.upload_id}:raw"
    await upload_repo.save(record, raw)
    await upload_repo.delete(record.upload_id)

    assert await upload_repo.get_record(record.upload_id) is None
    assert await upload_repo.get_raw_csv(record.upload_id) is None


# ---------------------------------------------------------------------------
# RunRepository tests
# ---------------------------------------------------------------------------

def _make_run(session_id: str = "sess-1", upload_id: str = "up-1") -> RunRecord:
    return RunRecord(
        session_id=session_id,
        upload_id=upload_id,
        run_label="Germany Q1",
        total_budget=500000.0,
        meridian_config=MeridianConfig(),
    )


async def test_run_create_and_get(run_repo):
    run = _make_run()
    await run_repo.create(run)

    fetched = await run_repo.get(run.run_id)
    assert fetched is not None
    assert fetched.run_label == "Germany Q1"
    assert fetched.status == RunStatus.queued


async def test_run_update_status(run_repo):
    run = _make_run()
    await run_repo.create(run)

    await run_repo.update_status(run.run_id, RunStatus.fitting, progress_pct=30)
    fetched = await run_repo.get(run.run_id)
    assert fetched.status == RunStatus.fitting
    assert fetched.progress_pct == 30


async def test_run_update_to_failed_sets_completed_at(run_repo):
    run = _make_run()
    await run_repo.create(run)

    await run_repo.update_status(run.run_id, RunStatus.failed, error_message="boom")
    fetched = await run_repo.get(run.run_id)
    assert fetched.status == RunStatus.failed
    assert fetched.error_message == "boom"
    assert fetched.completed_at is not None


async def test_run_save_and_get_results(run_repo):
    run = _make_run()
    await run_repo.create(run)

    results = RunResults(
        run_id=run.run_id,
        run_label="Germany Q1",
        channels=["tv", "search"],
        response_curves={
            "tv": ResponseCurveData(
                spend_points=[0, 50000, 100000],
                acquisitions=[0, 1200, 2000],
                ci_lower=[0, 1000, 1800],
                ci_upper=[0, 1400, 2200],
            ),
            "search": ResponseCurveData(
                spend_points=[0, 25000, 50000],
                acquisitions=[0, 800, 1400],
                ci_lower=[0, 700, 1200],
                ci_upper=[0, 900, 1600],
            ),
        },
        prior_allocation={"tv": 100000.0, "search": 50000.0},
        optimized_allocation={"tv": 80000.0, "search": 70000.0},
        prior_total_acquisitions=3200.0,
        optimized_total_acquisitions=3600.0,
        lift_pct=12.5,
        model_diagnostics=ModelDiagnostics(r_hat_max=1.01, ess_bulk_min=400),
    )
    await run_repo.save_results(run.run_id, results)

    fetched = await run_repo.get_results(run.run_id)
    assert fetched is not None
    assert fetched.lift_pct == 12.5
    assert "tv" in fetched.response_curves


async def test_list_for_session(run_repo):
    run1 = _make_run(session_id="sess-x")
    run2 = _make_run(session_id="sess-x")
    await run_repo.create(run1)
    await run_repo.create(run2)

    runs = await run_repo.list_for_session("sess-x", [run1.run_id, run2.run_id])
    assert len(runs) == 2
    run_ids = {r.run_id for r in runs}
    assert run1.run_id in run_ids
    assert run2.run_id in run_ids


async def test_run_delete(run_repo):
    run = _make_run()
    await run_repo.create(run)
    await run_repo.delete(run.run_id)

    assert await run_repo.get(run.run_id) is None
