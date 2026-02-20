# Modularization Improvement Proposal

## Repository Scan (Current State)
Root-level Python modules currently present:
- `chunking.py`, `collect_emails.py`, `context_packer.py`, `debug_retrieval.py`, `emailrag2.py`, `hashing.py`, `index_embeddings.py`, `localrag.py`, `localrag_no_rewrite.py`, `migrate_vault.py`, `phase4_validate.py`, `reranker.py`, `retrieval.py`, `settings.py`, `upload.py`

Observed structure issues:
- Core library code and CLI scripts are mixed at repo root.
- Cross-module imports rely on root module names (`import settings`, `import retrieval`, etc), which becomes fragile during refactors.
- Naming is historical rather than semantic (`emailrag2.py`, `localrag_no_rewrite.py`).
- Debug/validation scripts (`debug_retrieval.py`, `phase4_validate.py`) live beside production modules.
- Tests and eval runner import root modules directly, coupling package layout to the root.

## Target Package Structure (`app/`)

```text
app/
  __init__.py
  config/
    runtime_settings.py
  common/
    content_hashing.py
  context/
    token_chunking.py
    token_budget_packer.py
  retrieval/
    hybrid_search.py
    heuristic_reranker.py
  ingestion/
    file_ingest_gui.py
    email_ingest_job.py
  indexing/
    embedding_indexer.py
  migration/
    vault_migration.py
  chat/
    document_chat_cli.py
    document_chat_baseline_cli.py
    email_chat_cli.py
  validation/
    phase4_validation_cli.py
  tools/
    retrieval_debug_cli.py
```

## Semantic Rename Map (Old -> New)
- `settings.py` -> `app/config/runtime_settings.py`
- `hashing.py` -> `app/common/content_hashing.py`
- `chunking.py` -> `app/context/token_chunking.py`
- `context_packer.py` -> `app/context/token_budget_packer.py`
- `reranker.py` -> `app/retrieval/heuristic_reranker.py`
- `retrieval.py` -> `app/retrieval/hybrid_search.py`
- `upload.py` -> `app/ingestion/file_ingest_gui.py`
- `collect_emails.py` -> `app/ingestion/email_ingest_job.py`
- `index_embeddings.py` -> `app/indexing/embedding_indexer.py`
- `migrate_vault.py` -> `app/migration/vault_migration.py`
- `localrag.py` -> `app/chat/document_chat_cli.py`
- `localrag_no_rewrite.py` -> `app/chat/document_chat_baseline_cli.py`
- `emailrag2.py` -> `app/chat/email_chat_cli.py`
- `phase4_validate.py` -> `app/validation/phase4_validation_cli.py`
- `debug_retrieval.py` -> `app/tools/retrieval_debug_cli.py`

## Refactor Strategy and Constraints
1. Move foundational modules first (`runtime_settings`, hashing, chunking, packer, retrieval, reranker).
2. Convert all imports to explicit absolute package imports (`from app...`).
3. Move ingestion/indexing/chat scripts into `app/` and ensure each has a `main()` entrypoint.
4. Keep root compatibility through thin shims only for existing CLIs (`localrag.py`, `localrag_no_rewrite.py`, `emailrag2.py`, `upload.py`, `collect_emails.py`, `index_embeddings.py`, `migrate_vault.py`, `retrieval.py`, `phase4_validate.py`, `debug_retrieval.py`).
5. Update `tests/` and `eval/run_eval.py` imports to `app.*`.
6. Preserve behavior; only bugfix-level changes allowed (for example import path correctness).

No new heavy dependency is required. Existing runtime should remain `python` + `requirements.txt`.

## Definition of Done
- All non-shim root Python modules are moved under `app/`.
- Existing CLI commands remain usable via root shims.
- `python -m pytest -q` passes.
- `python eval/run_eval.py --questions eval/questions.jsonl --top-k 6 --output eval/results.json` runs.
- README/AGENTS docs reflect the new package paths.

## Non-Goals
- Rewriting retrieval logic, ranking math, or chat behavior.
- Changing config schema or `.env` variable names.
- Introducing a new framework or package manager.

## Risks and Mitigations
- Circular imports after moves.
  - Mitigation: keep `runtime_settings` dependency one-directional; avoid importing chat modules from core layers.
- Broken imports due to partial rename.
  - Mitigation: phase-by-phase move + `rg` checks for old import strings.
- Entry-point regressions.
  - Mitigation: root shim scripts with `main()` delegation and smoke-run using piped `quit`.
- Test/eval drift.
  - Mitigation: run pytest and eval checkpoint after import migration.
- Hidden `sys.path` assumptions (`debug_retrieval.py`).
  - Mitigation: remove manual path injection and rely on package imports.