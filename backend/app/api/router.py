from fastapi import APIRouter

from app.api import results, runs, sessions, uploads

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(sessions.router, tags=["sessions"])
api_router.include_router(uploads.router, tags=["uploads"])
api_router.include_router(runs.router, tags=["runs"])
api_router.include_router(results.router, tags=["results"])
