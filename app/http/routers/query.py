from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import runtime_settings as settings
from app.http.schemas.query import QueryRequest
from app.http.sse_utils import to_sse
from app.services.query_service import QueryService

router = APIRouter(prefix="/v1", tags=["query"])


def _db_path() -> str:
    return str(settings.CONFIG.get("sqlite_db_path") or "data/app.db")


def _svc() -> QueryService:
    return QueryService(_db_path(), settings.CONFIG)


@router.post("/query")
def query(body: QueryRequest) -> dict:
    result = _svc().run_query(
        query=body.query,
        top_k=body.top_k,
        rerank=body.rerank,
        filters=body.filters,
        namespaces=body.namespaces,
        mode="non_stream",
    )
    return {"ok": True, **result}


@router.post("/query/stream")
async def query_stream(body: QueryRequest) -> StreamingResponse:
    result = _svc().run_query(
        query=body.query,
        top_k=body.top_k,
        rerank=body.rerank,
        filters=body.filters,
        namespaces=body.namespaces,
        mode="stream",
    )

    def event_iter():
        yield to_sse("meta", {"run_id": result["run_id"], "trace_id": result["trace_id"]})
        yield to_sse("final_delta", {"text": result["answer"]})
        yield to_sse("sources", {"sources": result["sources"]})
        yield to_sse("citation_stats", {"stats": result["citation_stats"]})
        yield to_sse("done", {"cancelled": False, "text": result["answer"]})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "close",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_iter(), media_type="text/event-stream; charset=utf-8", headers=headers)


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 6
    rerank: bool = True
    filters: dict[str, Any] | None = None
    namespaces: list[str] = Field(default_factory=list)


class RerankRequest(BaseModel):
    query: str
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    top_k: int | None = None
    weights: dict[str, float] | None = None


@router.post("/retrieve")
def retrieve(body: RetrieveRequest) -> dict:
    result = _svc().retrieve(
        query=body.query,
        top_k=body.top_k,
        rerank=body.rerank,
        filters=body.filters,
        namespaces=body.namespaces,
    )
    return {"ok": True, **result}


@router.post("/rerank")
def rerank(body: RerankRequest) -> dict:
    if not body.candidates:
        return {"ok": True, "query": body.query, "count": 0, "candidates": []}
    result = _svc().rerank_candidates(
        query=body.query,
        candidates=body.candidates,
        top_k=body.top_k,
        weights=body.weights,
    )
    return {"ok": True, **result}

