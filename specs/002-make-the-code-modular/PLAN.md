# Runnable Modularization Plan

## Execution Status
This plan has been executed through Phase H in the current branch/worktree.
Refer to `specs/002-make-the-code-modular/TASKS.md` for per-task completion states (`T001`-`T017`).

## Preflight
Repository facts detected from scan:
- Tests present: `tests/test_smoke_ingest.py`, `tests/test_smoke_packer.py`, `tests/test_smoke_retrieval.py`
- Eval runner present: `eval/run_eval.py`
- No lint/typecheck config detected: no `pyproject.toml`, `ruff.toml`, `mypy.ini`, `setup.cfg`

Create a working branch first:
```powershell
git switch -c refactor/modular-app
```

## Phase A: Create Package Skeleton
1. Create package directories and `__init__.py` files.
```powershell
New-Item -ItemType Directory -Force app, app\config, app\common, app\context, app\retrieval, app\ingestion, app\indexing, app\migration, app\chat, app\validation, app\tools | Out-Null
@('__init__.py','config\__init__.py','common\__init__.py','context\__init__.py','retrieval\__init__.py','ingestion\__init__.py','indexing\__init__.py','migration\__init__.py','chat\__init__.py','validation\__init__.py','tools\__init__.py') | ForEach-Object { New-Item -ItemType File -Force (Join-Path 'app' $_) | Out-Null }
```
2. Checkpoint:
```powershell
python -c "import app; print('app package ok')"
```

## Phase B: Move Core Modules (No CLI Yet)
1. Move files with semantic names.
```powershell
git mv settings.py app\config\runtime_settings.py
git mv hashing.py app\common\content_hashing.py
git mv chunking.py app\context\token_chunking.py
git mv context_packer.py app\context\token_budget_packer.py
git mv reranker.py app\retrieval\heuristic_reranker.py
git mv retrieval.py app\retrieval\hybrid_search.py
```
2. Update imports across repo:
- `import settings` -> `from app.config import runtime_settings as settings`
- `from hashing import ...` -> `from app.common.content_hashing import ...`
- `from chunking import ...` -> `from app.context.token_chunking import ...`
- `import reranker` -> `from app.retrieval import heuristic_reranker as reranker`
- `import retrieval` -> `from app.retrieval import hybrid_search as retrieval`
3. Checkpoint:
```powershell
python -c "from app.retrieval import hybrid_search; from app.context import token_budget_packer; print('core imports ok')"
```

## Phase C: Move Ingestion/Index/Migration
1. Move modules.
```powershell
git mv upload.py app\ingestion\file_ingest_gui.py
git mv collect_emails.py app\ingestion\email_ingest_job.py
git mv index_embeddings.py app\indexing\embedding_indexer.py
git mv migrate_vault.py app\migration\vault_migration.py
```
2. Update imports in these files to `app.*` absolute imports.
3. Ensure each file has `def main(): ...` and `if __name__ == '__main__': main()`.
4. Checkpoint:
```powershell
python -c "from app.ingestion.file_ingest_gui import write_chunks_file; from app.indexing.embedding_indexer import main as i_main; print('ingestion/index imports ok')"
```

## Phase D: Move Chat/Validation/Tool Scripts
1. Move modules.
```powershell
git mv localrag.py app\chat\document_chat_cli.py
git mv localrag_no_rewrite.py app\chat\document_chat_baseline_cli.py
git mv emailrag2.py app\chat\email_chat_cli.py
git mv phase4_validate.py app\validation\phase4_validation_cli.py
git mv debug_retrieval.py app\tools\retrieval_debug_cli.py
```
2. Ensure chat CLIs expose `main()` to be callable from shims.
3. Update imports to `app.*`.
4. Checkpoint:
```powershell
python -c "from app.chat.document_chat_cli import main as chat_main; from app.chat.email_chat_cli import main as email_main; print('chat imports ok')"
```

## Phase E: Add Root Compatibility Shims
Create thin root shims (same filenames as before) that only delegate to `app`:
- `localrag.py` -> `app.chat.document_chat_cli.main`
- `localrag_no_rewrite.py` -> `app.chat.document_chat_baseline_cli.main`
- `emailrag2.py` -> `app.chat.email_chat_cli.main`
- `upload.py` -> `app.ingestion.file_ingest_gui.main`
- `collect_emails.py` -> `app.ingestion.email_ingest_job.main`
- `index_embeddings.py` -> `app.indexing.embedding_indexer.main`
- `migrate_vault.py` -> `app.migration.vault_migration.main`
- `retrieval.py` -> `app.retrieval.hybrid_search` CLI `main`
- `phase4_validate.py` -> `app.validation.phase4_validation_cli.main`
- `debug_retrieval.py` -> `app.tools.retrieval_debug_cli.main`

Checkpoint command:
```powershell
Get-ChildItem *.py | Select-Object -ExpandProperty Name
```
Expected: only shim scripts at root (plus docs/scripts that are intentionally non-module).

## Phase F: Update Tests, Eval, and Scripts
1. Update imports:
- `tests/test_smoke_ingest.py`: `from app.ingestion.file_ingest_gui import write_chunks_file`
- `tests/test_smoke_packer.py`: `from app.context.token_budget_packer import pack_context`; `from app.context.token_chunking import estimate_token_count`
- `tests/test_smoke_retrieval.py`: `from app.retrieval import hybrid_search as retrieval`
- `eval/run_eval.py`: import settings/retrieval from `app.*`
2. Update `run_all.ps1`/`Makefile` only if command paths changed.

Checkpoint:
```powershell
python -m pytest -q
python eval\run_eval.py --questions eval\questions.jsonl --top-k 6 --output eval\results.json
```

## Phase G: Runtime Smoke Checks
Run non-interactive smoke checks for entrypoint compatibility:
```powershell
"quit" | python localrag.py --top-k 2
"quit" | python localrag_no_rewrite.py
"quit" | python emailrag2.py
python retrieval.py --query "banana" --top-k 2
python phase4_validate.py --query "banana" --top-k 2
```

## Phase H: Documentation Sync
Update docs to new package paths:
- `AGENTS.md`
- `README.md`

## Lint/Typecheck Checkpoint
No lint/typecheck tool configured in current repo scan. Skip unless tooling is added during refactor.

## Rollback Guidance
- After each phase, commit a checkpoint:
```powershell
git add -A
git commit -m "refactor: phase X modular move"
```
- Roll back one phase safely:
```powershell
git revert <checkpoint_commit_sha>
```
- Discard uncommitted work for a specific file:
```powershell
git restore <path>
```

## Debugging Tips
- Find stale imports quickly:
```powershell
rg -n "^import (settings|retrieval|chunking|context_packer|reranker|hashing)$|from (settings|retrieval|chunking|context_packer|reranker|hashing)"
```
- Detect accidental non-shim root modules:
```powershell
$allowed = @('localrag.py','localrag_no_rewrite.py','emailrag2.py','upload.py','collect_emails.py','index_embeddings.py','migrate_vault.py','retrieval.py','phase4_validate.py','debug_retrieval.py')
Get-ChildItem *.py | Where-Object { $allowed -notcontains $_.Name }
```
- Validate package import graph:
```powershell
python -m compileall app
```
