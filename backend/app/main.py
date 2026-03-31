from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.core.limiter import limiter
from app.core.logging_config import configure_logging

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    client = aioredis.from_url(settings.REDIS_URL)
    await client.ping()
    logger.info("redis_connected", url=settings.REDIS_URL)
    yield
    await client.aclose()
    logger.info("redis_disconnected")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Spend Optimizer API",
        version="0.1.0",
        description="Performance marketing spend optimization powered by Media Mix Modelling.",
        lifespan=lifespan,
    )

    # Rate limiter state + middleware
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        log = logger.bind(request_id=request_id, method=request.method, path=request.url.path)
        log.info("request_started")
        try:
            response = await call_next(request)
        except Exception as exc:
            log.exception("request_error", exc_info=exc)
            return JSONResponse(status_code=500, content={"detail": "Internal server error."})
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        log.info("request_finished", status=response.status_code, elapsed_ms=elapsed_ms)
        return response

    app.include_router(api_router)

    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()
