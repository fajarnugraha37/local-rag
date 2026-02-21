# Spec 012: FastAPI Server Migration

## Current State (Repo Scan)

### Server Framework + Entrypoints
- Current server is `http.server` with `BaseHTTPRequestHandler` and `ThreadingHTTPServer`.
- Server handler: `app/http/server.py` (`create_streaming_handler`, `StreamingHandler`).
- Server compatibility entrypoint: `app/chat/streaming_server.py` (builds deps and exposes `StreamingHandler`).
- Launcher: `cmd/app.py` with `cmd/server/entrypoint.py` calling `cmd/actions.py` action `server` -> `app.chat.streaming_server:main`.

### Existing Endpoints and Behavior (Must Retain)
- `GET /health` -> JSON `{ok: true}`.
- `GET /actions` and `GET /action` -> list action specs + `http_supported_actions`.
- `POST /actions/run` and `POST /action/run` -> execute whitelisted CLI actions, returns `result` object.
- `GET /docs` -> list documents from `DocRegistryStore` with `limit` + `cursor` + optional `namespace`.
- `DELETE /docs/{doc_id}` -> delete vectors + registry records; supports `namespace` or `all_namespaces=true`.
- `GET /chat/stream` (SSE) -> streaming chat with continuation and citations.
- `POST /ingest/chunks` -> embed/upsert provided chunks.
- `POST /ingest/text` -> simple sentence chunking, embed/upsert.
- `POST /ingest/files` and `POST /ingestion/files` -> ingest file paths (recursive + include/exclude).
- `POST /ingest/folder` -> folder scan + ingestion, optional SSE progress stream.
- `POST /ingest/upload` and `POST /ingestion/upload` -> multipart uploads, ingest bytes.
- `POST /vectors/delete-doc` -> delete vectors by doc_id.
- `POST /retrieval/query` -> raw retrieval results + generated answer + sources.

### SSE Behavior (Current)
- `GET /chat/stream` emits event stream using `app/common/stream_protocol.py`.
- Emits events: `meta`, `final_delta`, `part_done`, `done`, `error`, plus `sources` and `citation_stats` right before `done`.
- `POST /ingest/folder` supports SSE events: `scan_started`, `file_found`, `file_selected`, `file_ingested`, `file_skipped`, `file_failed`, `scan_done`, `done`.

### RAG Modules Used by Server
- Ingestion: `app/ingestion/pipeline.py`, `app/ingestion/folder_ingest_service.py`, `app/ingestion/vector_ingest_service.py`.
- Extraction/Docling: `app/ingestion/extractors/*`, `app/document_conversion/docling_adapter.py`.
- Chunking: `app/ingestion/chunking.py`, `app/context/token_chunking.py`.
- Retrieval: `app/retrieval/hybrid_search.py`, `app/retrieval/heuristic_reranker.py`.
- Storage: `app/storage/chroma_vector_store.py`.
- Namespaces: `app/common/namespaces.py`.
- Citations: `app/chat/citation_prompting.py`, `app/chat/citation_formatter.py`, `app/retrieval/provenance.py`.
- Streaming: `app/chat/streaming_llm_client.py`, `app/common/stream_protocol.py`.

### Config + Logging + Error Handling
- Config loader: `app/config/runtime_settings.py` (loads `config.yaml` + `.env`).
- Logging: `app/logging/config.py`.
- Error handling: per-handler `try/except`, JSON error envelopes (`ok: false`).

### Persistence
- Vector DB: Chroma persistent store (`data/chroma`) via `app/storage/chroma_vector_store.py`.
- Doc registry: JSON file `data/doc_registry.json` via `app/ingestion/doc_registry_store.py`.
- Folder ingest state: JSON file `data/ingest_state.json` via `app/ingestion/file_state_store.py`.
- No SQLite or relational store currently.

### Tests + Docs
- Server tests: `tests/test_ingestion_server_routes.py`, `tests/test_server_citation_sse.py`.
- Stream tests: `tests/test_streaming_continuation.py`.
- Postman collection: `tests/postman/easy-local-rag-server.postman_collection.json`.
- Docs: `docs/server.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/development.md`.

### What Will Be Removed/Replaced
- Remove legacy HTTP server and handlers:
  - `app/http/server.py`
  - `app/http/handlers/*`
  - `app/http/request_parsing.py`
  - `app/http/sse.py`
  - `app/chat/streaming_server.py` (server entrypoint)
- Replace with FastAPI ASGI app, routers, schemas, middleware, and repositories.

## Target Design

### FastAPI App Structure (New)
- `app/http/fastapi_app.py`: `create_app()` + lifespan hooks + middleware.
- `app/http/routers/*`: modular routers for system, namespaces, ingestions, documents, query, runs, feedback, legacy endpoints.
- `app/http/schemas/*`: Pydantic request/response models.
- `app/http/middleware/*`: request id + idempotency.
- `app/http/sse/*`: SSE helpers.
- `app/services/*`: orchestration with existing ingestion/retrieval services.
- `app/repositories/sqlite/*`: persistent stores for docs, jobs, runs, idempotency, feedback, namespaces.
- `app/health/checks.py`: readiness probes.

### Endpoint Mapping
- Existing endpoints retained with same paths and payloads, implemented via FastAPI routes.
- New v1 endpoints added under `/v1/*` as specified.
- `/health` remains for backward compatibility; add `/healthz` and `/readyz`.

### Data Model Overview (SQLite)
Use stdlib `sqlite3` with a small repository layer:
- `namespaces`: `namespace`, `created_at`, `deleted_at`, defaults (embedding model, chunking config).
- `documents`: `namespace`, `doc_id`, `source_path`, `source_type`, `title`, `content_hash`, `chunk_count`, `size_bytes`, `tags`, `created_at`, `updated_at`, `last_ingested_at`, `deleted_at`, `repo`, `commit`.
- `ingestions`: `ingestion_id`, `namespace`, `source_type`, `source_spec`, `status`, `created_at`, `started_at`, `finished_at`, `counters`, `last_error`, `cancel_requested`.
- `ingestion_events`: `ingestion_id`, `ts`, `event`, `payload` (progress stream + audit).
- `runs`: `run_id`, `trace_id`, `query`, `mode`, `inputs`, `answer`, `citations`, `status`, `created_at`, `updated_at`, `timings`, `error`.
- `run_steps`: `run_id`, `step_index`, `summary`, `tool`, `scores`, `doc_ids`, `created_at`.
- `run_events`: `run_id`, `ts`, `event`, `payload` (SSE replay).
- `idempotency`: `key`, `method`, `path`, `signature`, `status`, `response_body`, `created_at`, `expires_at`.
- `feedback`: `feedback_id`, `run_id`, `thumb`, `note`, `citation_id`, `created_at`.

### Idempotency, Pagination, Soft Delete
- Idempotency via middleware + sqlite table keyed by `Idempotency-Key` + request signature.
- Cursor pagination uses base64 JSON cursor `{updated_at, doc_id}` with stable ordering `(updated_at, doc_id)`.
- Soft delete on documents and namespaces using `deleted_at`, retention window via config key.

## Definition of Done
- FastAPI app replaces old HTTP server implementation.
- All existing endpoints behave as before (paths, status codes, payload shape).
- All required `/v1/*` endpoints implemented.
- SQLite repositories added for namespaces, documents, ingestions, runs, idempotency, feedback.
- SSE endpoints implemented and tested.
- Docs, README, AGENTS, Makefile updated and accurate.
- Tests pass (new FastAPI tests + retained behavior tests).

## Risks and Mitigations
- Risk: Breaking legacy response envelopes.
  - Mitigation: Build compatibility wrappers for existing endpoints and reuse payload shapes from tests.
- Risk: Introducing data inconsistency between old JSON registry and new sqlite.
  - Mitigation: migrate doc registry to sqlite and standardize on sqlite for server paths.
- Risk: SSE event ordering changes.
  - Mitigation: reuse `app/common/stream_protocol.py` and current event order; test with new SSE tests.
- Risk: Background ingestion jobs blocking event loop.
  - Mitigation: run jobs in async worker with `asyncio.to_thread` and regular cancellation checks.
