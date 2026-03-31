"""
Redis implementations of AbstractUploadRepository and AbstractRunRepository.

Key layout:
  upload:{uid}:record   → JSON blob of UploadRecord
  upload:{uid}:raw      → raw CSV bytes

  run:{rid}             → JSON blob of RunRecord
  run:{rid}:results     → JSON blob of RunResults  (written on completion)

All keys share the same session TTL and are refreshed on access.
"""
from __future__ import annotations

from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.models.results import RunResults
from app.models.run import RunRecord, RunStatus
from app.models.upload import UploadRecord
from app.repositories.base import AbstractRunRepository, AbstractUploadRepository


# ---------------------------------------------------------------------------
# Upload repository
# ---------------------------------------------------------------------------

class RedisUploadRepository(AbstractUploadRepository):

    def __init__(self, client: aioredis.Redis, ttl_seconds: int) -> None:
        self._r = client
        self._ttl = ttl_seconds

    @staticmethod
    def _record_key(upload_id: str) -> str:
        return f"upload:{upload_id}:record"

    @staticmethod
    def _raw_key(upload_id: str) -> str:
        return f"upload:{upload_id}:raw"

    async def save(self, record: UploadRecord, raw_csv: bytes) -> None:
        pipe = self._r.pipeline()
        pipe.set(self._record_key(record.upload_id), record.model_dump_json(), ex=self._ttl)
        pipe.set(self._raw_key(record.upload_id), raw_csv, ex=self._ttl)
        await pipe.execute()

    async def get_record(self, upload_id: str) -> UploadRecord | None:
        raw = await self._r.get(self._record_key(upload_id))
        if raw is None:
            return None
        return UploadRecord.model_validate_json(raw)

    async def get_raw_csv(self, upload_id: str) -> bytes | None:
        return await self._r.get(self._raw_key(upload_id))

    async def delete(self, upload_id: str) -> None:
        pipe = self._r.pipeline()
        pipe.delete(self._record_key(upload_id))
        pipe.delete(self._raw_key(upload_id))
        await pipe.execute()


# ---------------------------------------------------------------------------
# Run repository
# ---------------------------------------------------------------------------

class RedisRunRepository(AbstractRunRepository):

    def __init__(self, client: aioredis.Redis, ttl_seconds: int) -> None:
        self._r = client
        self._ttl = ttl_seconds

    @staticmethod
    def _record_key(run_id: str) -> str:
        return f"run:{run_id}"

    @staticmethod
    def _results_key(run_id: str) -> str:
        return f"run:{run_id}:results"

    async def create(self, run: RunRecord) -> None:
        await self._r.set(
            self._record_key(run.run_id),
            run.model_dump_json(),
            ex=self._ttl,
        )

    async def get(self, run_id: str) -> RunRecord | None:
        raw = await self._r.get(self._record_key(run_id))
        if raw is None:
            return None
        return RunRecord.model_validate_json(raw)

    async def list_for_session(self, session_id: str, run_ids: list[str]) -> list[RunRecord]:
        if not run_ids:
            return []
        pipe = self._r.pipeline()
        for rid in run_ids:
            pipe.get(self._record_key(rid))
        raws = await pipe.execute()
        records = []
        for raw in raws:
            if raw is not None:
                records.append(RunRecord.model_validate_json(raw))
        return records

    async def update_status(
        self,
        run_id: str,
        status: RunStatus,
        progress_pct: int | None = None,
        error_message: str | None = None,
        celery_task_id: str | None = None,
    ) -> None:
        raw = await self._r.get(self._record_key(run_id))
        if raw is None:
            return
        record = RunRecord.model_validate_json(raw)
        record.status = status
        if progress_pct is not None:
            record.progress_pct = progress_pct
        if error_message is not None:
            record.error_message = error_message
        if celery_task_id is not None:
            record.celery_task_id = celery_task_id
        if status in (RunStatus.completed, RunStatus.failed):
            record.completed_at = datetime.now(timezone.utc)
        await self._r.set(
            self._record_key(run_id),
            record.model_dump_json(),
            ex=self._ttl,
        )

    async def save_results(self, run_id: str, results: RunResults) -> None:
        await self._r.set(
            self._results_key(run_id),
            results.model_dump_json(),
            ex=self._ttl,
        )

    async def get_results(self, run_id: str) -> RunResults | None:
        raw = await self._r.get(self._results_key(run_id))
        if raw is None:
            return None
        return RunResults.model_validate_json(raw)

    async def delete(self, run_id: str) -> None:
        pipe = self._r.pipeline()
        pipe.delete(self._record_key(run_id))
        pipe.delete(self._results_key(run_id))
        await pipe.execute()
