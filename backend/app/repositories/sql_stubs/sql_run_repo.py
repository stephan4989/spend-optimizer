"""
PostgreSQL implementation stubs for AbstractUploadRepository and AbstractRunRepository.

See sql_session_repo.py for activation instructions.
"""
from __future__ import annotations

from app.models.results import RunResults
from app.models.run import RunRecord, RunStatus
from app.models.upload import UploadRecord
from app.repositories.base import AbstractRunRepository, AbstractUploadRepository


class SqlUploadRepository(AbstractUploadRepository):

    def __init__(self, db_session) -> None:
        self._db = db_session

    async def save(self, record: UploadRecord, raw_csv: bytes) -> None:
        raise NotImplementedError("SQL implementation pending")

    async def get_record(self, upload_id: str) -> UploadRecord | None:
        raise NotImplementedError("SQL implementation pending")

    async def get_raw_csv(self, upload_id: str) -> bytes | None:
        raise NotImplementedError("SQL implementation pending")

    async def delete(self, upload_id: str) -> None:
        raise NotImplementedError("SQL implementation pending")


class SqlRunRepository(AbstractRunRepository):

    def __init__(self, db_session) -> None:
        self._db = db_session

    async def create(self, run: RunRecord) -> None:
        raise NotImplementedError("SQL implementation pending")

    async def get(self, run_id: str) -> RunRecord | None:
        raise NotImplementedError("SQL implementation pending")

    async def list_for_session(self, session_id: str, run_ids: list[str]) -> list[RunRecord]:
        raise NotImplementedError("SQL implementation pending")

    async def update_status(
        self,
        run_id: str,
        status: RunStatus,
        progress_pct: int | None = None,
        error_message: str | None = None,
        celery_task_id: str | None = None,
    ) -> None:
        raise NotImplementedError("SQL implementation pending")

    async def save_results(self, run_id: str, results: RunResults) -> None:
        raise NotImplementedError("SQL implementation pending")

    async def get_results(self, run_id: str) -> RunResults | None:
        raise NotImplementedError("SQL implementation pending")

    async def delete(self, run_id: str) -> None:
        raise NotImplementedError("SQL implementation pending")
