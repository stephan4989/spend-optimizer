"""
Redis implementation of AbstractSessionRepository.

Key layout:
  session:{sid}          → JSON blob of SessionRecord
  session:{sid}:run_ids  → Redis list of run_id strings

All keys share the same TTL (SESSION_TTL_SECONDS). The TTL is refreshed
on every read so active sessions don't expire mid-use.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis

from app.models.session import SessionRecord
from app.repositories.base import AbstractSessionRepository


class RedisSessionRepository(AbstractSessionRepository):

    def __init__(self, client: aioredis.Redis, ttl_seconds: int) -> None:
        self._r = client
        self._ttl = ttl_seconds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record_key(session_id: str) -> str:
        return f"session:{session_id}"

    @staticmethod
    def _run_ids_key(session_id: str) -> str:
        return f"session:{session_id}:run_ids"

    async def _refresh_ttl(self, session_id: str) -> None:
        pipe = self._r.pipeline()
        pipe.expire(self._record_key(session_id), self._ttl)
        pipe.expire(self._run_ids_key(session_id), self._ttl)
        await pipe.execute()

    # ------------------------------------------------------------------
    # AbstractSessionRepository implementation
    # ------------------------------------------------------------------

    async def create(self, session: SessionRecord) -> None:
        pipe = self._r.pipeline()
        pipe.set(
            self._record_key(session.session_id),
            session.model_dump_json(),
            ex=self._ttl,
        )
        # Initialise empty run_ids list with same TTL
        pipe.delete(self._run_ids_key(session.session_id))
        pipe.expire(self._run_ids_key(session.session_id), self._ttl)
        await pipe.execute()

    async def get(self, session_id: str) -> SessionRecord | None:
        raw = await self._r.get(self._record_key(session_id))
        if raw is None:
            return None
        await self._refresh_ttl(session_id)
        return SessionRecord.model_validate_json(raw)

    async def add_run_id(self, session_id: str, run_id: str) -> None:
        pipe = self._r.pipeline()
        pipe.rpush(self._run_ids_key(session_id), run_id)
        pipe.expire(self._run_ids_key(session_id), self._ttl)
        await pipe.execute()
        # Also update run_ids list inside the record blob for consistency
        raw = await self._r.get(self._record_key(session_id))
        if raw:
            record = SessionRecord.model_validate_json(raw)
            if run_id not in record.run_ids:
                record.run_ids.append(run_id)
            await self._r.set(
                self._record_key(session_id),
                record.model_dump_json(),
                ex=self._ttl,
            )

    async def delete(self, session_id: str) -> None:
        pipe = self._r.pipeline()
        pipe.delete(self._record_key(session_id))
        pipe.delete(self._run_ids_key(session_id))
        await pipe.execute()
