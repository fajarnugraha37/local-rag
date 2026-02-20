# Tasks: Spec 007 Folder Scan + Recursive Ingestion

## T001 - Build Deterministic Folder Scanner
Goal:
- Create a scanner that traverses directories and returns deterministic candidate files with metadata.

Files to touch:
- `app/ingestion/folder_scanner.py`
- `app/ingestion/__init__.py`

Steps:
1. Add scanner dataclasses (`ScanOptions`, `FileCandidate`, `ScanSummary`).
2. Implement deterministic traversal (`dirs/files` sorting, stable output ordering).
3. Add include/exclude glob filtering and extractor-support precheck via registry resolve.
4. Emit counters for scanned/selected/skipped.

Acceptance criteria:
- Folder scan returns reproducible ordering across runs.
- Unsupported file types are filtered before extraction/upsert.
- Include/exclude glob filtering works on relative paths.

Validation commands:
- `python -m pytest -q tests/test_folder_scanner.py -k deterministic`
- `python -m pytest -q tests/test_folder_scanner.py -k include`

Status:
- `todo`

## T002 - Implement Ignore Rules (`.gitignore` + `.ragignore`)
Goal:
- Support practical repo ignore semantics, including nested `.gitignore`.

Files to touch:
- `app/ingestion/folder_scanner.py`
- `requirements.txt`
- `tests/test_folder_scanner.py`
- `tests/fixtures/folder_scan/`

Steps:
1. Add `pathspec` dependency for gitignore-compatible matching.
2. Implement default exclude patterns (`.git`, `node_modules`, `__pycache__`, `dist`, `build`, etc.).
3. Parse `.ragignore` from scan root.
4. Parse root and nested `.gitignore` files relative to their directories.
5. Add toggles/options to disable gitignore behavior and append explicit excludes.

Acceptance criteria:
- Exclude rules work for default ignored directories.
- `.gitignore` is respected when enabled.
- Nested `.gitignore` rules are applied relative to nested directories.

Validation commands:
- `python -m pytest -q tests/test_folder_scanner.py -k gitignore`
- `python -m pytest -q tests/test_folder_scanner.py -k ragignore`

Status:
- `todo`

## T003 - Add File State Store + Incremental Skip
Goal:
- Skip unchanged files and support force reingestion.

Files to touch:
- `app/ingestion/file_state_store.py`
- `app/ingestion/folder_ingest_service.py`
- `app/config/runtime_settings.py`
- `config.yaml`
- `tests/test_folder_ingest_idempotency.py`

Steps:
1. Add persisted file state store (`data/ingest_state.json` by default).
2. Store per-file hash/stat/last_ingested metadata.
3. Implement stat-first then hash-on-demand unchanged detection.
4. Add `force` override to ingest unchanged files anyway.
5. Add `dry_run` mode that computes decisions without DB/state writes.

Acceptance criteria:
- Incremental ingestion skips unchanged files unless forced.
- Dry run lists ingest/skip decisions with reasons and performs no writes.
- State is updated after successful ingestion.

Validation commands:
- `python -m pytest -q tests/test_folder_ingest_idempotency.py -k unchanged`
- `python -m pytest -q tests/test_folder_ingest_idempotency.py -k dry_run`

Status:
- `todo`

## T004 - Add CLI Surface `ingest-folder`
Goal:
- Provide first-class CLI folder ingestion.

Files to touch:
- `cmd/actions.py`
- `app/ingestion/folder_ingest_cli.py`
- `README.md`

Steps:
1. Register `ingest-folder` action.
2. Add parser flags:
   - `--path`
   - `--include` / `--exclude`
   - `--respect-gitignore` / `--no-respect-gitignore`
   - `--dry-run`
   - `--force`
3. Wire CLI command to folder scanner + existing ingestion pipeline.
4. Print progress counters (`scanned`, `selected`, `ingested`, `skipped`, `failed`) and final summary.

Acceptance criteria:
- CLI can ingest an entire folder recursively from one command.
- Dry-run and force behavior is available in CLI.
- Progress output is visible and totals are consistent.

Validation commands:
- `python .\\cmd\\app.py --cli ingest-folder --help`
- `python .\\cmd\\app.py --cli ingest-folder --path . --dry-run`

Status:
- `todo`

## T005 - Add Server Endpoint `POST /ingest/folder` + SSE Progress
Goal:
- Support folder ingestion through server API with optional event streaming.

Files to touch:
- `app/chat/streaming_server.py`
- `tests/test_ingestion_server_routes.py`
- `tests/postman/easy-local-rag-server.postman_collection.json`

Steps:
1. Add request validation for folder options.
2. Add path guardrails:
   - reject unsafe root paths,
   - enforce configured allowed roots when present.
3. Add JSON summary response mode.
4. Add SSE streaming mode with events:
   - `scan_started`, `file_found`, `file_selected`, `file_ingested`, `file_skipped`, `file_failed`, `scan_done`.
5. Include `request_id` correlation on all events and summary.

Acceptance criteria:
- Server can ingest a folder by local path.
- Streaming mode emits required events in plausible order.
- Guardrails block dangerous scan roots.

Validation commands:
- `python -m pytest -q tests/test_ingestion_server_routes.py -k folder`
- `curl -X POST http://127.0.0.1:8000/ingest/folder -H "Content-Type: application/json" -d "{\"path\":\".\",\"dry_run\":true}"`

Status:
- `todo`

## T006 - Add Regression and Safety Tests
Goal:
- Ensure behavior is correct and resilient.

Files to touch:
- `tests/test_folder_scanner.py`
- `tests/test_folder_ingest_idempotency.py`
- `tests/test_ingestion_server_routes.py`
- `tests/fixtures/folder_scan/`

Steps:
1. Add include/exclude glob tests.
2. Add gitignore fixture test (including nested `.gitignore`).
3. Add unreadable-file and too-large-file behavior tests.
4. Add server endpoint coverage for happy path and invalid path.

Acceptance criteria:
- Tests cover:
  - include/exclude logic,
  - gitignore behavior,
  - idempotency skip behavior,
  - unreadable/too-large file handling.
- Existing ingestion tests continue to pass.

Validation commands:
- `python -m pytest -q tests/test_folder_scanner.py tests/test_folder_ingest_idempotency.py tests/test_ingestion_server_routes.py`
- `python -m pytest -q`

Status:
- `todo`

## Global Acceptance Criteria (Spec 007)
- Scanning a folder ingests all supported files under it (recursive).
- Exclude rules work (`node_modules`, `.git`, etc. are not ingested).
- `.gitignore` is respected when enabled.
- Dry-run lists planned actions without writing.
- Incremental ingestion skips unchanged files unless forced.
- CLI and server both support folder ingestion.
- Tests cover glob logic, gitignore behavior, idempotency skip behavior, and unreadable/too-large file handling.
