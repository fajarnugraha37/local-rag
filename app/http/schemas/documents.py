from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentDeleteResponse(BaseModel):
    ok: bool = True
    namespace: str
    doc_id: str
    deleted: bool
    hard_delete: bool = False


class DocumentsBulkDeleteRequest(BaseModel):
    namespace: str | None = None
    doc_ids: list[str] = Field(default_factory=list)
    hard_delete: bool = False
    limit: int = 500


class DocumentsBulkDeleteResponse(BaseModel):
    ok: bool = True
    matched: int
    deleted: int
    hard_delete: bool = False


class DocumentRecord(BaseModel):
    namespace: str
    doc_id: str
    source_path: str | None = None
    source_type: str | None = None
    title: str | None = None
    content_hash: str | None = None
    chunk_count: int | None = None
    size_bytes: int | None = None
    tags: list[Any] = Field(default_factory=list)
    created_at: str
    updated_at: str
    last_ingested_at: str | None = None
    deleted_at: str | None = None
    repo: str | None = None
    commit: str | None = None
