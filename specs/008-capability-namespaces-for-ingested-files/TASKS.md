# Tasks: Spec 008 Namespaces for Ingested Files

## T001 - Namespace Helper Module
Goal:
- Add centralized namespace validation/parsing/filter merge helpers.

Files to touch:
- `app/common/namespaces.py`
- `tests/test_namespaces.py`

Steps:
1. Add `default` namespace constant.
2. Implement validation (`[a-z0-9._-]`, max length 64).
3. Implement parser for repeated/comma-separated namespace values.
4. Implement helper to merge namespace filters with existing retrieval filters.

Acceptance criteria:
- Invalid namespaces are rejected.
- Omitted namespace resolves to `default` where required.
- Namespace filter helper supports single and multi-namespace cases.

Validation commands:
- `python -m pytest -q tests/test_namespaces.py`

Status:
- `done`

## T002 - Namespace Metadata in Ingestion
Goal:
- Ensure all ingestion writes namespace metadata for each chunk.

Files to touch:
- `app/ingestion/vector_ingest_service.py`
- `app/ingestion/pipeline.py`
- `app/ingestion/file_ingest_gui.py`
- `app/ingestion/folder_ingest_service.py`
- `app/ingestion/folder_ingest_cli.py`
- `app/ingestion/email_ingest_job.py`

Steps:
1. Add `namespace` parameter to ingestion service and pipeline calls.
2. Set default namespace to `default` if not provided.
3. Validate custom namespace values.
4. Include namespace in chunk metadata written to Chroma.

Acceptance criteria:
- Ingestion with no namespace writes `namespace=default`.
- Ingestion with explicit namespace writes that value.
- Invalid namespace input fails fast with clear error.

Validation commands:
- `python -m pytest -q tests/test_smoke_ingest.py -k namespace`
- `python -m pytest -q tests/test_ingestion_extended_formats.py`

Status:
- `done`

## T003 - Document Registry Store
Goal:
- Add efficient document listing source keyed by `(namespace, doc_id)`.

Files to touch:
- `app/ingestion/doc_registry_store.py`
- `app/config/runtime_settings.py`
- `config.yaml`
- `tests/test_doc_registry_store.py`

Steps:
1. Implement registry store with deterministic ordering and pagination.
2. Define schema fields:
   - namespace, doc_id, source_path, source_type, title, content_hash, chunk_count, created_at, updated_at, last_ingested_at, size_bytes, tags.
3. Add config path for registry file.
4. Add unit tests for CRUD + pagination.

Acceptance criteria:
- Listing does not scan vector chunks.
- Records are keyed by `(namespace, doc_id)`.
- Pagination returns stable output order.

Validation commands:
- `python -m pytest -q tests/test_doc_registry_store.py`

Status:
- `done`

## T004 - Retrieval Namespace Scoping
Goal:
- Support optional namespace scoping in retrieval query path.

Files to touch:
- `app/retrieval/hybrid_search.py`
- `tests/test_smoke_retrieval.py`

Steps:
1. Add optional `namespaces` parameter to `hybrid_search` and `scored_chunks`.
2. Merge namespace filter with optional `filters`.
3. Keep omitted namespaces behavior as all-namespaces search.
4. Expose namespace options in `query` CLI.

Acceptance criteria:
- Query with no namespaces searches all namespaces.
- Query with one/many namespaces returns only matching namespace content.
- Existing `filters` behavior remains correct.

Validation commands:
- `python -m pytest -q tests/test_smoke_retrieval.py -k namespace`

Status:
- `done`

## T005 - CLI Management Actions (`list-docs`, `delete-doc`)
Goal:
- Add namespace-aware doc listing and deletion in CLI.

Files to touch:
- `cmd/actions.py`
- `app/ingestion/list_docs_cli.py`
- `app/ingestion/delete_doc_cli.py`
- `app/ingestion/vector_ingest_service.py`
- `tests/test_cli_doc_management.py`

Steps:
1. Register new actions in action registry.
2. Implement `list-docs [--namespace] [--limit] [--cursor]`.
3. Implement `delete-doc --doc-id ... [--namespace] [--all-namespaces]`.
4. Default delete target to namespace `default` when no explicit global flag.

Acceptance criteria:
- `list-docs` works all namespaces and scoped namespace.
- `delete-doc` supports single namespace and all namespaces.
- Deleting non-existent docs returns success with not-found info.

Validation commands:
- `python .\\cmd\\app.py --cli list-docs --help`
- `python .\\cmd\\app.py --cli delete-doc --help`
- `python -m pytest -q tests/test_cli_doc_management.py`

Status:
- `done`

## T006 - Server Management Endpoints (`GET /docs`, `DELETE /docs/{doc_id}`)
Goal:
- Add namespace-aware list/delete APIs.

Files to touch:
- `app/chat/streaming_server.py`
- `tests/test_ingestion_server_routes.py`
- `tests/postman/easy-local-rag-server.postman_collection.json`

Steps:
1. Add `GET /docs` with optional namespace/limit/cursor.
2. Add `DELETE /docs/{doc_id}` with namespace/all_namespaces support.
3. Keep deletion idempotent and safe by default.
4. Return stable response payload including namespace + doc_id identifiers.

Acceptance criteria:
- Server list-docs supports global and per-namespace listing.
- Server delete-doc supports one namespace and all namespaces.
- Non-existent deletes are non-fatal and explicit.

Validation commands:
- `python -m pytest -q tests/test_ingestion_server_routes.py -k \"docs or delete\"`

Status:
- `done`

## T007 - Namespace Parameters in Server Ingestion Endpoints
Goal:
- Accept `namespace` for all server ingestion surfaces.

Files to touch:
- `app/chat/streaming_server.py`
- `tests/test_ingestion_server_routes.py`

Steps:
1. Add namespace parsing/validation to:
   - `/ingest/chunks`
   - `/ingest/text`
   - `/ingest/files`
   - `/ingest/folder`
   - `/ingest/upload`
2. Pass namespace through ingestion pipeline/services.
3. Ensure default namespace fallback.

Acceptance criteria:
- Each ingestion endpoint accepts and enforces namespace semantics.
- Invalid namespace returns HTTP 400.

Validation commands:
- `python -m pytest -q tests/test_ingestion_server_routes.py -k ingest`

Status:
- `done`

## T008 - Backfill/Migration for Existing Data
Goal:
- Assign namespace `default` to existing vectors and build registry.

Files to touch:
- `app/migration/backfill_namespaces.py`
- `cmd/actions.py`
- `app/storage/chroma_vector_store.py`
- `tests/test_namespace_migration.py`

Steps:
1. Add migration command/action (e.g. `backfill-namespaces`).
2. Scan existing vectors in batches.
3. Update missing namespace metadata to `default`.
4. Rebuild/update document registry entries from existing metadata.
5. Make operation idempotent.

Acceptance criteria:
- Existing vectors are assigned namespace `default`.
- Registry is populated for migrated docs.
- Re-running migration does not duplicate data or fail.

Validation commands:
- `python .\\cmd\\app.py --cli backfill-namespaces --help`
- `python -m pytest -q tests/test_namespace_migration.py`

Status:
- `done`

## T009 - End-to-End Acceptance Coverage
Goal:
- Validate complete spec acceptance criteria.

Files to touch:
- `tests/test_smoke_ingest.py`
- `tests/test_smoke_retrieval.py`
- `tests/test_ingestion_server_routes.py`
- `tests/test_cli_doc_management.py`
- `tests/test_namespaces.py`
- `tests/test_doc_registry_store.py`
- `tests/test_namespace_migration.py`

Steps:
1. Add acceptance-style tests covering all required behaviors.
2. Run full test suite and fix regressions.

Acceptance criteria:
- Ingestion assigns namespace correctly (`default` + custom).
- Query all-vs-subset namespace behavior works.
- List-docs and delete-doc behaviors work for single namespace and all namespaces.
- Existing data migration/backfill behavior is verified.

Validation commands:
- `python -m pytest -q`

Status:
- `todo`

## Global Acceptance Criteria (Spec 008)
- Ingestion assigns namespace correctly (default + custom).
- Query without namespaces searches all; query with namespaces searches only selected ones.
- `list-docs` works for all namespaces and for a specific namespace, efficiently.
- `delete-doc` supports:
  - delete from one namespace
  - delete across all namespaces
- Existing data is migrated to `default` or a documented re-ingest path exists.
- Tests cover namespace validation, ingestion metadata, query scoping, list-docs behavior, and delete behavior.
