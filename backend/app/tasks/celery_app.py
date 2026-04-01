import logging
import os

from celery import Celery
from celery.signals import task_failure

from app.config import get_settings
from app.core.logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)
settings = get_settings()

# Use mock task when MOCK_MMM=1 (no Meridian/Linux required — for local demo)
_task_module = "app.tasks.fit_model_mock" if os.getenv("MOCK_MMM") == "1" else "app.tasks.fit_model"

celery_app = Celery(
    "spend_optimizer",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[_task_module],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # One heavy task per worker at a time — Meridian MCMC is CPU/memory intensive
    worker_prefetch_multiplier=1,
    # Do NOT re-queue on crash — Meridian fits are long-running and a crash
    # (OOM/SIGKILL) should mark the run as failed, not restart it silently.
    task_acks_late=False,
    result_expires=settings.SESSION_TTL_SECONDS,
    timezone="UTC",
    enable_utc=True,
)


@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    """
    Fired in the main worker process when a task fails — including WorkerLostError
    (SIGKILL/OOM). Since the forked worker is dead, we must mark the run as failed
    here so the UI doesn't stay stuck on 'fitting' forever.
    """
    try:
        payload = args[0] if args else kwargs.get("payload", {})
        run_id = payload.get("run_id") if isinstance(payload, dict) else None
        if not run_id:
            return

        import redis as sync_redis
        from app.models.run import RunRecord, RunStatus

        r = sync_redis.from_url(settings.REDIS_URL, decode_responses=False)
        key = f"run:{run_id}"
        raw = r.get(key)
        if raw is None:
            return
        record = RunRecord.model_validate_json(raw)
        if record.status not in (RunStatus.completed, RunStatus.failed):
            from datetime import datetime, timezone
            record.status = RunStatus.failed
            record.error_message = f"Worker crashed (OOM or SIGKILL): {type(exception).__name__}"
            record.completed_at = datetime.now(timezone.utc)
            r.set(key, record.model_dump_json(), ex=settings.SESSION_TTL_SECONDS)
            logger.error("on_task_failure: marked run %s as failed — %s", run_id, exception)
    except Exception:
        logger.exception("on_task_failure: could not mark run as failed")
