# Spec 010 Tasks

Progress snapshot (updated): all tasks `T001` through `T010` completed and validated.

Dispatch format:
- `please follow specs/010-improve-code-quality/PLAN.md and do task T00X`

## T001
- Goal: add quality tooling baseline (formatter/linter/test config) and wire Make targets.
- Files to touch:
  - `pyproject.toml` (new)
  - `Makefile`
- Steps:
  - Add `ruff` lint and `ruff format` configuration.
  - Add pytest defaults (minimal, non-breaking).
  - Add/normalize Make targets: `fmt`, `lint`, `test`, `run-server`, `run-cli`.
- Acceptance criteria:
  - `make fmt` and `make lint` run successfully.
  - Existing operational Make targets still work.
- Validation commands:
  - `make help`
  - `make fmt`
  - `make lint`
  - `make test`
- Status: done

## T002
- Goal: establish a baseline no-regression checkpoint before structural refactor.
- Files to touch:
  - `tests/` (only if deterministic test harness fixes are required)
  - `specs/010-improve-code-quality/IMPROVEMENT.md` (append baseline notes if needed)
- Steps:
  - Run launcher help checks and current test suite.
  - Capture current known failures (if any) and constrain scope.
- Acceptance criteria:
  - Baseline command/test outcomes are recorded and reproducible.
- Validation commands:
  - `python .\cmd\app.py --help`
  - `python .\cmd\app.py --cli --help`
  - `python .\cmd\app.py --server --help`
  - `python -m pytest -q`
- Status: done

## T003
- Goal: split HTTP server into modular handlers without changing API behavior.
- Files to touch:
  - `app/chat/streaming_server.py`
  - `app/http/server.py` (new)
  - `app/http/sse.py` (new)
  - `app/http/request_parsing.py` (new)
  - `app/http/handlers/chat.py` (new)
  - `app/http/handlers/ingestion.py` (new)
  - `app/http/handlers/docs.py` (new)
  - `app/http/handlers/actions.py` (new)
- Steps:
  - Extract endpoint groups from `streaming_server.py` into handler modules.
  - Keep old module as thin compatibility entrypoint.
  - Preserve route paths and SSE event names.
- Acceptance criteria:
  - `/health`, `/actions`, `/chat/stream`, ingest routes, `/docs`, `/retrieval/query`, `/actions/run` still function.
  - SSE chat stream still emits `sources` and `citation_stats` before `done`.
- Validation commands:
  - `python -m pytest -q tests/test_ingestion_server_routes.py`
  - `python -m pytest -q tests/test_server_citation_sse.py`
  - `python .\cmd\app.py --server --help`
- Status: done

## T004
- Goal: consolidate duplicated chat orchestration across CLI chat modules.
- Files to touch:
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
  - `app/chat/chat_service.py` (new)
  - `app/chat/cli_formatting.py` (new)
- Steps:
  - Extract shared retrieve/prompt/generate/render pipeline into service functions/classes.
  - Keep per-command differences as thin wrappers.
  - Remove duplicated streaming loop and citation rendering glue.
- Acceptance criteria:
  - CLI flags for `chat`, `chat-baseline`, and `chat-email` remain compatible.
  - Citation/no-citation modes behave consistently across commands.
- Validation commands:
  - `python .\cmd\app.py --cli chat --help`
  - `python .\cmd\app.py --cli chat-baseline --help`
  - `python .\cmd\app.py --cli chat-email --help`
  - `python -m pytest -q tests/test_cli_citations.py tests/test_streaming_continuation.py`
- Status: done

## T005
- Goal: separate ingestion command wrappers from ingestion service logic.
- Files to touch:
  - `app/ingestion/file_ingest_gui.py`
  - `app/ingestion/folder_ingest_cli.py`
  - `app/ingestion/pipeline.py`
  - `app/cli/ingest_files.py` (new, if created)
  - `app/cli/ingest_folder.py` (new, if created)
- Steps:
  - Move CLI orchestration/progress UI code to command-layer modules.
  - Keep parsing/extraction/chunking/upsert in service modules.
  - Avoid behavior changes in ingest summary payloads.
- Acceptance criteria:
  - `ingest-files` and `ingest-folder` actions still produce expected summaries.
  - Folder scanning/idempotency tests stay green.
- Validation commands:
  - `python .\cmd\app.py --cli ingest-files --help`
  - `python .\cmd\app.py --cli ingest-folder --help`
  - `python -m pytest -q tests/test_folder_scanner.py tests/test_folder_ingest_idempotency.py tests/test_smoke_ingest.py`
- Status: done

## T006
- Goal: normalize naming and package semantics for embeddings and shared models.
- Files to touch:
  - `app/indexing/embedding_service.py`
  - `app/embeddings/service.py` (new)
  - `app/embeddings/__init__.py` (new)
  - imports in `app/ingestion/vector_ingest_service.py`
  - imports in `app/retrieval/hybrid_search.py`
  - imports in any chat modules that call embedding service directly
- Steps:
  - Introduce `app/embeddings/service.py`.
  - Update imports to semantic module path.
  - Keep temporary compatibility re-export in old module path.
- Acceptance criteria:
  - No runtime import breakage.
  - Retrieval and ingestion embedding calls still succeed in tests.
- Validation commands:
  - `python -m pytest -q tests/test_smoke_retrieval.py tests/test_vector_store_smoke.py`
  - `python -m pytest -q`
- Status: done

## T007
- Goal: standardize logging and error envelope behavior.
- Files to touch:
  - `app/logging/config.py` (new)
  - `app/http/*` (or `app/chat/streaming_server.py` compatibility layer)
  - `app/chat/*`
  - `app/ingestion/*`
- Steps:
  - Add shared logger setup and use it in service/server modules.
  - Keep user-facing CLI output concise while consolidating internal error logging.
  - Normalize server error payload shapes where currently inconsistent.
- Acceptance criteria:
  - Server endpoints return consistent error JSON format.
  - CLI output remains readable and not overly verbose.
- Validation commands:
  - `python -m pytest -q tests/test_ingestion_server_routes.py tests/test_server_citation_sse.py`
  - `python .\cmd\app.py --server --help`
- Status: done

## T008
- Goal: create architecture and contributor documentation in `docs/`.
- Files to touch:
  - `docs/architecture.md` (new)
  - `docs/rag-pipeline.md` (new)
  - `docs/configuration.md` (new)
  - `docs/development.md` (new)
  - `docs/cli.md` (new)
  - `docs/server.md` (new)
  - `docs/contributing.md` (new)
  - optional: `docs/testing.md`, `docs/observability.md`, `docs/security.md` (new)
- Steps:
  - Document module boundaries and data flow.
  - Document extension points (extractors, namespace filters, citations, SSE events).
  - Document development workflow and validation routine.
- Acceptance criteria:
  - Required docs exist with accurate command and path references.
  - README can link to these docs without broken paths.
- Validation commands:
  - `make help`
  - `python .\cmd\app.py --help`
- Status: done

## T009
- Goal: align top-level repo guidance with current architecture and workflows.
- Files to touch:
  - `README.md`
  - `AGENTS.md`
  - `Makefile`
- Steps:
  - Update quickstart and features to match refactored structure.
  - Add agent instructions for boundaries, safe changes, and validation.
  - Ensure Makefile quality targets and workflow targets are coherent.
- Acceptance criteria:
  - Top-level docs match actual commands and module locations.
  - AGENTS guidance is actionable and non-contradictory.
- Validation commands:
  - `make help`
  - `python .\cmd\app.py --cli --help`
  - `python .\cmd\app.py --server --help`
- Status: done

## T010
- Goal: final behavior-preservation verification and cleanup.
- Files to touch:
  - `tests/` (targeted additions/fixes only)
  - touched modules from T003-T009
  - `specs/010-improve-code-quality/IMPROVEMENT.md` (final change summary)
- Steps:
  - Run full validation and smoke checks.
  - Verify no accidental endpoint/flag regressions.
  - Remove obsolete compatibility shims only if all imports/callers are migrated.
- Acceptance criteria:
  - CLI + server + ingestion/query smoke paths pass.
  - Quality targets pass or documented limitations are explicit.
- Validation commands:
  - `make fmt`
  - `make lint`
  - `make test`
  - `python -m pytest -q tests/test_smoke_ingest.py tests/test_smoke_retrieval.py`
  - `python .\cmd\app.py --help`
- Status: done

## Global Acceptance Criteria
- Codebase is reorganized into clear modules with minimal cross-coupling.
- Naming is consistent and semantic across codebase.
- `docs/*.md` exist and are accurate.
- `AGENTS.md`, `README.md`, and `Makefile` are updated and aligned.
- Lint/format/test targets exist and pass (or are explicitly documented when blocked).
- Key workflows validate:
  - run cli
  - run server (HTTP + SSE)
  - run ingestion + query smoke path
