# Plan: FastAPI Server Migration

## Phase 0: Baseline and Dependencies
1. Add dependencies for FastAPI + ASGI + test client.
   - Files: `requirements.txt`, `pyproject.toml` (if needed).
   - Add: `fastapi`, `uvicorn`, `httpx`, `python-multipart`.
   - Validation: `python -m pytest -q` (expect existing tests to fail until server refactor is done).

## Phase 1: SQLite Persistence Layer
1. Create sqlite db module and migrations.
   - Files: `app/repositories/sqlite/db.py`.
   - Add schema for namespaces, documents, ingestions, ingestion_events, runs, run_steps, run_events, idempotency, feedback.
2. Implement repositories per table with small, explicit queries.
   - Files: `app/repositories/sqlite/namespaces_repo.py`, `documents_repo.py`, `ingestions_repo.py`, `runs_repo.py`, `idempotency_repo.py`, `feedback_repo.py`.
3. Provide migration/init CLI or Make target (db init).
   - Files: `Makefile`, optional `cmd/actions.py` action for db init.
   - Validation: `python -c "from app.repositories.sqlite.db import init_db; init_db('data/app.db')"`.

## Phase 2: FastAPI App Skeleton + Middleware
1. Create FastAPI app factory and lifespan.
   - Files: `app/http/fastapi_app.py`.
2. Add middleware for request id / trace id.
   - Files: `app/http/middleware/request_id.py`.
3. Add idempotency middleware (Idempotency-Key + sqlite storage).
   - Files: `app/http/middleware/idempotency.py`, `app/repositories/sqlite/idempotency_repo.py`.
4. Validation:
   - `python -c "from app.http.fastapi_app import create_app; app=create_app()"`.

## Phase 3: Legacy Endpoint Parity Routers
1. Implement legacy routes with identical behavior:
   - `GET /health`, `GET /actions`, `POST /actions/run`, `GET /docs`, `DELETE /docs/{doc_id}`.
   - `GET /chat/stream`, `POST /ingest/chunks`, `POST /ingest/text`, `POST /ingest/files`, `POST /ingest/folder`, `POST /ingest/upload`.
   - `POST /vectors/delete-doc`, `POST /retrieval/query`.
2. Use services that call existing ingestion/retrieval modules to keep behavior.
   - Files: `app/services/*`, `app/http/routers/legacy.py` (or split by domain).
3. Validation:
   - `python -m pytest -q tests/test_ingestion_server_routes.py tests/test_server_citation_sse.py`.

## Phase 4: New v1 System + Config Endpoints
1. Implement system routes:
   - `/healthz`, `/readyz`, `/version`, `/v1/capabilities`, `/v1/config` GET/PATCH.
   - Readiness uses `app/health/checks.py` with vector DB, sqlite, reranker checks.
2. Validation:
   - `python -m pytest -q tests/test_fastapi_system_endpoints.py` (new test).

## Phase 5: Namespaces + Documents APIs
1. Implement `/v1/namespaces` list/create/delete (soft delete).
2. Implement `/v1/documents` list/detail/delete and `documents:bulk_delete`.
3. Pagination with stable cursor `(updated_at, doc_id)`.
4. Soft delete + retention config; purge command or scheduled cleanup.
5. Validation:
   - `python -m pytest -q tests/test_fastapi_documents.py tests/test_fastapi_namespaces.py`.

## Phase 6: Ingestion Jobs (Async)
1. Implement ingestion job runner and status tracking.
   - Use sqlite tables + background tasks.
2. Implement sources:
   - folder (reuses `app/ingestion/folder_scanner.py` + `folder_ingest_service.py`),
   - repo (git clone + checkout),
   - upload (multipart to temp storage).
3. Implement `/v1/ingestions` endpoints and `/v1/documents` upload.
4. Validation:
   - `python -m pytest -q tests/test_fastapi_ingestions.py`.

## Phase 7: Query + Runs + Events
1. Implement `/v1/query` (non-stream) with run_id + trace_id.
2. Implement `/v1/query/stream` SSE with required events.
3. Implement `/v1/runs/{run_id}`, `/v1/runs/{run_id}/steps`, `/v1/runs/{run_id}/events`, `/v1/runs/{run_id}/replay`.
4. Validation:
   - `python -m pytest -q tests/test_fastapi_query_runs.py tests/test_fastapi_sse.py`.

## Phase 8: Retrieval + Rerank API
1. Implement `/v1/retrieve` returning raw candidates and component scores.
2. Implement `/v1/rerank` for arbitrary candidates.
3. Validation:
   - `python -m pytest -q tests/test_fastapi_retrieve_rerank.py`.

## Phase 9: Cutover + Cleanup
1. Remove old server modules and update entrypoint.
   - Update `cmd/actions.py` server target to FastAPI runner.
   - Remove `app/http/server.py`, `app/http/handlers/*`, `app/http/request_parsing.py`, `app/http/sse.py`, `app/chat/streaming_server.py`.
2. Update Makefile to run `uvicorn app.http.fastapi_app:create_app`.
3. Update docs + README + AGENTS.
4. Validation:
   - `make run-server` (manual), `python -m pytest -q`.

## Phase 10: Docs and Validation
1. Update docs: `docs/api.md`, `docs/server.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/development.md`.
2. Update `README.md`, `AGENTS.md`, `Makefile`.
3. Validation:
   - `make fmt`, `make lint`, `make test`.
