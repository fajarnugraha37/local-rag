# Repository Improvement Plan

## Goal
Improve this repository for three outcomes:
1. Reliable operation (fewer runtime failures).
2. Fast ingestion + retrieval on large document collections.
3. Better answer accuracy when using small models (for example 1B with ~8k context).

## High-Priority Fixes (Do First)

### 1) Fix correctness and config issues
- `localrag_no_rewrite.py`: `ollama_chat()` ignores the `vault_embeddings` argument and uses global `vault_embeddings_tensor`. Remove global dependency.
- `localrag.py`: remove hardcoded model/API key values. Load from `config.yaml` or `.env`.
- `emailrag2.py`: in `load_or_generate_embeddings()`, JSON decode failure returns empty tensor without regeneration. Regenerate + resave on decode failure.
- `collect_emails.py`: add robust error handling for IMAP login/fetch/decode failures and skip bad messages safely.
- `localrag.py`: remove `max_context_chars` hard truncation. It can cut evidence mid-sentence and lose key facts.

### 2) Stop full re-embedding on every run
- `localrag.py` currently embeds every chunk at startup.
- Add persistent embedding cache keyed by `(chunk_hash, embedding_model)`.
- Store cache on disk as JSONL/SQLite (prefer SQLite for scale).

### 3) Remove duplicate ingestion
- `upload.py` and `collect_emails.py` append directly into `vault.txt`, causing duplicates across runs.
- Add dedup key (`sha256(normalized_text)` or email `Message-ID`).

## Architecture Upgrades for Large Documents

### 1) Replace `vault.txt` line store with structured chunk store
Use `data/chunks.jsonl` (or SQLite) with:
- `chunk_id`, `doc_id`, `source_path`, `page`, `section`, `text`, `token_count`, `content_hash`, `created_at`.

This enables incremental indexing, traceable citations, and reliable re-indexing.

### 2) Token-aware chunking (not character-only)
Current chunking uses character limits; this is suboptimal for 8k contexts.
- Use token-based chunking (target 300-450 tokens, overlap 50-80).
- Preserve boundaries: heading/paragraph/sentence first, then fallback split.
- Keep source metadata per chunk.

### 3) Build an ANN retrieval index
For scale, avoid full cosine scan on every query.
- Use FAISS/Qdrant/Chroma for vector index.
- Keep a lexical index (BM25) and run hybrid retrieval (lexical + dense).

### 4) Retrieval pipeline for small models
Use a 3-stage pipeline:
1. Retrieve wide: `top_n_dense=40`, `top_n_bm25=40`.
2. Re-rank merged candidates to top 8 (cross-encoder or lightweight reranker).
3. Context pack top 4-6 chunks with token budget.

This improves precision before prompt construction.

### 5) Replace truncation with token-aware packing
Do not truncate raw context by character count. Instead:
- Compute token count per chunk.
- Add full chunks in score order until the evidence budget is full.
- Prefer dropping the lowest-ranked chunk over cutting chunk text.
- If important evidence does not fit, run a second retrieval/answer pass.

## Accuracy Plan for 1B Models with ~8k Context

### 1) Add strict token budgeting (no blind truncation)
Reserve context window explicitly:
- System + instructions: 600-900 tokens
- Conversation memory: 800-1200 tokens
- Retrieved evidence: 3500-4500 tokens
- Answer: 600-900 tokens

Drop oldest chat turns and low-score chunks first, but keep selected evidence chunks intact.

### 2) Context compression before answer generation
For large retrieved text:
- Run extractive compression (sentence selection by relevance) before final answer call.
- Optional map-reduce summary: summarize each chunk, then answer from summaries.
- Compression should be chunk-level and query-aware, not `[:N]` substring truncation.

### 3) Citation-first prompting
Prompt model to cite chunk IDs (`[doc_id:chunk_id]`) per claim.
- If confidence is low (retrieval score below threshold), return "not enough evidence".
- This reduces hallucination and improves trustworthiness.

### 4) Query rewrite safeguards
`localrag.py` rewrite can drift intent.
- Make rewrite optional (`--rewrite on|off`).
- Keep original query and retrieve with both original + rewritten query.
- Merge results with reciprocal-rank fusion.

### 5) Multi-pass answering for 1B/8k
When evidence exceeds budget:
1. Answer pass A using top packed chunks.
2. Retrieve remaining high-score chunks not used in pass A.
3. Run refinement pass B that updates/validates answer with new evidence.

This avoids losing information while staying within small context limits.

## File-by-File Recommendations

### `upload.py`
- Extract reusable chunking/normalization utilities.
- Add CLI mode (`python upload.py --input path --type pdf`) for automation.
- Process PDFs page-by-page in streaming mode; avoid loading huge files entirely in memory.
- Store chunks with metadata instead of plain text append.

### `collect_emails.py`
- Keep UTF-8 text (avoid forced ASCII loss).
- Store `message_id`, `subject`, `from`, `date`, and chunk provenance.
- Add incremental sync (`--since-last-sync`) and dedup by `Message-ID`.

### `emailrag2.py`
- Add stale-index detection (`vault hash` + embedding model hash).
- Batch embedding requests where possible and retry with backoff.
- Add retrieval score threshold and citations in output.

### `localrag.py`
- Move startup embedding generation into shared index module.
- Remove `max_context_chars` truncation and add token-budget context packer.
- Add reranking and context compression steps.

### `localrag_no_rewrite.py`
- Keep as baseline script but align config/loading path with main pipeline.
- Remove debug print of full embedding tensor (expensive/noisy).

## Evaluation & Quality Gates
- Create `eval/questions.jsonl` with representative queries + expected supporting chunks.
- Track metrics per change:
  - Retrieval Recall@k
  - MRR / nDCG for retrieval ranking
  - Answer groundedness (citation coverage)
  - Latency (P50/P95)
- Add `pytest` smoke tests for ingestion, indexing, and query path.

## Suggested Implementation Order
1. Stability patch release: fix bugs, config, dedup, cache regeneration.
2. Indexing refactor: structured chunk store + persistent embeddings + ANN index.
3. Retrieval quality: hybrid retrieval + reranker + token-budget packer.
4. Small-model optimization: compression, citation gating, and eval harness.

## Expected Result
After these changes, the repo should:
- Ingest large corpora incrementally without startup reprocessing.
- Fit relevant evidence into 1B/8k prompts more reliably.
- Produce more accurate, grounded answers with lower hallucination risk.
