import os
from celery import Celery

from app.config import get_settings
from app.core.logging_config import configure_logging

configure_logging()

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
