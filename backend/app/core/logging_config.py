"""
Configure structlog.

Call configure_logging() once at process startup (main.py or celery_app.py).
In development (LOG_FORMAT=console) output is colourful and human-readable.
In production (default) output is newline-delimited JSON for log aggregators.
"""
from __future__ import annotations

import logging
import os

import structlog


def configure_logging() -> None:
    log_format = os.getenv("LOG_FORMAT", "json")

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if log_format == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure the stdlib root logger so uvicorn/celery logs are captured
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )
