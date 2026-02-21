# Architecture

## Overview
Runtime is FastAPI-first with a unified launcher (`cmd/app.py`).

- `--server` mode starts `app.http.fastapi_server:main` (uvicorn).
- `--cli` mode runs Typer-based direct-to-service commands in `app/cli/main.py`.
- Legacy CLI action modules are retained behind `--cli actions ...`.

## CLI Layer
Core modules:
- `app/cli/main.py`: root Typer app and command registration.
- `app/cli/commands/*`: command domain handlers.
- `app/cli/shell.py`: interactive shell command.
- `app/cli/interactive.py`: shell dispatch helper (reuses command handlers via launcher).
- `app/cli/adapters/service_container.py`: shared service/repository wiring.
- `app/cli/idempotency.py`: idempotency helpers.
- `app/cli/pagination.py`: cursor/limit helpers.
- `app/cli/render/*`: table and event rendering.

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

## Services
- `app/services/namespace_service.py`
- `app/services/document_service.py`
- `app/services/ingestion_service.py`
- `app/services/query_service.py`
- `app/services/run_service.py`
- `app/services/feedback_service.py`
  - Query service can append an explicitly labeled general-knowledge fallback when configured.

## Extraction + Retrieval
- Docling conversion: `app/document_conversion/docling_adapter.py`
- Ingestion pipeline: `app/ingestion/pipeline.py`
- Hybrid retrieval: `app/retrieval/hybrid_search.py`
- Heuristic rerank: `app/retrieval/heuristic_reranker.py`

## Extension Points
- Add CLI commands in `app/cli/commands/*`.
- Add API routes in `app/http/routers/*`.
- Add schemas in `app/http/schemas/*`.
- Add orchestration in `app/services/*`.
- Add repository logic in `app/repositories/sqlite/*`.
