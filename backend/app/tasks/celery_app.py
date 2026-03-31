from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "spend_optimizer",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.fit_model"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # One heavy task per worker at a time — Meridian MCMC is CPU/memory intensive
    worker_prefetch_multiplier=1,
    # Re-queue task if worker crashes mid-run
    task_acks_late=True,
    result_expires=settings.SESSION_TTL_SECONDS,
    timezone="UTC",
    enable_utc=True,
)
