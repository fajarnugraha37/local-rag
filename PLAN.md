# Implementation Plan (Cheap-AI Ready)

## Scope and Constraints
This plan implements `IMPROVEMENT.md` with a strict low-cost setup:
- Local-first (`Ollama`) and no paid APIs.
- Target hardware: CPU or low-VRAM GPU, 8-16 GB RAM.
- Target generation models: `gemma3:1b` or `qwen2.5:1.5b-instruct`.
- Context window assumption: ~8k tokens.
- Primary goal: no information loss from naive truncation.

## Delivery Strategy
Work in 5 phases. Each phase is deployable and testable on its own.

## Phase 1: Stability and Config Hygiene
### Goals
- Remove hardcoded model/API values.
- Fix correctness bugs and failure handling.
- Keep behavior backward-compatible.

### Tasks
1. Update `localrag.py` and `localrag_no_rewrite.py` to load model/base URL from `config.yaml` and `.env`.
2. Fix `localrag_no_rewrite.py` global-tensor bug (`ollama_chat` must use its function args).
3. Fix `emailrag2.py` embedding-cache decode path: regenerate and resave when cache is corrupted.
4. Add guarded IMAP error handling in `collect_emails.py` for login, fetch, and decode failures.
5. Add one shared `settings` loader utility (new file: `settings.py`).

### Acceptance Criteria
- Scripts run without hardcoded secrets.
- Corrupted embedding cache auto-recovers.
- Email sync continues when one message fails.

### Validation Commands
```powershell
python localrag.py --model gemma3:1b
python localrag_no_rewrite.py --model gemma3:1b
python emailrag2.py --clear-cache
python collect_emails.py --keyword "test"
```

## Phase 2: Data Model and Incremental Indexing
### Goals
- Support large corpora without full reprocessing each run.
- Preserve provenance per chunk.

### Tasks
1. Introduce storage layout:
- `data/chunks.jsonl`
- `data/embeddings.sqlite` (or `data/embeddings.jsonl` if SQLite deferred)
- `data/index_meta.json`
2. Add migration script `migrate_vault.py` to convert `vault.txt` into chunk records with metadata.
3. Implement dedup via `sha256(normalized_text)`.
4. Implement incremental embedding pipeline:
- Only embed new/changed chunks.
- Key cache by `(content_hash, embedding_model)`.
5. Update `upload.py` and `collect_emails.py` to write structured chunks instead of raw append-only text.

### Acceptance Criteria
- Re-running ingestion does not duplicate data.
- Startup no longer embeds everything from scratch.
- Chunk records include `chunk_id`, `doc_id`, `source`, and `token_count`.

### Validation Commands
```powershell
python migrate_vault.py
python upload.py
python emailrag2.py --clear-cache
```

## Phase 3: Retrieval Pipeline for Small Models
### Goals
- Improve retrieval precision before answer generation.
- Keep runtime affordable.

### Tasks
1. Add token-aware chunking utility (`chunking.py`):
- Target 300-450 tokens/chunk, overlap 50-80.
- Preserve paragraph/sentence boundaries when possible.
2. Add hybrid retrieval (`retrieval.py`):
- Dense retrieval using existing embeddings.
- Lexical retrieval (BM25).
- Merge by reciprocal-rank fusion (RRF).
3. Add cheap rerank stage:
- Default: heuristic reranker (cosine + keyword overlap).
- Optional: lightweight reranker model when available.
4. Return scored chunk objects with metadata for downstream packing.

### Acceptance Criteria
- Retrieval returns better-focused evidence than dense-only baseline.
- No large latency jump on CPU-only runs.

### Validation Commands
```powershell
python localrag.py --model gemma3:1b --top-k 6
python localrag.py --model gemma3:1b --top-k 6 --rewrite off
```

## Phase 4: Context Packing Without Truncation
### Goals
- Remove `max_context_chars` slicing.
- Preserve complete evidence chunks.

### Tasks
1. Remove `max_context_chars` logic from `localrag.py`.
2. Add token-budget context packer (`context_packer.py`):
- Reserve budget by role:
  - Instructions: 600-900
  - Conversation memory: 800-1200
  - Evidence: 3500-4500
  - Answer: 600-900
- Add full chunks in rank order until budget is full.
- Drop lowest-scored chunks instead of cutting text.
3. Add multi-pass answering mode:
- Pass A: answer from packed top evidence.
- Pass B: fetch unused high-score chunks and refine answer.
4. Add citation format in final answer (`[doc_id:chunk_id]`).

### Acceptance Criteria
- No substring truncation of context.
- Long evidence handled by packing + second pass.
- Responses include citations to source chunks.

### Validation Commands
```powershell
python localrag.py --model gemma3:1b --top-k 8 --rewrite on
python localrag.py --model gemma3:1b --top-k 8 --rewrite off
```

## Phase 5: Evaluation, Testing, and Release Hardening
### Goals
- Make quality measurable.
- Prevent regressions.

### Tasks
1. Add `eval/questions.jsonl` with real queries and expected supporting chunks.
2. Add `eval/run_eval.py` to compute:
- Retrieval Recall@k
- MRR
- Citation coverage
- Latency (P50/P95)
3. Add `pytest` smoke tests:
- Ingestion/dedup
- Incremental indexing
- Retrieval returns non-empty evidence
- Context packer respects token budgets
4. Add `Makefile` or script aliases for repeatable runs.

### Acceptance Criteria
- Evaluation runs locally and outputs metrics JSON.
- Smoke tests pass in CI/local.
- Regression threshold documented.

### Validation Commands
```powershell
pytest -q
python eval/run_eval.py --model gemma3:1b
```

## Cheap-AI Runtime Defaults
Use these defaults after implementation:
- Generation model: `gemma3:1b`.
- Embedding model: keep `mxbai-embed-large` initially, add optional smaller embedding model flag for low-RAM setups.
- Retrieval: `top_n_dense=30`, `top_n_bm25=30`, rerank to `top_k=6`.
- Conversation memory: rolling window only (last N turns within budget).

## Suggested Execution Order (Runnable)
1. Implement Phase 1 and release as `v1.4-stability`.
2. Implement Phase 2 migration and indexing as `v1.5-index`.
3. Implement Phase 3 + 4 retrieval/packing as `v1.6-small-model-rag`.
4. Implement Phase 5 evaluation and tests as `v1.7-quality-gates`.

## Risks and Mitigations
- Risk: latency increase from hybrid retrieval.
- Mitigation: keep heuristic reranker default, optional model reranker.

- Risk: migration complexity from `vault.txt`.
- Mitigation: keep read-compatible fallback during one release cycle.

- Risk: small-model hallucinations.
- Mitigation: citation-required prompting and low-confidence fallback response.

## Definition of Done
The plan is complete when:
1. Context slicing/truncation is removed.
2. Large-document ingestion is incremental and deduplicated.
3. 1B/8k model answers are grounded with citations.
4. Eval metrics and smoke tests are runnable locally.