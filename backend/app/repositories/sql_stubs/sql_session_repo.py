"""
PostgreSQL implementation stub for AbstractSessionRepository.

To activate:
1. Add sqlalchemy + asyncpg to requirements.txt
2. Create the sessions table (migration via alembic)
3. Implement all methods below
4. Update app/dependencies.py to return SqlSessionRepository instead of RedisSessionRepository
"""
from __future__ import annotations

from app.models.session import SessionRecord
from app.repositories.base import AbstractSessionRepository


class SqlSessionRepository(AbstractSessionRepository):

    def __init__(self, db_session) -> None:
        # db_session: sqlalchemy AsyncSession injected via Depends()
        self._db = db_session

    async def create(self, session: SessionRecord) -> None:
        raise NotImplementedError("SQL implementation pending")

    async def get(self, session_id: str) -> SessionRecord | None:
        raise NotImplementedError("SQL implementation pending")

    async def add_run_id(self, session_id: str, run_id: str) -> None:
        raise NotImplementedError("SQL implementation pending")

    async def delete(self, session_id: str) -> None:
        raise NotImplementedError("SQL implementation pending")
