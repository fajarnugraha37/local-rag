# Spec 013: CLI Enhancement (Direct-to-App)

## Repo Scan Summary (Current State)
- CLI entrypoint: `cmd/app.py` (argparse launcher) and `cmd/cli/entrypoint.py` (action dispatcher).
- Action registry: `cmd/actions.py` loads per-action modules (chat, ingest, query, list-docs, delete-doc, etc).
- Current CLI implementations:
  - `app/cli/ingest_files.py`, `app/cli/ingest_folder.py`.
  - `app/ingestion/list_docs_cli.py`, `app/ingestion/delete_doc_cli.py`.
  - Chat CLIs: `app/chat/document_chat_cli.py`, `app/chat/document_chat_baseline_cli.py`, `app/chat/email_chat_cli.py`.
  - Retrieval CLI: `app/retrieval/hybrid_search.py` (JSON output).
- FastAPI server routers and services (CLI must reuse these services directly):
  - Routers: `app/http/routers/system.py`, `namespaces.py`, `documents.py`, `ingestions.py`, `query.py`, `runs.py`, `legacy.py`.
  - Services: `app/services/{namespace_service.py,document_service.py,ingestion_service.py,query_service.py,run_service.py}`.
  - SSE helpers: `app/http/sse_utils.py` and protocol in `app/common/stream_protocol.py`.
- Persistence:
  - SQLite repos: `app/repositories/sqlite/{db.py,namespaces_repo.py,documents_repo.py,ingestions_repo.py,runs_repo.py,feedback_repo.py,idempotency_repo.py}`.
  - Vector DB: `app/storage/chroma_vector_store.py` (Chroma, stored under `data/chroma`).
  - Legacy doc registry JSON: `app/ingestion/doc_registry_store.py` (used by current CLI list/delete, not by FastAPI v1 docs endpoints).
- Existing docs for CLI: `docs/cli.md`, `docs/development.md`, `README.md`.
- Makefile targets for CLI: `run-cli`, plus action-based targets (`chat`, `ingest`, `list-docs`, `delete-doc`, etc).

## Current CLI Gaps vs FastAPI v1 Surface
- CLI does **not** expose v1 endpoints for namespaces, ingestions, runs, or system readiness/version/config.
- CLI document list/delete uses legacy JSON registry, not the SQLite-backed `DocumentService` used by FastAPI.
- CLI has no structured support for ingestion jobs, events, or job cancellation (FastAPI `/v1/ingestions`).
- CLI query streaming is limited to chat actions; no parity with `/v1/query/stream` run events.
- No CLI for `/v1/retrieve`, `/v1/rerank` equivalents (beyond `retrieval/hybrid_search.py`).
- No CLI for feedback (repository exists but no service/HTTP/CLI wiring).
- No CLI idempotency support (server uses `IdempotencyRepository` + middleware).

## Design Choice: CLI Framework
- Current CLI uses argparse scattered across multiple modules with `cmd/actions.py` dispatch.
- For parity and usability, migrate to a unified CLI app using **Typer** (subcommands, help, testability) while keeping `cmd/app.py --cli` as the entrypoint.
- Justification: Typer improves UX, supports subcommands cleanly, and is a modest dependency. We can keep output formatting in stdlib (no rich) to keep deps minimal.

## Target Command Mapping (API -> CLI)
- System
  - `GET /healthz` -> `rag healthz`
  - `GET /readyz` -> `rag readyz`
  - `GET /version` -> `rag version`
  - `GET /v1/capabilities` -> `rag capabilities`
  - `GET /v1/config` -> `rag config get`
  - `PATCH /v1/config` -> `rag config set --key K --value V` (or `--json`)
- Namespaces
  - `GET /v1/namespaces` -> `rag ns list [--include-deleted]`
  - `POST /v1/namespaces` -> `rag ns create <name> [--defaults-json ...]`
  - `DELETE /v1/namespaces/{ns}` -> `rag ns delete <name> [--dry-run] [--yes]`
- Ingestions
  - `POST /v1/ingestions` -> `rag ingest start --namespace <ns> --source folder|repo|files ...`
  - `POST /v1/ingestions/upload` -> `rag ingest start --source files --paths ...`
  - `GET /v1/ingestions/{id}` -> `rag ingest status <id>`
  - `POST /v1/ingestions/{id}/cancel` -> `rag ingest cancel <id>`
  - `GET /v1/ingestions/{id}/events` -> `rag ingest logs <id> [--follow]`
- Documents
  - `GET /v1/documents` -> `rag doc list [filters] [--cursor --limit]`
  - `GET /v1/documents/{namespace}/{doc_id}` -> `rag doc show <namespace> <doc_id>` (alias `rag doc show <doc_id> --namespace`)
  - `DELETE /v1/documents/{namespace}/{doc_id}` -> `rag doc delete <doc_id> --namespace ... [--hard-delete]`
  - `POST /v1/documents:bulk_delete` -> `rag doc bulk-delete ...`
- Query/Runs
  - `POST /v1/query` -> `rag query "..."` (non-stream)
  - `POST /v1/query/stream` -> `rag query stream "..."` (terminal stream)
  - `GET /v1/runs/{run_id}` -> `rag run show <run_id>`
  - `GET /v1/runs/{run_id}/steps` -> `rag run steps <run_id>`
  - `GET /v1/runs/{run_id}/events` -> `rag run events <run_id> [--follow]`
  - `GET /v1/runs/{run_id}/replay` -> `rag run replay <run_id>`
- Retrieval Tools
  - `POST /v1/retrieve` -> `rag retrieve "..."`
  - `POST /v1/rerank` -> `rag rerank --query "..." --candidates <json>`
- Legacy parity
  - Keep alias commands for legacy endpoints (`/health`, `/docs`, `/actions/run`, `/chat/stream`, `/ingest/*`, `/retrieval/query`) implemented via service calls where possible or wrappers to legacy modules when required.

## Interactive UX (Shell Mode)
- `rag shell` provides a guided menu:
  - Query (stream + citations)
  - Browse namespaces and documents (pagination)
  - Start ingestion (folder/repo/files) + tail events
  - Inspect run + replay
  - Config view/update
- Interactive prompts only when `--interactive` is enabled; otherwise all commands remain scriptable and non-blocking.

## Idempotency / Pagination / Soft Delete
- CLI must use `IdempotencyRepository` directly for destructive or job-creating commands.
- Default delete operations are soft (respect `deleted_at`); `rag doc purge` calls hard deletes past retention.
- Pagination uses the same cursor encoding as `DocumentService` (`updated_at`, `doc_id` ordering).

## Definition of Done
- CLI covers all v1 capabilities implemented by FastAPI plus legacy routes via direct service calls.
- CLI is single-entry with subcommands, consistent help, and interactive shell.
- CLI calls services directly (no HTTP).
- Tests cover pagination, idempotency, query streaming, and destructive confirmations.
- Docs/README/AGENTS/Makefile updated to match the new CLI.

## Risks & Mitigations
- Drift between CLI and service interfaces: mitigate with shared service container and tests that exercise both CLI and service outputs.
- Output stability (automation users): provide `--json` for structured output on all commands.
- Interactive prompts blocking automation: only prompt when `--interactive` or `rag shell` is used.
