from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str
    top_k: int = 6
    rerank: bool = True
    filters: dict[str, Any] | None = None
    namespaces: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    ok: bool = True
    run_id: str
    trace_id: str
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    citation_stats: dict[str, Any] = Field(default_factory=dict)
    count: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
