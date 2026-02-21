from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NamespaceCreateRequest(BaseModel):
    namespace: str
    defaults: dict[str, Any] = Field(default_factory=dict)


class NamespaceDeleteResponse(BaseModel):
    ok: bool = True
    namespace: str
    deleted: bool
    not_found: bool = False
    dry_run: bool = False
    would_delete: bool | None = None
