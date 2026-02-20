# Task Breakdown and Progress Tracker

## How to Use
- Prompt format: `please follow instruction in PLAN.md and do task Txxx`
- Execution rule: do tasks in dependency order unless explicitly marked independent.
- Update tracker: change `Status` to `DONE` only after validation command passes.

## Status Legend
- `TODO`: not started
- `IN_PROGRESS`: actively being implemented
- `DONE`: implemented and validated
- `BLOCKED`: waiting for prerequisite/decision

## Master Tracker
| Task | Phase | Summary | Depends On | Status |
|---|---|---|---|---|
| T101 | 1 | Add shared settings loader (`settings.py`) | - | DONE |
| T102 | 1 | Remove hardcoded config in `localrag.py` | T101 | DONE |
| T103 | 1 | Remove hardcoded config in `localrag_no_rewrite.py` | T101 | DONE |
| T104 | 1 | Fix global tensor bug in `localrag_no_rewrite.py` | T103 | DONE |
| T105 | 1 | Auto-recover corrupted embedding cache in `emailrag2.py` | - | DONE |
| T106 | 1 | Harden IMAP error handling in `collect_emails.py` | - | DONE |
| T107 | 1 | Run Phase 1 validation commands | T102,T103,T104,T105,T106 | DONE |
| T201 | 2 | Create `data/` storage layout and metadata format | T107 | DONE |
| T202 | 2 | Add hashing and dedup utility | T201 | DONE |
| T203 | 2 | Create `migrate_vault.py` for legacy migration | T201,T202 | DONE |
| T204 | 2 | Implement incremental embedding cache/index | T201,T202 | DONE |
| T205 | 2 | Refactor `upload.py` to structured chunk writes | T202 | DONE |
| T206 | 2 | Refactor `collect_emails.py` to structured chunk writes | T202,T106 | DONE |
| T207 | 2 | Run Phase 2 validation commands | T203,T204,T205,T206 | DONE |
| T301 | 3 | Add token-aware chunking module (`chunking.py`) | T207 | DONE |
| T302 | 3 | Add hybrid retrieval (dense + BM25 + RRF) | T301 | DONE |
| T303 | 3 | Add cheap reranker (heuristic default) | T302 | DONE |
| T304 | 3 | Return scored chunk objects with metadata | T302,T303 | DONE |
| T305 | 3 | Run Phase 3 validation commands | T304 | DONE |
| T401 | 4 | Remove `max_context_chars` truncation path | T305 | DONE |
| T402 | 4 | Add token-budget context packer (`context_packer.py`) | T401 | DONE |
| T403 | 4 | Add multi-pass answering (A/B refinement) | T402 | DONE |
| T404 | 4 | Add citation output format `[doc_id:chunk_id]` | T402 | DONE |
| T405 | 4 | Run Phase 4 validation commands | T403,T404 | TODO |
| T501 | 5 | Create `eval/questions.jsonl` benchmark set | T405 | TODO |
| T502 | 5 | Implement `eval/run_eval.py` metrics runner | T501 | TODO |
| T503 | 5 | Add `pytest` smoke tests for ingestion/retrieval/packing | T405 | TODO |
| T504 | 5 | Add repeatable run scripts (`Makefile` or `.ps1`) | T502,T503 | TODO |
| T505 | 5 | Run full quality gates and document thresholds | T502,T503,T504 | TODO |

## Task Cards

### T101
- Objective: Centralize config loading from `config.yaml` + `.env`.
- Files: `settings.py`, `localrag.py`, `localrag_no_rewrite.py`, `emailrag2.py`.
- Done when: all runtime settings come from shared loader, no hardcoded API key/model defaults in code.

### T102
- Objective: Replace hardcoded client/model settings in `localrag.py`.
- Done when: script works with config/env only.
- Validate: `python localrag.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest`

### T103
- Objective: Replace hardcoded client/model settings in `localrag_no_rewrite.py`.
- Done when: script uses shared settings path.
- Validate: `python localrag_no_rewrite.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest`

### T104
- Objective: Fix `ollama_chat()` to use passed `vault_embeddings` argument, not global tensor.
- Done when: no global reference inside retrieval call path.

### T105
- Objective: In `emailrag2.py`, corrupted embedding cache regenerates and persists automatically.
- Done when: invalid embeddings file no longer breaks startup.
- Validate: `python emailrag2.py --clear-cache`

### T106
- Objective: Add robust IMAP login/fetch/decode exception handling.
- Done when: bad email/login does not crash full sync.
- Validate: `python collect_emails.py --keyword "test"`

### T201-T207
- Objective: Incremental indexing and structured storage.
- Files: `data/chunks.jsonl`, `data/embeddings.sqlite` (or `jsonl`), `data/index_meta.json`, `migrate_vault.py`.
- Done when: re-runs do not duplicate chunks and only new/changed chunks are embedded.
- Validate:
```powershell
python migrate_vault.py
python upload.py
python emailrag2.py --clear-cache
```

### T301-T305
- Objective: Cheap retrieval quality upgrade (token chunking, hybrid retrieval, heuristic rerank).
- Done when: retrieval returns ranked chunk objects with scores and metadata.
- Validate:
```powershell
python localrag.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest --top-k 6
python localrag.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest --top-k 6 --rewrite off
```

### T401-T405
- Objective: Remove truncation and implement token-budget packing + multi-pass answering.
- Rule: never use character slicing for evidence (`max_context_chars` path removed).
- Done when: context is packed by token budget and overflow evidence handled by second pass.
- Validate:
```powershell
python localrag.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest --top-k 8 --rewrite on
python localrag.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest --top-k 8 --rewrite off
```

### T501-T505
- Objective: Add eval + tests + repeatable commands.
- Metrics: Recall@k, MRR, citation coverage, P50/P95 latency.
- Done when: local eval and smoke tests run and thresholds are documented.
- Validate:
```powershell
pytest -q
python eval/run_eval.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest
```

## Quick Start Sequence
1. Complete `T101` through `T107`.
2. Complete `T201` through `T207`.
3. Complete `T301` through `T305`.
4. Complete `T401` through `T405`.
5. Complete `T501` through `T505`.
