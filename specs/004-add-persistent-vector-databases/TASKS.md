# Tasks: Persistent Vector Database Migration (Feature 004)

## Progress Tracker
- `todo`: 7
- `doing`: 0
- `done`: 4
- `blocked`: 0

## Dispatch Rule
Use: `please follow specs/004-add-persistent-vector-databases/PLAN.md and do task T00X`.

## Task List

### T001 — Baseline behavior snapshot
- Status: `done`
- Goal: capture pre-migration retrieval behavior and data counts for parity checks.
- Files to touch: `eval/results-pre-vector-db.json` (generated artifact only).
- Steps:
1. Run eval baseline.
2. Record current chunk count from `data/chunks.jsonl`.
- Acceptance criteria:
1. Baseline eval JSON exists.
2. Chunk count is recorded in command output/log.
- Validation commands:
```powershell
python eval\run_eval.py --questions eval\questions.jsonl --top-k 6 --output eval\results-pre-vector-db.json
```

### T002 — Add Chroma dependency and vector config
- Status: `done`
- Goal: define runtime settings for persistent vector DB.
- Files to touch: `requirements.txt`, `config.yaml`, `app/config/runtime_settings.py`.
- Steps:
1. Add `chromadb` dependency.
2. Add `vector_db_provider`, `vector_db_persist_dir`, `vector_db_collection`, `vector_db_batch_size`, `vector_db_timeout_s`, `embedding_dim`.
3. Add env overrides for these keys.
- Acceptance criteria:
1. Config keys load via `settings.CONFIG`.
2. App still imports successfully.
- Validation commands:
```powershell
@'
from app.config import runtime_settings as s
print({k: s.CONFIG.get(k) for k in ["vector_db_provider", "vector_db_collection", "embedding_dim"]})
'@ | python -
```

### T003 — Implement deterministic ID strategy
- Status: `done`
- Goal: ensure idempotent upsert/delete semantics with stable IDs.
- Files to touch: `app/storage/vector_ids.py` (new), `app/common/content_hashing.py` (optional reuse).
- Steps:
1. Add helpers for `doc_id`, `chunk_id`, `vector_id`.
2. Ensure `vector_id = sha256(doc_id + ':' + chunk_id)`.
- Acceptance criteria:
1. Same input always returns same IDs.
2. Different docs with same text produce different `vector_id`.
- Validation commands:
```powershell
python -m pytest -q tests\test_vector_ids.py
```

### T004 — Implement Chroma vector store module
- Status: `done`
- Goal: add persistent store operations as the new storage backend.
- Files to touch: `app/storage/chroma_vector_store.py` (new), `app/storage/__init__.py` (new).
- Steps:
1. Implement connect/init with persist dir + collection.
2. Implement `upsert`, `query`, `delete_by_doc_id`, `count`, `health`.
3. Enforce embedding dimension check (hard fail).
- Acceptance criteria:
1. Store can upsert/query/delete in local persist dir.
2. Dimension mismatch raises explicit error.
- Validation commands:
```powershell
python -m pytest -q tests\test_vector_store_smoke.py
```

### T005 — Centralize embedding generation
- Status: `todo`
- Goal: avoid duplicated embedding parsing logic and validate embedding dimensions once.
- Files to touch: `app/indexing/embedding_service.py` (new), `app/indexing/embedding_indexer.py`, `app/retrieval/hybrid_search.py`.
- Steps:
1. Add shared `extract_embedding` and `embed_text` utilities.
2. Reuse in indexing/retrieval/storage flows.
- Acceptance criteria:
1. No duplicated `extract_embedding` logic remains in multiple modules.
2. Embedding service returns list[float] and model metadata.
- Validation commands:
```powershell
rg -n "def extract_embedding" app
python -m pytest -q
```

### T006 — Migrate ingestion to vector upsert and delete-by-doc
- Status: `todo`
- Goal: make ingestion write directly to vector DB and support deletion lifecycle.
- Files to touch: `app/ingestion/file_ingest_gui.py`, `app/ingestion/email_ingest_job.py`, `app/migration/vault_migration.py`, `app/ingestion/vector_ingest_service.py` (new).
- Steps:
1. Replace JSONL append logic with vector upsert service.
2. Add delete-by-doc function and wire CLI path.
3. Keep chunking behavior unchanged unless required bugfix.
- Acceptance criteria:
1. Ingested chunks appear in vector store.
2. Delete by `doc_id` removes all related vectors.
- Validation commands:
```powershell
python -m pytest -q tests\test_smoke_ingest.py tests\test_vector_store_smoke.py
```

### T007 — Rewrite retrieval path to use vector DB
- Status: `todo`
- Goal: cut retrieval over to persistent vector DB (no file-based loading).
- Files to touch: `app/retrieval/hybrid_search.py`, `app/retrieval/heuristic_reranker.py` (if needed), callers in `app/chat/*.py`, `app/tools/retrieval_debug_cli.py`, `eval/run_eval.py`, `app/validation/phase4_validation_cli.py`.
- Steps:
1. Replace `load_chunks/load_embeddings` logic with vector query.
2. Keep `scored_chunks` contract usable by callers.
3. Add optional metadata filter support.
- Acceptance criteria:
1. `scored_chunks` returns top-k results from Chroma.
2. Metadata filters work for at least `doc_id`.
- Validation commands:
```powershell
python -m pytest -q tests\test_smoke_retrieval.py
python -m app.retrieval.hybrid_search --query "contract" --top-k 3
```

### T008 — Implement migration/backfill command
- Status: `todo`
- Goal: migrate existing JSONL knowledge to vector DB with resume-safe behavior.
- Files to touch: `app/migration/backfill_vector_db.py` (new), optionally `index_embeddings.py` shim.
- Steps:
1. Read `data/chunks.jsonl` and optional `data/embeddings.jsonl`.
2. Upsert in batches with deterministic IDs and retries.
3. Log progress and failures.
- Acceptance criteria:
1. Re-running command does not duplicate records.
2. Backfill reports migrated/skipped/error counts.
- Validation commands:
```powershell
python -m app.migration.backfill_vector_db --batch-size 64
@'
from app.storage.chroma_vector_store import ChromaVectorStore
print("count", ChromaVectorStore().count())
'@ | python -
```

### T009 — Remove old storage mechanism after cutover
- Status: `todo`
- Goal: fully eliminate JSONL-based chunk/embedding storage paths.
- Files to touch: `app/indexing/embedding_indexer.py`, `app/retrieval/hybrid_search.py`, `app/ingestion/file_ingest_gui.py`, `app/ingestion/email_ingest_job.py`, `config.yaml`, `README.md`.
- Steps:
1. Remove file-based read/write code and obsolete config keys.
2. Keep legacy mentions only inside migration docs/scripts if needed.
- Acceptance criteria:
1. App runtime does not depend on `data/chunks.jsonl` or `data/embeddings.jsonl`.
2. `rg` shows no active old-path references in runtime code.
- Validation commands:
```powershell
rg -n "chunks\.jsonl|embeddings\.jsonl|append_embedding|load_embeddings\(" app config.yaml README.md
```

### T010 — Add full test coverage for migration requirements
- Status: `todo`
- Goal: cover correctness and reliability for new storage.
- Files to touch: `tests/test_vector_ids.py` (new), `tests/test_vector_store_smoke.py` (new), `tests/test_smoke_ingest.py`, `tests/test_smoke_retrieval.py`.
- Steps:
1. Add unit tests for IDs and metadata/filter mapping.
2. Add ingest->retrieve->delete integration smoke test using temporary persist dir.
3. Add dimension mismatch test.
- Acceptance criteria:
1. Required test scenarios pass.
2. No regression in existing streaming tests.
- Validation commands:
```powershell
python -m pytest -q
```

### T011 — Post-cutover evaluation and documentation
- Status: `todo`
- Goal: verify retrieval parity and document new operational workflow.
- Files to touch: `eval/results-post-vector-db.json` (artifact), `README.md`, `AGENTS.md`.
- Steps:
1. Run post-migration eval and compare with baseline.
2. Document vector DB setup, backup/restore, healthcheck, backfill command.
- Acceptance criteria:
1. Eval completes and output is saved.
2. Docs describe Chroma as single source of truth and include delete/upsert workflow.
- Validation commands:
```powershell
python eval\run_eval.py --questions eval\questions.jsonl --top-k 6 --output eval\results-post-vector-db.json
python -m pytest -q
```
