# Plan: Spec 008 Namespaces for Ingested Files

## Scope
Implement namespace-aware ingestion, retrieval scoping, and document management (list/delete) for both CLI and server, with backfill for existing data.

## Step 1: Add Namespace Validation + Helpers
Goal:
- Create shared namespace parsing/validation and filter merge logic.

Changes:
- Add `app/common/namespaces.py`:
  - default namespace constant (`default`)
  - validator for `[a-z0-9._-]`, max length 64
  - parser for comma/repeated namespace inputs
  - helper to merge namespace filter with existing `filters`.

Validation commands:
- `python -m pytest -q tests/test_namespaces.py -k validation`

## Step 2: Add Namespace to Chunk Metadata + Ingestion Paths
Goal:
- Ensure every ingested chunk/document carries a namespace.

Changes:
- Update `app/ingestion/vector_ingest_service.py`:
  - accept `namespace` argument
  - write `namespace` metadata on each chunk
  - preserve default behavior via `default` namespace.
- Update `app/ingestion/pipeline.py`:
  - plumb `namespace` through `ingest_single_path`, `ingest_paths`, `ingest_uploaded_files`.
- Update CLI ingestion entrypoints:
  - `app/ingestion/file_ingest_gui.py`
  - `app/ingestion/folder_ingest_cli.py`
  - `app/ingestion/folder_ingest_service.py`

Validation commands:
- `python -m pytest -q tests/test_smoke_ingest.py -k namespace`
- `python -m pytest -q tests/test_ingestion_extended_formats.py`

## Step 3: Implement Document Registry Store
Goal:
- Provide efficient list-docs without scanning all vectors.

Changes:
- Add `app/ingestion/doc_registry_store.py` with key `(namespace, doc_id)`.
- Add config key default (for example `doc_registry_path`) in:
  - `app/config/runtime_settings.py`
  - `config.yaml`
- Update ingestion service to upsert registry record after successful ingest.

Validation commands:
- `python -m pytest -q tests/test_doc_registry_store.py`

## Step 4: Update Retrieval for Optional Namespace Scoping
Goal:
- Support all-namespaces by default and subset filtering when requested.

Changes:
- Update `app/retrieval/hybrid_search.py`:
  - accept optional namespaces
  - merge namespace filter with existing `filters`
  - include namespace in returned result metadata.
- Update query CLI flags in same file:
  - `--namespaces` (comma-separated and repeatable).

Validation commands:
- `python -m pytest -q tests/test_smoke_retrieval.py -k namespace`

## Step 5: Add List-Docs and Delete-Doc Management Actions
Goal:
- Add namespace-aware document management in CLI and server.

Changes:
- CLI:
  - add actions in `cmd/actions.py`: `list-docs`, `delete-doc` (and migration action)
  - add `app/ingestion/list_docs_cli.py`
  - add `app/ingestion/delete_doc_cli.py`
- Server:
  - update `app/chat/streaming_server.py`:
    - `GET /docs?namespace=&limit=&cursor=`
    - `DELETE /docs/{doc_id}?namespace=...|all_namespaces=true`
  - keep delete idempotent and safe defaults.

Validation commands:
- `python -m pytest -q tests/test_ingestion_server_routes.py -k \"docs or delete\"`
- `python .\\cmd\\app.py --cli list-docs --help`
- `python .\\cmd\\app.py --cli delete-doc --help`

## Step 6: Implement Backfill/Migration Tool
Goal:
- Assign `namespace=default` to existing vectors and build registry records.

Changes:
- Add `app/migration/backfill_namespaces.py`.
- Add action wiring in `cmd/actions.py` (for example `backfill-namespaces`).
- Migration should be idempotent and batched.

Validation commands:
- `python .\\cmd\\app.py --cli backfill-namespaces --help`
- `python -m pytest -q tests/test_namespace_migration.py`

## Step 7: Update Server Ingestion Contracts
Goal:
- Ensure all ingestion endpoints accept namespace.

Changes:
- Update `app/chat/streaming_server.py` for:
  - `/ingest/chunks`
  - `/ingest/text`
  - `/ingest/files`
  - `/ingest/folder`
  - `/ingest/upload`

Validation commands:
- `python -m pytest -q tests/test_ingestion_server_routes.py -k ingest`

## Step 8: End-to-End Regression Tests
Goal:
- Cover required acceptance behavior and prevent regressions.

Changes:
- Add/extend tests:
  - `tests/test_namespaces.py`
  - `tests/test_doc_registry_store.py`
  - `tests/test_smoke_ingest.py`
  - `tests/test_smoke_retrieval.py`
  - `tests/test_ingestion_server_routes.py`
  - `tests/test_namespace_migration.py`

Validation commands:
- `python -m pytest -q`
