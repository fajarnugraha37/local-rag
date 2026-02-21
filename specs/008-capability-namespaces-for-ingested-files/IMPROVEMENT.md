# Feature 008: Capability Namespaces for Ingested Files

## Problem Statement (Current Repo Reality)
Today, ingested content is stored in a single global pool with no namespace concept.

Grounded findings from current code:
- CLI ingestion entrypoints:
  - `ingest-files` -> `app/ingestion/file_ingest_gui.py` (wired in `cmd/actions.py`)
  - `ingest-folder` -> `app/ingestion/folder_ingest_cli.py` (spec 007 is present)
- Server ingestion entrypoints (`app/chat/streaming_server.py`):
  - `POST /ingest/chunks`
  - `POST /ingest/text`
  - `POST /ingest/files`
  - `POST /ingest/folder`
  - `POST /ingest/upload`
- Retrieval pipeline:
  - `app/retrieval/hybrid_search.py` (`hybrid_search`, `scored_chunks`)
  - Chroma query happens in `ChromaVectorStore.query(..., where=filters)` in `app/storage/chroma_vector_store.py`
- Storage layer:
  - Chroma persistent single collection (`vector_db_collection`) in `app/storage/chroma_vector_store.py`
  - Metadata filtering already supported via `where=filters` in `query`
- Current chunk/document id strategy:
  - Deterministic ids in `app/storage/vector_ids.py` (`doc_id`, `chunk_id`, `vector_id`)
  - `app/ingestion/vector_ingest_service.py` writes metadata keys:
    - `doc_id`, `doc_key`, `chunk_id`, `source`, `token_count`
  - No `namespace` metadata is written
- Existing doc management features:
  - Delete only: `POST /vectors/delete-doc` -> `delete_doc(doc_id)` in `app/ingestion/vector_ingest_service.py`
  - No list-docs CLI or server endpoint
  - Delete currently removes by doc id globally (`ChromaVectorStore.delete_by_doc_id`)
- Config system:
  - Module: `app/config/runtime_settings.py`
  - File: `config.yaml`
  - Env overrides in `runtime_settings.py`

Impact:
- Cannot scope retrieval to project-specific data.
- Cannot list or delete documents cleanly by logical group.
- Accidental cross-project retrieval is likely because all chunks live together.

## Chosen Storage Design
Chosen: **Option 1: namespace as chunk metadata field** + **document registry file**.

Decision matrix:
- Option 1 (metadata field in one collection):
  - Pros: fits existing `where=filters` support in `app/storage/chroma_vector_store.py`; minimal operational complexity; no collection lifecycle code.
  - Cons: listing docs efficiently needs separate registry.
- Option 2 (collection per namespace):
  - Pros: isolation by storage boundary.
  - Cons: larger refactor, collection lifecycle/ops complexity, higher risk.

Why Option 1 here:
- Repo already uses one Chroma collection and metadata filters.
- Namespace filtering can be implemented without changing storage provider assumptions.
- A lightweight registry solves efficient list-docs without scanning all chunks.

## Namespace Semantics
- Every ingested document must have a namespace.
- Default namespace: `default`.
- Namespace validation:
  - Allowed characters: `[a-z0-9._-]`
  - Max length: `64`
  - Empty/invalid values rejected.

Query behavior:
- No namespaces provided: search across all namespaces.
- One or more namespaces provided: search only selected namespaces.

## Document Registry Design
Add a lightweight registry keyed by `(namespace, doc_id)` for fast document management.

Suggested module:
- `app/ingestion/doc_registry_store.py`

Record schema:
- `namespace`
- `doc_id`
- `source_path`
- `source_type`
- `title`
- `content_hash`
- `chunk_count`
- `size_bytes`
- `tags`
- `created_at`
- `updated_at`
- `last_ingested_at`

Why needed:
- Efficient `list-docs` without querying/scanning all vectors.
- Stable management interface for delete workflows.

## API / CLI Contract Updates
### Ingestion
- CLI:
  - `python .\cmd\app.py --cli ingest-files --path README.md --namespace default`
  - `python .\cmd\app.py --cli ingest-folder --path . --namespace project-a`
- Server:
  - All ingestion endpoints accept `namespace` in JSON/form body where applicable.
  - If omitted -> `default`.

### Query
- CLI:
  - `python .\cmd\app.py --cli query --query "payment terms" --namespaces project-a,default`
  - Support repeated `--namespaces` flags.
- Server:
  - `POST /retrieval/query` body may include `"namespaces": ["project-a", "default"]`.
  - Omitted `namespaces` means query all.

### List documents
- CLI:
  - `python .\cmd\app.py --cli list-docs`
  - `python .\cmd\app.py --cli list-docs --namespace project-a --limit 50 --cursor 50`
- Server:
  - `GET /docs?namespace=project-a&limit=50&cursor=50`

Response fields:
- `namespace`, `doc_id`, `source_path`, `chunk_count`, `updated_at`, `content_hash`, `size_bytes`

### Delete documents
- CLI:
  - `python .\cmd\app.py --cli delete-doc --doc-id README.md --namespace project-a`
  - `python .\cmd\app.py --cli delete-doc --doc-id README.md --all-namespaces`
  - Safety default: if neither `--namespace` nor `--all-namespaces`, delete from `default` only.
- Server:
  - `DELETE /docs/{doc_id}?namespace=project-a`
  - `DELETE /docs/{doc_id}?all_namespaces=true`

Deletion behavior:
- Idempotent.
- Removes vector chunks and registry entries.

## Migration / Backfill Plan
Existing vectors have no namespace metadata. Migration tool is required.

Add command:
- `python .\cmd\app.py --cli backfill-namespaces --namespace default`

Tool behavior:
1. Scan existing vectors in current Chroma collection.
2. For vectors missing `namespace`, set `namespace="default"`.
3. Build/update doc registry entries from existing metadata.
4. Safe to rerun (idempotent).

If metadata is insufficient for complete registry fields, fill best-effort fields and document fallback behavior.

## Definition of Done
- Ingestion writes namespace for all ingest paths (`default` + custom).
- Query without namespaces searches all; with namespaces searches only selected namespaces.
- `list-docs` works globally and per-namespace efficiently via registry.
- `delete-doc` supports namespace-specific and all-namespaces deletes.
- Existing data is backfilled to `default` (or explicit re-ingest path documented if impossible).
- Tests cover:
  - namespace validation
  - ingestion metadata namespace write
  - query all-vs-subset behavior
  - list-docs per namespace correctness
  - delete single namespace vs all namespaces

## Non-goals
- Authentication/authorization.
- Fancy UI changes.
- Remote git clone ingestion.

## Risks and Mitigations
- Risk: accidental global deletes.
  - Mitigation: explicit `--all-namespaces` / `all_namespaces=true`; default to `default` namespace delete only.
- Risk: filter composition bugs (`filters` + namespace).
  - Mitigation: centralized filter merge helper and dedicated tests.
- Risk: migration touching large collections.
  - Mitigation: batched backfill with resumable/idempotent behavior.
- Risk: doc id collisions across namespaces if ids are unchanged.
  - Mitigation: keep registry key as `(namespace, doc_id)` and ensure vector metadata always includes namespace.
