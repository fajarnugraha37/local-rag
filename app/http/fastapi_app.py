from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.runtime_settings import CONFIG
from app.http.middleware.idempotency import IdempotencyMiddleware
from app.http.middleware.request_id import RequestIdMiddleware
from app.http.routers.legacy import router as legacy_router
from app.http.routers.system import router as system_router
from app.repositories.sqlite.db import init_db
from app.repositories.sqlite.idempotency_repo import IdempotencyRepository


def _db_path() -> str:
    return str(CONFIG.get("sqlite_db_path") or "data/app.db")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(_db_path())
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Easy Local RAG API", version="0.1.0", lifespan=lifespan)

    idempotency_repo = IdempotencyRepository(_db_path())
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(IdempotencyMiddleware, repo=idempotency_repo)

    app.include_router(system_router)
    app.include_router(legacy_router)
    return app
