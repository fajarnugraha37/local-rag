from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config.runtime_settings import CONFIG
from app.repositories.sqlite.feedback_repo import FeedbackRepository
from app.repositories.sqlite.idempotency_repo import IdempotencyRepository
from app.services.document_service import DocumentService
from app.services.ingestion_service import IngestionService
from app.services.namespace_service import NamespaceService
from app.services.query_service import QueryService
from app.services.run_service import RunService


@dataclass(frozen=True)
class CliServices:
    db_path: str
    config: dict[str, Any]
    namespace_service: NamespaceService
    document_service: DocumentService
    ingestion_service: IngestionService
    query_service: QueryService
    run_service: RunService
    idempotency_repo: IdempotencyRepository
    feedback_repo: FeedbackRepository


def resolve_db_path(config: dict[str, Any] | None = None) -> str:
    cfg = config or CONFIG
    return str(cfg.get("sqlite_db_path") or "data/app.db")


def build_services(config: dict[str, Any] | None = None) -> CliServices:
    cfg = dict(config or CONFIG)
    db_path = resolve_db_path(cfg)

    return CliServices(
        db_path=db_path,
        config=cfg,
        namespace_service=NamespaceService(db_path),
        document_service=DocumentService(db_path),
        ingestion_service=IngestionService(db_path),
        query_service=QueryService(db_path, cfg),
        run_service=RunService(db_path),
        idempotency_repo=IdempotencyRepository(db_path),
        feedback_repo=FeedbackRepository(db_path),
    )


__all__ = ["CliServices", "build_services", "resolve_db_path"]
