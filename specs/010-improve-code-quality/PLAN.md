# Spec 010 Plan: Improve Code Quality

This plan is incremental and behavior-preserving. Each phase has explicit checkpoints and rollback guidance.

## Phase 1: Tooling Baseline and Guardrails

### Step 1.1 Add repo tooling config
- Files/dirs to change:
  - `pyproject.toml` (new)
  - `Makefile`
- Work:
  - Configure `ruff` lint + format.
  - Configure `pytest` defaults.
  - Add optional, scoped `mypy` config if feasible.
  - Add `make fmt`, `make lint`, `make test`, `make run-server`, `make run-cli` targets.
- Validation commands:
  - `make fmt`
  - `make lint`
  - `make test`
- Rollback checkpoint:
  - `git add pyproject.toml Makefile`
  - `git commit -m "Add quality tooling baseline"`

### Step 1.2 Establish no-regression baseline
- Files/dirs to change:
  - `tests/` (only if small fixes needed for deterministic baseline)
- Work:
  - Run baseline test suite and capture current pass/fail snapshot.
  - Ensure launcher and help surfaces still operate.
- Validation commands:
  - `python .\cmd\app.py --help`
  - `python .\cmd\app.py --cli --help`
  - `python .\cmd\app.py --server --help`
  - `python -m pytest -q`
- Rollback checkpoint:
  - `git add tests`
  - `git commit -m "Stabilize baseline checks"`

## Phase 2: Module Boundary Refactor

### Step 2.1 Split HTTP server responsibilities
- Files/dirs to change:
  - `app/chat/streaming_server.py`
  - `app/http/server.py` (new)
  - `app/http/sse.py` (new)
  - `app/http/request_parsing.py` (new)
  - `app/http/handlers/chat.py` (new)
  - `app/http/handlers/ingestion.py` (new)
  - `app/http/handlers/docs.py` (new)
  - `app/http/handlers/actions.py` (new)
- Work:
  - Move route logic into handler modules.
  - Keep `app/chat/streaming_server.py` as compatibility entrypoint forwarding to new server bootstrap.
  - Preserve endpoint routes and SSE event names.
- Validation commands:
  - `python .\cmd\app.py --server --help`
  - `python -m pytest -q tests/test_ingestion_server_routes.py`
  - `python -m pytest -q tests/test_server_citation_sse.py`
- Rollback checkpoint:
  - `git add app/chat/streaming_server.py app/http`
  - `git commit -m "Split HTTP server into modular handlers"`

### Step 2.2 Consolidate chat orchestration
- Files/dirs to change:
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
  - `app/chat/chat_service.py` (new)
  - `app/chat/cli_formatting.py` (new)
- Work:
  - Extract shared retrieval/prompt/stream/render flow into a service.
  - Keep existing action names and CLI flags.
  - Remove duplicated event handling blocks where behavior is identical.
- Validation commands:
  - `python .\cmd\app.py --cli chat --help`
  - `python .\cmd\app.py --cli chat-baseline --help`
  - `python .\cmd\app.py --cli chat-email --help`
  - `python -m pytest -q tests/test_cli_citations.py tests/test_streaming_continuation.py`
- Rollback checkpoint:
  - `git add app/chat`
  - `git commit -m "Extract shared chat service and slim CLI modules"`

### Step 2.3 Separate ingestion command wrappers from services
- Files/dirs to change:
  - `app/ingestion/file_ingest_gui.py`
  - `app/ingestion/folder_ingest_cli.py`
  - `app/ingestion/pipeline.py`
  - `app/cli/ingest_files.py` (new, if introduced)
  - `app/cli/ingest_folder.py` (new, if introduced)
- Work:
  - Isolate UI/CLI argument parsing from ingestion business logic.
  - Keep extractor/chunk/upsert flow in service modules.
  - Reuse shared progress rendering utilities.
- Validation commands:
  - `python .\cmd\app.py --cli ingest-files --help`
  - `python .\cmd\app.py --cli ingest-folder --help`
  - `python -m pytest -q tests/test_folder_scanner.py tests/test_folder_ingest_idempotency.py tests/test_smoke_ingest.py`
- Rollback checkpoint:
  - `git add app/ingestion app/cli`
  - `git commit -m "Decouple ingestion command wrappers from ingestion services"`

## Phase 3: Naming Cleanup and API Hygiene

### Step 3.1 Normalize naming and package semantics
- Files/dirs to change:
  - `app/indexing/embedding_service.py`
  - `app/embeddings/service.py` (new)
  - `app/indexing/__init__.py`
  - internal imports across `app/ingestion/*`, `app/retrieval/*`, `app/chat/*`
- Work:
  - Move embedding service to semantic package (`app/embeddings`).
  - Add compatibility shim imports in old module paths during transition.
  - Remove vague helper names and dead code (`open_file`-style leftovers) where safe.
- Validation commands:
  - `python -m pytest -q tests/test_smoke_retrieval.py tests/test_vector_store_smoke.py`
  - `python -m pytest -q`
- Rollback checkpoint:
  - `git add app/indexing app/embeddings app`
  - `git commit -m "Normalize embeddings naming and remove dead helpers"`

### Step 3.2 Standardize error handling and logging shape
- Files/dirs to change:
  - `app/logging/config.py` (new)
  - `app/chat/*`
  - `app/http/*` or `app/chat/streaming_server.py` compatibility module
  - `app/ingestion/*`
- Work:
  - Replace ad-hoc print/error formatting in service/server code with shared logger + consistent response envelopes.
  - Keep CLI-friendly output in command wrappers.
- Validation commands:
  - `python -m pytest -q tests/test_ingestion_server_routes.py tests/test_server_citation_sse.py`
  - `python .\cmd\app.py --server --help`
- Rollback checkpoint:
  - `git add app/logging app/chat app/ingestion app/http`
  - `git commit -m "Standardize logging and error handling paths"`

## Phase 4: Documentation and Repo Surface Alignment

### Step 4.1 Add canonical docs set
- Files/dirs to change:
  - `docs/architecture.md`
  - `docs/rag-pipeline.md`
  - `docs/configuration.md`
  - `docs/development.md`
  - `docs/cli.md`
  - `docs/server.md`
  - `docs/contributing.md`
  - optional: `docs/testing.md`, `docs/observability.md`, `docs/security.md`
- Work:
  - Document actual architecture/data flows and extension points.
  - Include naming conventions and safe refactor workflow.
- Validation commands:
  - manual link/path check from README
  - `python .\cmd\app.py --help`
  - `make help`
- Rollback checkpoint:
  - `git add docs`
  - `git commit -m "Add architecture and contributor documentation set"`

### Step 4.2 Update top-level repo contracts
- Files/dirs to change:
  - `README.md`
  - `AGENTS.md`
  - `Makefile`
- Work:
  - Align docs/commands/features with current implementation.
  - Add agent guidance for module boundaries, validation sequence, and safe small diffs.
  - Ensure Make targets reflect quality tooling and run paths.
- Validation commands:
  - `make help`
  - `python .\cmd\app.py --cli --help`
  - `python .\cmd\app.py --server --help`
  - `python -m pytest -q`
- Rollback checkpoint:
  - `git add README.md AGENTS.md Makefile`
  - `git commit -m "Align README AGENTS and Makefile with refactored architecture"`

## Final Verification Gate
- Required verification commands:
  - `make fmt`
  - `make lint`
  - `make test`
  - `python .\cmd\app.py --help`
  - `python .\cmd\app.py --cli --help`
  - `python .\cmd\app.py --server --help`
  - `python -m pytest -q tests/test_smoke_ingest.py tests/test_smoke_retrieval.py`
- Completion criteria:
  - No regressions on core CLI/server paths.
  - Docs and top-level guides match real behavior.
  - Quality targets are reproducible from clean checkout.

