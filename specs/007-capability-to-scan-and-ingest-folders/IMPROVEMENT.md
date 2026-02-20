# Feature 007: Capability to Scan and Ingest Folders

## Problem Statement (Current Repo Reality)
Current ingestion can take explicit file paths and can recurse directories, but it is still path-list driven and misses repository-scale workflow needs.

From the codebase today:
- CLI ingestion entrypoint is `app/ingestion/file_ingest_gui.py` (wired as `ingest-files` in `cmd/actions.py`).
- Server ingestion entrypoints are `POST /ingest/files` and `POST /ingest/upload` in `app/chat/streaming_server.py`.
- Shared ingestion pipeline is `app/ingestion/pipeline.py` with `_collect_paths`, `_path_allowed`, `ingest_paths`, and `ingest_single_path`.
- `_collect_paths` supports directory traversal and sorting, but:
  - recursion defaults to `False` (`build_options` in `app/ingestion/pipeline.py`),
  - include/exclude are simple `fnmatch` checks on normalized absolute paths,
  - there is no `.gitignore` or `.ragignore` handling,
  - there is no folder-level dry run, force, or unchanged-file skip.
- Extractor support is registry-based in `app/ingestion/extractors/registry.py` and includes docs/config/data/office formats plus special names (`Dockerfile`, `Makefile`).
- Ingestion limits are configured in `app/config/runtime_settings.py` and `config.yaml` (`ingest_max_bytes`, `ingest_max_rows`, `ingest_max_pages`, zip limits, etc.).
- Progress exists for chunk ingestion callbacks (`start`, `chunk`, `done`) in `app/ingestion/vector_ingest_service.py` and CLI progress bars in `app/ingestion/file_ingest_gui.py`.
- SSE currently exists only for chat (`GET /chat/stream`) in `app/chat/streaming_server.py`; ingestion endpoints return JSON only.
- Idempotency today is chunk/vector upsert idempotency, not file incremental ingestion:
  - vector ids are deterministic (`app/storage/vector_ids.py`),
  - upsert is idempotent per vector id (`app/storage/chroma_vector_store.py`),
  - chunk metadata includes `content_hash` in `app/ingestion/pipeline.py`,
  - there is no persisted per-file ingest state (`path/hash/last_ingested_at`) for unchanged-file skip.

## Why This Is Still Painful
- Ingesting a repo requires manual path orchestration and repeated filtering flags.
- Ignore semantics are not gitignore-like; common folders (`.git`, `node_modules`) are not automatically ignored.
- No first-class folder ingestion API/command with dry-run and incremental behavior.
- No ingestion SSE progress stream for long server-side scans.
- No server-side guardrails against scanning unsafe roots.

## Proposed Design
Add a dedicated folder scan layer and keep ingestion pipeline responsibilities separate.

### 1) Scanner Module (Separate from Ingestion)
New module: `app/ingestion/folder_scanner.py`.

Core types:
- `ScanOptions`: root path, recursive (default `True` for folder mode), include/exclude globs, ignore toggles, limits.
- `FileCandidate`: absolute path, relative path, size, mtime_ns, optional content hash, selected/skipped reason.
- `ScanSummary`: counters and deterministic candidate list.

Scanner behavior:
1. Validate `root` exists and is a directory.
2. Apply server/CLI guardrails:
   - reject filesystem root (for example `C:\\`, `/`) unless explicitly allowed,
   - if `ingest_allowed_roots` is configured, require `root` to be within one of them.
3. Traverse with deterministic ordering (`dirs.sort()`, `files.sort()`, stable final ordering by relative path).
4. Apply filtering pipeline:
   - include globs (default `["**/*"]`),
   - exclude globs (default common ignores),
   - ignore engine (`.ragignore`, optional `.gitignore`, nested `.gitignore`),
   - extractor-supported file check (registry `resolve` pass).
5. Emit scan events and counters without ingesting yet.
6. Return iterable/list of selected `FileCandidate` objects for ingestion phase.

### 2) Ignore Rule Semantics
Defaults (always on unless user overrides):
- `**/.git/**`
- `**/node_modules/**`
- `**/__pycache__/**`
- `**/dist/**`
- `**/build/**`
- `**/.venv/**`
- `**/venv/**`
- `**/.mypy_cache/**`
- `**/.pytest_cache/**`
- `**/.idea/**`
- `**/.vscode/**`

Sources of ignore rules:
1. Built-in defaults.
2. CLI/API `exclude` patterns.
3. `.ragignore` in scan root.
4. `.gitignore` in root and nested directories (enabled by default in folder mode, toggleable).

Precedence:
- File must match include rules.
- File is excluded if matched by any effective exclude/ignore rule.
- CLI/API can disable gitignore handling (`respect_gitignore=false`) and can add/override excludes.

Implementation note:
- Use a lightweight gitignore matcher (`pathspec`) to avoid reimplementing full rule semantics.

### 3) Incremental/Idempotent File Ingestion
New module: `app/ingestion/file_state_store.py`.

State location:
- default `data/ingest_state.json` (configurable via new `ingest_state_path` key).

State record per file (keyed by normalized absolute path):
- `doc_id`
- `content_hash`
- `size`
- `mtime_ns`
- `last_ingested_at`
- `last_result` (`ingested|skipped|failed`)

Flow:
1. Scanner does stat-first selection.
2. For selected files, compute file hash in streaming mode only when needed:
   - if no prior state -> hash then ingest,
   - if prior `size+mtime_ns` unchanged -> skip fast,
   - if stat changed -> hash compare with stored hash to avoid false positives.
3. Skip unchanged files unless `force=true`.
4. `dry_run=true` performs scan + decisioning only; no vector writes, no state writes.

### 4) Batching and Safety
- Keep existing per-file extractor limits from `IngestOptions`.
- Add run-level caps:
  - `ingest_max_files_per_run` (optional),
  - `ingest_max_total_bytes_per_run` (optional).
- Handle unreadable files as `file_failed` with reason; continue unless fail-fast mode is requested.
- Stream file hashing reads in chunks (for example 64KB blocks) to avoid memory spikes.

### 5) CLI and Server Surfaces
CLI:
- Add action `ingest-folder` in `cmd/actions.py`.
- New CLI module `app/ingestion/folder_ingest_cli.py`.
- Command:
  - `python cmd/app.py --cli ingest-folder --path <dir> [--include ...] [--exclude ...] [--respect-gitignore|--no-respect-gitignore] [--dry-run] [--force]`
- Folder mode defaults:
  - recursive `True`,
  - include `["**/*"]`,
  - default excludes enabled.

Server:
- Add endpoint `POST /ingest/folder` in `app/chat/streaming_server.py`.
- Request body:
  - `path`, `recursive`, `include`, `exclude`, `respect_gitignore`, `dry_run`, `force`, optional limit overrides.
- Response:
  - JSON summary for non-streaming mode,
  - SSE event stream when `stream=true`.

### 6) Server Progress Event Schema
All events include:
- `request_id` (from header `X-Request-Id` if present, else generated UUID)
- `timestamp`
- `root`
- stage counters snapshot

Event names:
- `scan_started`
- `file_found`
- `file_selected`
- `file_ingested`
- `file_skipped`
- `file_failed`
- `scan_done`

Example payload shape:
```json
{
  "request_id": "f55f1af7-9d95-4b92-9cfe-9979ba8033db",
  "path": "C:/repo/README.md",
  "relative_path": "README.md",
  "reason": "unchanged",
  "counts": {
    "scanned": 120,
    "selected": 84,
    "ingested": 40,
    "skipped": 42,
    "failed": 2
  }
}
```

## Definition of Done
- Scanning a folder ingests supported files under it recursively.
- Exclude rules work for default ignored folders and explicit excludes.
- `.gitignore` is respected when enabled.
- `dry_run` returns planned actions without vector writes/state writes.
- Incremental ingestion skips unchanged files unless `force=true`.
- Both CLI and server support folder ingestion.
- Tests cover:
  - include/exclude glob logic,
  - gitignore behavior (with fixture),
  - idempotency unchanged-file skip behavior,
  - unreadable/too-large file handling.

## Risks and Mitigations
- Risk: gitignore semantics drift if hand-rolled.
  - Mitigation: use `pathspec` and fixture-driven tests.
- Risk: hash cost on very large repos.
  - Mitigation: stat-first checks; hash only selected/needed files.
- Risk: server path abuse.
  - Mitigation: root guardrails and optional allowed-roots enforcement.
- Risk: doc_id collisions from basename defaults.
  - Mitigation: folder ingestion sets deterministic doc ids from root-relative paths.
