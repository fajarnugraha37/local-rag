# Tasks: FastAPI Server Migration

## T001: Add FastAPI Dependencies
- Goal: Add FastAPI + ASGI + multipart + test client dependencies.
- Files to touch:
  - `requirements.txt`
  - `pyproject.toml`
- Steps:
  1. Add `fastapi`, `uvicorn`, `httpx`, `python-multipart`.
  2. Keep versions unpinned unless conflicts arise.
- Acceptance criteria:
  - `pip install -r requirements.txt` installs FastAPI dependencies.
- Validation commands:
  - `python -m pytest -q` (expected to fail until refactor is complete).
- Status: done

## T002: SQLite DB + Repositories
- Goal: Create sqlite schema and repository layer for namespaces, docs, ingestions, runs, idempotency, feedback.
- Files to touch:
  - `app/repositories/sqlite/db.py`
  - `app/repositories/sqlite/namespaces_repo.py`
  - `app/repositories/sqlite/documents_repo.py`
  - `app/repositories/sqlite/ingestions_repo.py`
  - `app/repositories/sqlite/runs_repo.py`
  - `app/repositories/sqlite/idempotency_repo.py`
  - `app/repositories/sqlite/feedback_repo.py`
- Steps:
  1. Implement `init_db()` with explicit schema.
  2. Implement CRUD operations with consistent return shapes.
  3. Add soft-delete columns and pagination query helpers.
- Acceptance criteria:
  - Schema initializes and basic CRUD works with sqlite file.
- Validation commands:
  - `python -c "from app.repositories.sqlite.db import init_db; init_db('data/app.db')"`
- Status: done

## T003: FastAPI App Skeleton + Middleware
- Goal: Create FastAPI app with middleware, lifespan, and router registration.
- Files to touch:
  - `app/http/fastapi_app.py`
  - `app/http/middleware/request_id.py`
  - `app/http/middleware/idempotency.py`
- Steps:
  1. Implement `create_app()` and register routers.
  2. Implement request id middleware and idempotency middleware with sqlite repo.
- Acceptance criteria:
  - App starts and responds to `/health` and `/healthz`.
- Validation commands:
  - `python -c "from app.http.fastapi_app import create_app; app=create_app()"`
- Status: done

## T004: Legacy Endpoint Parity (FastAPI)
- Goal: Re-implement all existing endpoints with identical behavior.
- Files to touch:
  - `app/http/routers/legacy.py` (or split per domain)
  - `app/http/schemas/*`
  - `app/services/*`
- Steps:
  1. Implement `GET /health`, `GET /actions`, `POST /actions/run`.
  2. Implement ingestion endpoints and `/vectors/delete-doc`.
  3. Implement `/docs` list + delete and `/retrieval/query`.
  4. Implement `/chat/stream` SSE using current stream protocol.
- Acceptance criteria:
  - Existing server tests pass with FastAPI.
- Validation commands:
  - `python -m pytest -q tests/test_ingestion_server_routes.py tests/test_server_citation_sse.py`
- Status: done

## T005: System Endpoints
- Goal: Add `/healthz`, `/readyz`, `/version`, `/v1/capabilities`, `/v1/config`.
- Files to touch:
  - `app/http/routers/system.py`
  - `app/http/schemas/common.py`
  - `app/health/checks.py`
- Steps:
  1. Implement readiness checks for vector db + sqlite + reranker.
  2. Implement config GET/PATCH with validation.
- Acceptance criteria:
  - `/readyz` reports all dependencies.
- Validation commands:
  - `python -m pytest -q tests/test_fastapi_system_endpoints.py`
- Status: todo

## T006: Namespaces + Documents v1
- Goal: Implement namespace registry + documents APIs with pagination and soft delete.
- Files to touch:
  - `app/http/routers/namespaces.py`
  - `app/http/routers/documents.py`
  - `app/http/schemas/namespaces.py`
  - `app/http/schemas/documents.py`
  - `app/services/namespace_service.py`
  - `app/services/document_service.py`
  - `app/repositories/sqlite/*`
- Steps:
  1. Implement namespace list/create/delete with soft delete and dry_run.
  2. Implement document list/detail/delete and bulk delete by filters.
  3. Enforce stable cursor pagination `(updated_at, doc_id)`.
- Acceptance criteria:
  - List and delete behavior matches spec, including soft delete filter.
- Validation commands:
  - `python -m pytest -q tests/test_fastapi_documents.py tests/test_fastapi_namespaces.py`
- Status: todo

## T007: Ingestion Jobs
- Goal: Implement async ingestion jobs with folder/repo/upload sources.
- Files to touch:
  - `app/http/routers/ingestions.py`
  - `app/http/schemas/ingestions.py`
  - `app/services/ingestion_service.py`
  - `app/repositories/sqlite/ingestions_repo.py`
- Steps:
  1. Implement job table + background runner with cancellation checks.
  2. Implement folder source via `folder_scanner.py` and `folder_ingest_service.py`.
  3. Implement repo source using `git clone` into controlled workspace.
  4. Implement upload source via multipart handling and temp storage.
- Acceptance criteria:
  - `/v1/ingestions` returns job id, status updates, cancel works.
- Validation commands:
  - `python -m pytest -q tests/test_fastapi_ingestions.py`
- Status: todo

## T008: Query + Runs + SSE
- Goal: Implement query endpoints with run storage and SSE event replay.
- Files to touch:
  - `app/http/routers/query.py`
  - `app/http/routers/runs.py`
  - `app/http/schemas/query.py`
  - `app/http/schemas/runs.py`
  - `app/services/query_service.py`
  - `app/services/run_service.py`
  - `app/repositories/sqlite/runs_repo.py`
- Steps:
  1. Implement `/v1/query` returning `run_id` + `trace_id` + citations.
  2. Implement `/v1/query/stream` SSE with required event names.
  3. Persist run events and expose `/v1/runs/{id}` and `/events`.
- Acceptance criteria:
  - Streaming and non-streaming endpoints return run metadata and citations.
- Validation commands:
  - `python -m pytest -q tests/test_fastapi_query_runs.py tests/test_fastapi_sse.py`
- Status: todo

## T009: Retrieval + Rerank APIs
- Goal: Add `/v1/retrieve` and `/v1/rerank` endpoints.
- Files to touch:
  - `app/http/routers/query.py`
  - `app/http/schemas/query.py`
  - `app/services/query_service.py`
- Steps:
  1. Implement raw retrieval response with component scores.
  2. Implement rerank for given candidate set using existing heuristic reranker.
- Acceptance criteria:
  - Endpoints return structured scores and stable ids.
- Validation commands:
  - `python -m pytest -q tests/test_fastapi_retrieve_rerank.py`
- Status: todo

## T010: Idempotency + Pagination + Soft Delete
- Goal: Ensure idempotency, cursor pagination, soft delete retention across endpoints.
- Files to touch:
  - `app/http/middleware/idempotency.py`
  - `app/repositories/sqlite/idempotency_repo.py`
  - `app/repositories/sqlite/documents_repo.py`
  - `app/repositories/sqlite/namespaces_repo.py`
- Steps:
  1. Implement idempotency signature and response cache.
  2. Implement retention window with purge job or Make target.
- Acceptance criteria:
  - Duplicate key returns same response; soft deleted records excluded by default.
- Validation commands:
  - `python -m pytest -q tests/test_fastapi_idempotency.py tests/test_fastapi_pagination.py`
- Status: todo

## T011: Cutover + Cleanup
- Goal: Remove old server and update entrypoints.
- Files to touch:
  - `cmd/actions.py`
  - `cmd/server/entrypoint.py`
  - `app/http/server.py` (remove)
  - `app/http/handlers/*` (remove)
  - `app/http/request_parsing.py` (remove)
  - `app/http/sse.py` (remove)
  - `app/chat/streaming_server.py` (remove)
- Steps:
  1. Point server action to FastAPI entrypoint (uvicorn or programmatic).
  2. Delete old server code and update imports.
- Acceptance criteria:
  - `python .\cmd\app.py --server --help` works and starts FastAPI server.
- Validation commands:
  - `python -m pytest -q`
- Status: todo

## T012: Docs + README + AGENTS + Makefile
- Goal: Update documentation and workflows for FastAPI.
- Files to touch:
  - `docs/api.md`
  - `docs/server.md`
  - `docs/architecture.md`
  - `docs/configuration.md`
  - `docs/development.md`
  - `README.md`
  - `AGENTS.md`
  - `Makefile`
- Steps:
  1. Document new endpoints and Swagger at `/docs`.
  2. Update run commands to `uvicorn`.
  3. Add Make targets: `run-server`, `db-init`, `smoke`.
- Acceptance criteria:
  - Docs match FastAPI behavior and Make targets run.
- Validation commands:
  - `make fmt`, `make lint`, `make test`, `make run-server`.
- Status: todo

## Global Acceptance Criteria
- All legacy endpoints are preserved with identical behavior.
- All `/v1/*` endpoints implemented and documented.
- SSE streaming works for chat and `/v1/query/stream`.
- Idempotency, pagination, and soft delete are enforced.
- SQLite repositories used for server state (namespaces, docs, jobs, runs, feedback, idempotency).
- Old server implementation removed.
- Tests pass.

