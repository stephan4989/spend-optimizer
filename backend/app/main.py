from __future__ import annotations

from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify Redis is reachable
    settings = get_settings()
    client = aioredis.from_url(settings.REDIS_URL)
    await client.ping()
    yield
    # Shutdown: close connection
    await client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Spend Optimizer API",
        version="0.1.0",
        description="Performance marketing spend optimization powered by Media Mix Modelling.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()
