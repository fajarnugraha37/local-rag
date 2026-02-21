from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IngestionCreateRequest(BaseModel):
    namespace: str = "default"
    source_type: str
    source_spec: dict[str, Any] = Field(default_factory=dict)


class IngestionCancelResponse(BaseModel):
    ok: bool = True
    ingestion_id: str
    cancel_requested: bool


class IngestionRecordResponse(BaseModel):
    ok: bool = True
    record: dict[str, Any]
