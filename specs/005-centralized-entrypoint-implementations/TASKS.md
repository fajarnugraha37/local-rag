# Tasks - Centralized Entrypoint Implementations

## Progress Tracker
- Total tasks: 10
- Done: 10
- Doing: 0
- Todo: 0
- Blocked: 0

## T001
- Status: done
- Goal: Identify all existing entrypoints and action call paths.
- Files to touch: none (scan only).
- Steps:
  - Scan root scripts, `app/*` `__main__` blocks, `Makefile`, `README.md`, `AGENTS.md`.
- Acceptance criteria:
  - Old entrypoint inventory captured in spec docs.
- Validation commands:
  - `rg --line-number "__main__" -g "*.py"`

## T002
- Status: done
- Goal: Create centralized launcher at `cmd/app.py`.
- Files to touch:
  - `cmd/app.py`
- Steps:
  - Add `--server` / `--cli` mutually exclusive dispatch.
  - Add pass-through argument forwarding and mode-aware help behavior.
- Acceptance criteria:
  - Launcher can route to server/cli without mangling downstream args.
- Validation commands:
  - `python .\cmd\app.py --help`

## T003
- Status: done
- Goal: Build shared action layer and thin wrappers.
- Files to touch:
  - `cmd/actions.py`
  - `cmd/cli/entrypoint.py`
  - `cmd/server/entrypoint.py`
  - `cmd/__init__.py`
  - `cmd/cli/__init__.py`
  - `cmd/server/__init__.py`
- Steps:
  - Register all actions.
  - Implement `run_action()` using import target + `sys.argv` patching.
  - Add stdlib `cmd.Cmd` compatibility export in `cmd/__init__.py`.
- Acceptance criteria:
  - CLI action list is discoverable; server wrapper calls shared action layer.
- Validation commands:
  - `python .\cmd\app.py --cli --help`
  - `python .\cmd\app.py --server --help`

## T004
- Status: done
- Goal: Remove old root entrypoint scripts.
- Files to touch:
  - deleted: `localrag.py`, `localrag_no_rewrite.py`, `emailrag2.py`, `upload.py`, `collect_emails.py`, `migrate_vault.py`, `index_embeddings.py`, `retrieval.py`, `phase4_validate.py`, `debug_retrieval.py`
- Steps:
  - Delete root shims after launcher cutover.
- Acceptance criteria:
  - Legacy root entrypoint files no longer exist.
- Validation commands:
  - `git status --short`

## T005
- Status: done
- Goal: Remove direct module-entrypoint execution in action modules.
- Files to touch:
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
  - `app/chat/streaming_server.py`
  - `app/ingestion/file_ingest_gui.py`
  - `app/ingestion/email_ingest_job.py`
  - `app/migration/vault_migration.py`
  - `app/migration/backfill_vector_db.py`
  - `app/indexing/embedding_indexer.py`
  - `app/retrieval/hybrid_search.py`
  - `app/validation/phase4_validation_cli.py`
  - `app/tools/retrieval_debug_cli.py`
  - `eval/run_eval.py`
- Steps:
  - Remove `if __name__ == "__main__": main()` blocks.
- Acceptance criteria:
  - Runtime entry flow is centralized through `cmd/app.py`.
- Validation commands:
  - `rg --line-number "if __name__ ==" app eval -g "*.py"`

## T006
- Status: done
- Goal: Update Makefile to use unified launcher.
- Files to touch:
  - `Makefile`
- Steps:
  - Add targets: `run-server`, `run-cli`, `chat`, `ingest`, `query`, `test`, `eval`, `all`.
  - Ensure targets call `python cmd\app.py --server|--cli`.
- Acceptance criteria:
  - Make targets run new launcher only.
- Validation commands:
  - `make run-cli`

## T007
- Status: done
- Goal: Update user docs for centralized contract.
- Files to touch:
  - `README.md`
- Steps:
  - Replace legacy run instructions with unified launcher examples.
  - Add server + cli examples and command list.
- Acceptance criteria:
  - README contains only `python .\cmd\app.py --server|--cli` entry instructions.
- Validation commands:
  - `rg --line-number "localrag.py|upload.py|collect_emails.py|migrate_vault.py" README.md`

## T008
- Status: done
- Goal: Update contributor instructions.
- Files to touch:
  - `AGENTS.md`
- Steps:
  - Document centralized launcher and where new commands must be added.
- Acceptance criteria:
  - AGENTS references `cmd/app.py` workflow and `cmd/actions.py` extension point.
- Validation commands:
  - `rg --line-number "cmd/app.py|cmd/actions.py" AGENTS.md`

## T009
- Status: done
- Goal: Validate server startup through new entrypoint (including health).
- Files to touch: none (runtime check).
- Steps:
  - Start server in background via `--server` mode and call `/health`.
  - Start server through CLI action path and call `/health`.
- Acceptance criteria:
  - Both paths return HTTP 200 for `/health`.
- Validation commands:
  - `python .\cmd\app.py --server --host 127.0.0.1 --port 8011` (background job)
  - `Invoke-WebRequest http://127.0.0.1:8011/health`
  - `python .\cmd\app.py --cli server --host 127.0.0.1 --port 8012` (background job)
  - `Invoke-WebRequest http://127.0.0.1:8012/health`
- Result notes:
  - `HEALTH_STATUS:200`, `HEALTH_BODY:{"ok":true}`
  - `CLI_SERVER_HEALTH_STATUS:200`, `CLI_SERVER_HEALTH_BODY:{"ok":true}`

## T010
- Status: done
- Goal: Validate CLI + tests and finalize spec docs.
- Files to touch:
  - `specs/005-centralized-entrypoint-implementations/IMPROVEMENT.md`
  - `specs/005-centralized-entrypoint-implementations/PLAN.md`
  - `specs/005-centralized-entrypoint-implementations/TASKS.md`
- Steps:
  - Run help flows and representative CLI command.
  - Run full pytest.
  - Record outcomes in TASKS.
- Acceptance criteria:
  - Help flows pass.
  - At least two CLI commands executed successfully.
  - Test suite passes.
- Validation commands:
  - `python .\cmd\app.py --help`
  - `python .\cmd\app.py --server --help`
  - `python .\cmd\app.py --cli --help`
  - `python .\cmd\app.py --cli query --help`
  - `python .\cmd\app.py --cli debug-retrieval`
  - `python -m pytest -q`
- Result notes:
  - Help commands returned exit code 0.
  - `debug-retrieval` produced ranked JSON output.
  - `pytest`: `13 passed in 3.35s`.
