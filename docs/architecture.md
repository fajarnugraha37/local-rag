# Architecture

## Overview
The runtime is FastAPI-first with a unified launcher (`cmd/app.py`).

- `--server` mode starts `app.http.fastapi_server:main` (uvicorn).
- `--cli` mode dispatches actions from `cmd/actions.py`.

## HTTP Layer
Core modules:
- `app/http/fastapi_app.py`: app factory, lifespan, middleware, router registration.
- `app/http/fastapi_server.py`: server runner.
- `app/http/middleware/request_id.py`: request id middleware.
- `app/http/middleware/idempotency.py`: idempotency-key middleware.
- `app/http/routers/*`: route groups.
- `app/http/sse_utils.py`: SSE frame helper.

## Persistence
SQLite repositories in `app/repositories/sqlite/*`:
- namespaces, documents, ingestions, runs, idempotency, feedback.

Vector/document data:
- Chroma vectors: `data/chroma/`
- Doc registry JSON is still used by legacy-compatible doc routes.

## Services
- `app/services/namespace_service.py`
- `app/services/document_service.py`
- `app/services/ingestion_service.py`
- `app/services/query_service.py`
- `app/services/run_service.py`

## Extraction + Retrieval
- Docling conversion: `app/document_conversion/docling_adapter.py`
- Ingestion pipeline: `app/ingestion/pipeline.py`
- Hybrid retrieval: `app/retrieval/hybrid_search.py`
- Heuristic rerank: `app/retrieval/heuristic_reranker.py`

## Extension Points
- Add API routes in `app/http/routers/*`.
- Add schemas in `app/http/schemas/*`.
- Add backend orchestration in `app/services/*`.
- Add repository logic in `app/repositories/sqlite/*`.
