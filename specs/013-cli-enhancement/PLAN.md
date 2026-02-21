# Plan: CLI Enhancement (Direct-to-App)

## Phase 1: CLI Framework + Structure
1. Add Typer dependency and create new CLI package structure.
   - Files: `app/cli/main.py`, `app/cli/shell.py`, `app/cli/render/*`, `app/cli/commands/*`, `app/cli/adapters/service_container.py`.
   - Update `cmd/cli/entrypoint.py` to call new CLI app.
2. Validation:
   - `python .\cmd\app.py --cli --help`
   - `python -c "from app.cli.main import app; print(app)"`

## Phase 2: Service Container Wiring
1. Implement `service_container.py` to wire config, sqlite repos, and services used by FastAPI routers.
   - Use `app/config/runtime_settings.py` for `CONFIG` and `sqlite_db_path`.
2. Validation:
   - `python -c "from app.cli.adapters.service_container import build_services; print(build_services())"`

## Phase 3: Implement Command Domains
1. System commands (healthz/readyz/version/capabilities/config).
   - Use `app.health.checks.run_readiness_checks` and `CONFIG` from runtime settings.
2. Namespaces commands (list/create/delete).
   - Use `NamespaceService` + `validate_namespace`.
3. Documents commands (list/show/delete/bulk-delete/purge).
   - Use `DocumentService` + `DocumentsRepository.purge_soft_deleted`.
4. Ingestions commands (start/status/cancel/logs).
   - Use `IngestionService` directly with `UploadPayload` for file-based ingestion.
5. Query + runs + streaming commands.
   - Use `QueryService` + `RunService` and render events in terminal.
6. Retrieval tools (retrieve/rerank).
   - Use `QueryService.retrieve` and `QueryService.rerank_candidates`.
7. Feedback commands (add/export).
   - Add `FeedbackService` if missing, using `FeedbackRepository`.
8. Validation:
   - `python .\cmd\app.py --cli healthz`
   - `python .\cmd\app.py --cli ns list`
   - `python .\cmd\app.py --cli query "test" --json`

## Phase 4: Interactive Shell + Output Rendering
1. Implement `rag shell` with menus and prompt helpers.
2. Add render helpers for tables, JSON, and event streams.
3. Validation:
   - `python .\cmd\app.py --cli shell`

## Phase 5: Tests
1. Add pytest CLI tests using Typer test runner.
2. Cover pagination, idempotency, streaming, confirmations.
3. Validation:
   - `python -m pytest -q tests/test_cli_*.py`

## Phase 6: Docs + Makefile + AGENTS/README
1. Update docs (`docs/cli.md`, `docs/development.md`, `docs/architecture.md`, `docs/configuration.md`).
2. Update `README.md` and `AGENTS.md` for CLI usage and parity expectations.
3. Update Makefile with `run-cli`, `shell`, and `cli-smoke` targets pointing at new CLI.
4. Validation:
   - `make run-cli`
   - `make cli-smoke`
