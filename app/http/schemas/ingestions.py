from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IngestionSourceSpec(BaseModel):
    path: str | None = None
    repo: str | None = None
    revision: str | None = None
    recursive: bool | None = None
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    respect_gitignore: bool | None = None
    dry_run: bool | None = None
    force: bool | None = None
    embedding_model: str | None = None
    max_bytes: int | None = None
    max_rows: int | None = None
    max_pages: int | None = None
    max_slides: int | None = None
    max_sheets: int | None = None
    ingest_timeout_s: int | None = None
    chunk_max_tokens: int | None = None
    chunk_overlap_tokens: int | None = None
    ocr_enabled: bool | None = None
    parallel_workers: int | None = None


class IngestionCreateRequest(BaseModel):
    namespace: str = "default"
    source_type: str
    source_spec: IngestionSourceSpec = Field(default_factory=IngestionSourceSpec)


class IngestionCancelResponse(BaseModel):
    ok: bool = True
    ingestion_id: str
    cancel_requested: bool


class IngestionRecordResponse(BaseModel):
    ok: bool = True
    record: dict[str, Any]
