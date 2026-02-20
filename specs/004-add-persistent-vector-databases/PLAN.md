# Implementation Plan: Persistent Vector DB Cutover (Feature 004)

## Preconditions
- Python env active and dependencies installed.
- Ollama running with embedding model from `config.yaml` (`mxbai-embed-large`).
- Create a working branch before changes.

## Step 1: Baseline and freeze reference behavior
**Change**
- Record baseline retrieval metrics before migration.
- Snapshot current data counts.

**Commands**
```powershell
python eval\run_eval.py --questions eval\questions.jsonl --top-k 6 --output eval\results-pre-vector-db.json
@'
from pathlib import Path
p = Path("data/chunks.jsonl")
count = sum(1 for line in p.open("r", encoding="utf-8") if line.strip()) if p.exists() else 0
print({"chunks_count": count})
'@ | python -
```

## Step 2: Add vector DB dependency and runtime config
**Change**
- Update `requirements.txt` with `chromadb`.
- Update `config.yaml` with `vector_db_*` keys + `embedding_dim`.
- Extend `app/config/runtime_settings.py` env overrides for vector DB settings.

**Files**
- `requirements.txt`
- `config.yaml`
- `app/config/runtime_settings.py`

**Validate**
```powershell
@'
from app.config import runtime_settings as s
print(s.CONFIG.get("vector_db_provider"), s.CONFIG.get("vector_db_collection"))
'@ | python -
```

## Step 3: Add storage package (single source of truth)
**Change**
- Create `app/storage/` package with:
  - `app/storage/vector_ids.py` (deterministic `doc_id/chunk_id/vector_id` helpers)
  - `app/storage/chroma_vector_store.py` (connect, upsert, query, delete_by_doc_id, count, health)
  - `app/storage/__init__.py` exports
- Enforce embedding dimension checks in store init/upsert.

**Validate**
```powershell
@'
from app.storage.chroma_vector_store import ChromaVectorStore
print("ok")
'@ | python -
```

## Step 4: Centralize embedding generation
**Change**
- Create `app/indexing/embedding_service.py` for provider calls (currently Ollama) and shared `extract_embedding`.
- Remove duplicated embedding extraction logic from:
  - `app/indexing/embedding_indexer.py`
  - `app/retrieval/hybrid_search.py`

**Validate**
```powershell
@'
from app.indexing.embedding_service import extract_embedding
print(callable(extract_embedding))
'@ | python -
```

## Step 5: Migrate ingestion paths to vector upsert
**Change**
- Replace JSONL writes in ingestion with vector upserts.
- Update:
  - `app/ingestion/file_ingest_gui.py`
  - `app/ingestion/email_ingest_job.py`
  - `app/migration/vault_migration.py`
- Add shared ingestion service:
  - `app/ingestion/vector_ingest_service.py` (chunk -> embed -> upsert)
- Implement delete-by-doc operation (service + CLI hook).

**Validate**
```powershell
python -m pytest -q tests\test_smoke_ingest.py
```

## Step 6: Rewrite retrieval to query vector DB
**Change**
- Refactor `app/retrieval/hybrid_search.py`:
  - Replace file loading (`load_chunks`, `load_embeddings`) with vector store queries.
  - Keep `scored_chunks(...)` as primary API for callers.
  - Add optional metadata filter argument (`filters: dict | None`).
  - Keep reranker integration in `app/retrieval/heuristic_reranker.py`.
- Update callers if needed:
  - `app/chat/document_chat_cli.py`
  - `app/chat/document_chat_baseline_cli.py`
  - `app/chat/email_chat_cli.py`
  - `app/chat/streaming_server.py`
  - `eval/run_eval.py`
  - `app/tools/retrieval_debug_cli.py`
  - `app/validation/phase4_validation_cli.py`

**Validate**
```powershell
python -m pytest -q tests\test_smoke_retrieval.py
python -m app.retrieval.hybrid_search --query "payment terms" --top-k 3
```

## Step 7: Add idempotent backfill command
**Change**
- Add `app/migration/backfill_vector_db.py`:
  - Reads old `data/chunks.jsonl` and optional `data/embeddings.jsonl`.
  - Upserts in batches with retries.
  - Supports resume-safe reruns and progress logging.
- Wire optional root shim if needed (or repurpose `index_embeddings.py`).

**Validate**
```powershell
python -m app.migration.backfill_vector_db --batch-size 64
@'
from app.storage.chroma_vector_store import ChromaVectorStore
print({"vector_count": ChromaVectorStore().count()})
'@ | python -
```

## Step 8: Cut over and remove old storage mechanism
**Change**
- Remove old JSONL storage code paths:
  - `app/indexing/embedding_indexer.py` (old append-to-embeddings flow)
  - `load_chunks/load_embeddings` file-based retrieval logic in `app/retrieval/hybrid_search.py`
  - JSONL write helpers in ingestion modules
- Remove obsolete config keys (`vault_file`, `embeddings_file`) and docs references.

**Validate**
```powershell
rg -n "chunks\.jsonl|embeddings\.jsonl|load_embeddings\(|append_embedding\(" app README.md config.yaml
```
(only migration docs/scripts may still mention legacy files)

## Step 9: Add/upgrade tests
**Change**
- Add unit tests:
  - deterministic ID generation
  - metadata mapping/filter-building
  - dimension mismatch hard-fail
- Add integration smoke tests (local Chroma persist dir):
  - ingest -> retrieve -> delete -> retrieve empty
- Update existing tests to avoid file-based assumptions.

**Files**
- `tests/test_vector_ids.py` (new)
- `tests/test_vector_store_smoke.py` (new)
- `tests/test_smoke_ingest.py` (update)
- `tests/test_smoke_retrieval.py` (update)

**Validate**
```powershell
python -m pytest -q
```

## Step 10: Post-cutover verification and docs
**Change**
- Run eval again and compare against baseline.
- Update docs to reflect Chroma-only architecture.

**Files**
- `README.md`
- `AGENTS.md`

**Validate**
```powershell
python eval\run_eval.py --questions eval\questions.jsonl --top-k 6 --output eval\results-post-vector-db.json
python -m pytest -q
```

## Rollback Guidance
If a step breaks:
```powershell
git status
git restore <file1> <file2>
git restore --staged <file1> <file2>
```
To reset all uncommitted changes on your working branch:
```powershell
git reset --hard HEAD
```
(Use only when you intentionally want full rollback.)

## Debug Checklist
- Empty retrieval results: verify Chroma collection name, persist dir, and non-zero `count()`.
- Dimension errors: confirm `embedding_dim` matches model output dimension.
- Duplicate retrieval chunks: verify deterministic `vector_id` and upsert (not add-only).
- Slow ingestion: reduce batch size and inspect Ollama embedding latency.
- Filters not working: inspect metadata types (`str/int`) and generated `where` payload.
- Windows path/lock issues: use writable `vector_db_persist_dir` and avoid concurrent writers in tests.
