"""
Abstract repository interfaces.

All storage logic is hidden behind these ABCs. The current implementation
uses Redis. To migrate to PostgreSQL (or any other store), create concrete
classes that satisfy these interfaces and update app/dependencies.py —
no changes needed in the API or service layers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.results import RunResults
from app.models.run import RunRecord, RunStatus
from app.models.session import SessionRecord
from app.models.upload import UploadRecord


class AbstractSessionRepository(ABC):

    @abstractmethod
    async def create(self, session: SessionRecord) -> None:
        """Persist a new session record."""
        ...

    @abstractmethod
    async def get(self, session_id: str) -> SessionRecord | None:
        """Return the session or None if not found / expired."""
        ...

    @abstractmethod
    async def add_run_id(self, session_id: str, run_id: str) -> None:
        """Append a run_id to the session's run list."""
        ...

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Remove a session and all associated keys."""
        ...


class AbstractUploadRepository(ABC):

    @abstractmethod
    async def save(self, record: UploadRecord, raw_csv: bytes) -> None:
        """Persist the upload metadata record and the raw CSV bytes."""
        ...

    @abstractmethod
    async def get_record(self, upload_id: str) -> UploadRecord | None:
        """Return upload metadata or None if not found."""
        ...

    @abstractmethod
    async def get_raw_csv(self, upload_id: str) -> bytes | None:
        """Return raw CSV bytes or None if not found."""
        ...

    @abstractmethod
    async def delete(self, upload_id: str) -> None:
        """Remove upload record and raw bytes."""
        ...


class AbstractRunRepository(ABC):

    @abstractmethod
    async def create(self, run: RunRecord) -> None:
        """Persist a new run record."""
        ...

    @abstractmethod
    async def get(self, run_id: str) -> RunRecord | None:
        """Return the run record or None if not found."""
        ...

    @abstractmethod
    async def list_for_session(self, session_id: str, run_ids: list[str]) -> list[RunRecord]:
        """Return all runs for the given session, in creation order."""
        ...

    @abstractmethod
    async def update_status(
        self,
        run_id: str,
        status: RunStatus,
        progress_pct: int | None = None,
        error_message: str | None = None,
        celery_task_id: str | None = None,
    ) -> None:
        """Patch the mutable status fields on a run record."""
        ...

    @abstractmethod
    async def save_results(self, run_id: str, results: RunResults) -> None:
        """Persist final results after model completion."""
        ...

    @abstractmethod
    async def get_results(self, run_id: str) -> RunResults | None:
        """Return results or None if not yet available."""
        ...

    @abstractmethod
    async def delete(self, run_id: str) -> None:
        """Remove the run record and its results."""
        ...
