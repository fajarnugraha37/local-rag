# Tasks: CLI Enhancement (Direct-to-App)

## T001: CLI Framework + Entry Point
- Goal: Introduce unified Typer CLI app and wire `cmd/cli/entrypoint.py` to it.
- Files:
  - `app/cli/main.py`
  - `app/cli/__init__.py`
  - `cmd/cli/entrypoint.py`
  - `requirements.txt` / `pyproject.toml` (if Typer added)
- Steps:
  1. Create Typer app with root command + global options.
  2. Update `run_cli()` to invoke Typer app instead of action dispatch.
  3. Keep legacy actions accessible via an `actions` subcommand if needed.
- Acceptance:
  - `python .\cmd\app.py --cli --help` shows new CLI help.
  - `python -c "from app.cli.main import app"` succeeds.
- Validation:
  - `python .\cmd\app.py --cli --help`
- Status: done

## T002: Service Container
- Goal: Provide a central wiring helper for CLI to access services directly.
- Files:
  - `app/cli/adapters/service_container.py`
- Steps:
  1. Implement `build_services()` returning instances of `NamespaceService`, `DocumentService`, `IngestionService`, `QueryService`, `RunService`, and new `FeedbackService` if added.
  2. Ensure DB path resolution mirrors FastAPI (`CONFIG['sqlite_db_path']` fallback to `data/app.db`).
- Acceptance:
  - Services created without side effects.
- Validation:
  - `python -c "from app.cli.adapters.service_container import build_services; print(build_services())"`
- Status: done

## T003: System + Config Commands
- Goal: Implement system commands for healthz/readyz/version/capabilities/config.
- Files:
  - `app/cli/commands/system.py`
  - `app/cli/main.py`
- Steps:
  1. Implement commands calling `run_readiness_checks` and `CONFIG`.
  2. Support `config get` and `config set` (patch-like updates).
- Acceptance:
  - Commands return JSON or formatted output.
- Validation:
  - `python .\cmd\app.py --cli healthz`
  - `python .\cmd\app.py --cli config get --json`
- Status: done

## T004: Namespaces + Documents Commands
- Goal: CLI parity for namespaces and documents (list/show/delete/bulk/purge).
- Files:
  - `app/cli/commands/namespaces.py`
  - `app/cli/commands/documents.py`
  - `app/cli/render/tables.py`
- Steps:
  1. Use `NamespaceService` + `DocumentService` for operations.
  2. Implement pagination cursor support and `--json` output.
  3. Implement soft delete by default and `doc purge` for retention purge.
- Acceptance:
  - `rag ns list` and `rag doc list` display tables and emit next cursor.
- Validation:
  - `python .\cmd\app.py --cli ns list`
  - `python .\cmd\app.py --cli doc list --limit 5 --json`
- Status: done

## T005: Ingestion Commands + Job Events
- Goal: CLI support for ingestion jobs and logs.
- Files:
  - `app/cli/commands/ingestions.py`
  - `app/cli/render/events.py`
- Steps:
  1. Implement `ingest start` for folder/repo/files using `IngestionService`.
  2. Implement `ingest status`, `ingest cancel`, `ingest logs` (follow mode).
  3. Support idempotency keys via shared helper.
- Acceptance:
  - `rag ingest start` returns ingestion_id and `rag ingest logs` streams events.
- Validation:
  - `python .\cmd\app.py --cli ingest status <id>`
- Status: done

## T006: Query + Runs + Streaming
- Goal: Implement query/runs commands and streaming event renderer.
- Files:
  - `app/cli/commands/query.py`
  - `app/cli/commands/runs.py`
  - `app/cli/render/events.py`
- Steps:
  1. `rag query` uses `QueryService.run_query` and prints answer + citations.
  2. `rag query stream` replays events from `RunsRepository` in terminal-friendly form.
  3. Runs commands show stored runs, steps, events, replay streams.
- Acceptance:
  - `rag query "..."` prints run_id + trace_id.
  - `rag query stream "..."` prints meta/final/sources/done.
- Validation:
  - `python .\cmd\app.py --cli query "test" --json`
- Status: done

## T007: Retrieve/Rerank + Feedback
- Goal: Add CLI support for retrieval tools and feedback.
- Files:
  - `app/cli/commands/retrieve.py`
  - `app/cli/commands/feedback.py`
  - `app/services/feedback_service.py` (new, if missing)
- Steps:
  1. Implement `rag retrieve` and `rag rerank` using `QueryService`.
  2. Add FeedbackService wrapping `FeedbackRepository`.
  3. Implement `rag feedback add` and `rag feedback export`.
- Acceptance:
  - Commands return structured output and support `--json`.
- Validation:
  - `python .\cmd\app.py --cli retrieve "test" --json`
- Status: todo

## T008: Interactive Shell
- Goal: Implement `rag shell` interactive menu.
- Files:
  - `app/cli/shell.py`
  - `app/cli/interactive.py`
- Steps:
  1. Provide menu for query, namespaces/docs, ingestion, runs, config.
  2. Use same command handlers internally (no duplicate business logic).
- Acceptance:
  - Shell starts and can run a query end-to-end.
- Validation:
  - `python .\cmd\app.py --cli shell`
- Status: todo

## T009: Idempotency + Pagination Helpers
- Goal: Provide shared helpers for idempotency keys and cursor pagination.
- Files:
  - `app/cli/pagination.py`
  - `app/cli/idempotency.py`
- Steps:
  1. Add deterministic key builder for CLI operations.
  2. Reuse `IdempotencyRepository` to store/replay results.
- Acceptance:
  - Duplicate idempotency keys return same result.
- Validation:
  - `python -m pytest -q tests/test_cli_idempotency.py`
- Status: todo

## T010: Tests
- Goal: Add CLI test coverage for critical flows.
- Files:
  - `tests/test_cli_basic.py`
  - `tests/test_cli_pagination.py`
  - `tests/test_cli_streaming.py`
- Steps:
  1. Use Typer CliRunner to invoke commands.
  2. Validate pagination cursor behavior, idempotency, streaming output, and confirmations.
- Acceptance:
  - CLI tests pass.
- Validation:
  - `python -m pytest -q tests/test_cli_*.py`
- Status: todo

## T011: Docs + Makefile + AGENTS/README
- Goal: Update docs and workflow targets to reflect new CLI.
- Files:
  - `docs/cli.md`
  - `docs/development.md`
  - `docs/architecture.md`
  - `docs/configuration.md`
  - `README.md`
  - `AGENTS.md`
  - `Makefile`
- Steps:
  1. Update docs with command reference and interactive shell.
  2. Update Makefile with `run-cli`, `shell`, `cli-smoke`.
- Acceptance:
  - Docs reflect direct-to-service CLI and current command surface.
- Validation:
  - `make run-cli`
- Status: todo
