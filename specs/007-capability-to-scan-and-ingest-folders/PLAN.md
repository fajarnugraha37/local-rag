# Plan: Spec 007 Folder Scan + Recursive Ingestion

## Scope
Implement folder-first ingestion for both CLI and server, with deterministic scanning, ignore rules, incremental skip, dry-run, and progress reporting.

## Step 1: Add Scanner Module with Glob + Deterministic Traversal
Goal:
- Introduce a dedicated scanner that discovers and filters file candidates before ingestion.

Changes:
- Add `app/ingestion/folder_scanner.py` with:
  - scan options dataclass,
  - deterministic traversal,
  - include/exclude evaluation,
  - extractor-support prefilter using `ExtractorRegistry.resolve`.

Validation commands:
- `python -m pytest -q tests/test_folder_scanner.py`

## Step 2: Add Ignore Rule Engine (`.gitignore` + `.ragignore`)
Goal:
- Support ignore semantics expected for repository ingestion.

Changes:
- Add lightweight dependency `pathspec` in `requirements.txt`.
- Extend scanner to:
  - apply default exclude set,
  - parse root `.ragignore`,
  - parse root and nested `.gitignore` when enabled.
- Add options to disable gitignore or pass explicit ignore file path.

Validation commands:
- `python -m pytest -q tests/test_folder_scanner.py -k ignore`

## Step 3: Implement Incremental Idempotency Store + `dry_run` + `force`
Goal:
- Skip unchanged files by persisted file fingerprint/hash state.

Changes:
- Add `app/ingestion/file_state_store.py`.
- Add file hashing utility in scanner/ingestion path (streaming reads).
- Add folder-ingest orchestration module (for example `app/ingestion/folder_ingest_service.py`) that:
  - runs scan,
  - decides ingest vs skip,
  - respects `dry_run` and `force`,
  - updates state store after successful ingest.

Validation commands:
- `python -m pytest -q tests/test_folder_ingest_idempotency.py`

## Step 4: Integrate Folder Mode into CLI
Goal:
- Expose a dedicated CLI action for folder ingestion.

Changes:
- Update `cmd/actions.py` to add `ingest-folder`.
- Add `app/ingestion/folder_ingest_cli.py` (or extend existing CLI ingestion module if preferred) with flags:
  - `--path`
  - `--recursive` (default true for this action)
  - `--include`, `--exclude`
  - `--respect-gitignore` / `--no-respect-gitignore`
  - `--dry-run`
  - `--force`
- Reuse existing ingestion pipeline for actual extraction/chunk/upsert.

Validation commands:
- `python .\\cmd\\app.py --cli ingest-folder --help`
- `python .\\cmd\\app.py --cli ingest-folder --path . --dry-run`

## Step 5: Integrate Folder Mode into Server + Progress Streaming
Goal:
- Add server endpoint with optional SSE progress.

Changes:
- Add `POST /ingest/folder` in `app/chat/streaming_server.py`.
- Request validation + path guardrails (reject unsafe roots, enforce allowed roots when configured).
- Non-streaming mode returns JSON summary.
- Streaming mode emits:
  - `scan_started`, `file_found`, `file_selected`, `file_ingested`, `file_skipped`, `file_failed`, `scan_done`.
- Ensure each event includes `request_id`.

Validation commands:
- `python -m pytest -q tests/test_ingestion_server_routes.py -k folder`
- `curl -X POST http://127.0.0.1:8000/ingest/folder -H "Content-Type: application/json" -d "{\"path\":\".\",\"dry_run\":true}"`

## Step 6: Tests + Fixtures + Regression Coverage
Goal:
- Cover scanner, ignore behavior, idempotency, and failure handling.

Changes:
- Add tests:
  - `tests/test_folder_scanner.py`
  - `tests/test_folder_ingest_idempotency.py`
  - update `tests/test_ingestion_server_routes.py` for `/ingest/folder`.
- Add fixtures under `tests/fixtures/folder_scan/` including nested `.gitignore` and `.ragignore`.
- Ensure no regressions in existing ingestion tests.

Validation commands:
- `python -m pytest -q tests/test_folder_scanner.py tests/test_folder_ingest_idempotency.py tests/test_ingestion_server_routes.py`
- `python -m pytest -q`
