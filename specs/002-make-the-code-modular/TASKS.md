# Modularization Tasks Tracker

## Usage
Prompt format for delegation:
- `please follow ALL instruction carefully in specs\002-make-the-code-modular\PLAN.md and do task T001`

Status values:
- `todo` | `doing` | `done` | `blocked`

## Task Index
| ID | Summary | Depends On | Status |
|---|---|---|---|
| T001 | Create `app/` package skeleton and `__init__.py` files | - | done |
| T002 | Move config/common/context/retrieval modules to semantic `app/` paths | T001 | done |
| T003 | Rewrite internal imports in moved core modules to `app.*` absolute imports | T002 | done |
| T004 | Move ingestion/index/migration modules into `app/` and keep `main()` entrypoints | T003 | done |
| T005 | Move chat modules into `app/chat/` and expose `main()` in each CLI module | T003 | done |
| T006 | Move validation/debug scripts into `app/validation` and `app/tools` | T003 | todo |
| T007 | Create root compatibility shims for all existing CLI filenames | T004,T005,T006 | todo |
| T008 | Update tests to import from `app.*` modules | T007 | todo |
| T009 | Update `eval/run_eval.py` imports to `app.*` modules | T007 | todo |
| T010 | Run compile/import smoke checks for package integrity | T008,T009 | todo |
| T011 | Run pytest smoke suite | T010 | todo |
| T012 | Run evaluation command and verify result file generation | T010 | todo |
| T013 | Run entrypoint backward-compatibility smoke commands | T007 | todo |
| T014 | Audit root `.py` files: only approved shims remain | T013 | todo |
| T015 | Update `AGENTS.md` to new modular structure and commands | T014 | todo |
| T016 | Update `README.md` to new package layout and preserved CLI usage | T014 | todo |
| T017 | Final consistency pass across PLAN/IMPROVEMENT/TASKS docs | T015,T016 | todo |

---

## Task Details

### T001
- Goal: Create package directories and initialization files.
- Files to touch: `app/**` (new dirs and `__init__.py` files).
- Acceptance criteria:
  - `app/` and all planned subpackages exist.
  - Each subpackage has `__init__.py`.
- Validate:
```powershell
python -c "import app; print('ok')"
```
- Status: `done`

### T002
- Goal: Move foundational modules to semantic names.
- Files to touch:
  - `settings.py` -> `app/config/runtime_settings.py`
  - `hashing.py` -> `app/common/content_hashing.py`
  - `chunking.py` -> `app/context/token_chunking.py`
  - `context_packer.py` -> `app/context/token_budget_packer.py`
  - `reranker.py` -> `app/retrieval/heuristic_reranker.py`
  - `retrieval.py` -> `app/retrieval/hybrid_search.py`
- Acceptance criteria:
  - Files moved with `git mv`.
  - No duplicate old copies remain (before shim step).
- Validate:
```powershell
python -c "from app.config import runtime_settings; from app.retrieval import hybrid_search; print('ok')"
```
- Status: `done`

### T003
- Goal: Update all core imports to package-qualified imports.
- Files to touch: moved core modules + any modules importing them.
- Acceptance criteria:
  - No root-style imports for moved core modules remain.
- Validate:
```powershell
rg -n "^import (settings|retrieval|chunking|context_packer|reranker|hashing)$|from (settings|retrieval|chunking|context_packer|reranker|hashing)"
```
Expected: no matches.
- Status: `done`

### T004
- Goal: Move ingestion/index/migration modules and preserve executable behavior.
- Files to touch:
  - `upload.py` -> `app/ingestion/file_ingest_gui.py`
  - `collect_emails.py` -> `app/ingestion/email_ingest_job.py`
  - `index_embeddings.py` -> `app/indexing/embedding_indexer.py`
  - `migrate_vault.py` -> `app/migration/vault_migration.py`
- Acceptance criteria:
  - Each module has `main()` + `if __name__ == '__main__': main()`.
- Validate:
```powershell
python -c "from app.ingestion.file_ingest_gui import write_chunks_file; from app.indexing.embedding_indexer import main; print('ok')"
```
- Status: `done`

### T005
- Goal: Move chat CLIs into `app/chat/` and keep runtime flow unchanged.
- Files to touch:
  - `localrag.py` -> `app/chat/document_chat_cli.py`
  - `localrag_no_rewrite.py` -> `app/chat/document_chat_baseline_cli.py`
  - `emailrag2.py` -> `app/chat/email_chat_cli.py`
- Acceptance criteria:
  - Each chat module exposes callable `main()`.
  - CLI arguments still accepted.
- Validate:
```powershell
python -c "from app.chat.document_chat_cli import main; from app.chat.email_chat_cli import main as em; print('ok')"
```
- Status: `done`

### T006
- Goal: Move non-production scripts into semantic locations.
- Files to touch:
  - `phase4_validate.py` -> `app/validation/phase4_validation_cli.py`
  - `debug_retrieval.py` -> `app/tools/retrieval_debug_cli.py`
- Acceptance criteria:
  - No `sys.path.insert(...)` hacks remain.
- Validate:
```powershell
python -c "from app.validation.phase4_validation_cli import main; from app.tools.retrieval_debug_cli import main; print('ok')"
```
- Status: `todo`

### T007
- Goal: Reintroduce root CLI filenames as thin shims only.
- Files to touch: root `localrag.py`, `localrag_no_rewrite.py`, `emailrag2.py`, `upload.py`, `collect_emails.py`, `index_embeddings.py`, `migrate_vault.py`, `retrieval.py`, `phase4_validate.py`, `debug_retrieval.py`.
- Acceptance criteria:
  - Each shim delegates directly to `app...main()` and contains no business logic.
- Validate:
```powershell
Get-Content localrag.py
```
Expected: tiny wrapper only.
- Status: `todo`

### T008
- Goal: Update test imports to package modules.
- Files to touch:
  - `tests/test_smoke_ingest.py`
  - `tests/test_smoke_packer.py`
  - `tests/test_smoke_retrieval.py`
- Acceptance criteria:
  - Tests no longer import moved root modules.
- Validate:
```powershell
rg -n "from (upload|context_packer|chunking) import|^import retrieval" tests
```
Expected: no matches.
- Status: `todo`

### T009
- Goal: Update evaluation runner imports.
- Files to touch: `eval/run_eval.py`.
- Acceptance criteria:
  - Imports use `app.config.runtime_settings` and `app.retrieval.hybrid_search`.
- Validate:
```powershell
python -c "import eval.run_eval as r; print('ok')"
```
- Status: `todo`

### T010
- Goal: Catch syntax/import issues before runtime tests.
- Files to touch: none.
- Acceptance criteria:
  - Package compiles without errors.
- Validate:
```powershell
python -m compileall app
```
- Status: `todo`

### T011
- Goal: Confirm unit/smoke tests still pass after refactor.
- Files to touch: none unless fixes required.
- Acceptance criteria:
  - `pytest` exits with code 0.
- Validate:
```powershell
python -m pytest -q
```
- Status: `todo`

### T012
- Goal: Confirm eval pipeline still works.
- Files to touch: none unless fixes required.
- Acceptance criteria:
  - `eval/results.json` is generated.
- Validate:
```powershell
python eval\run_eval.py --questions eval\questions.jsonl --top-k 6 --output eval\results.json
```
- Status: `todo`

### T013
- Goal: Verify backward-compatible root entrypoint usage.
- Files to touch: none unless shim bug fixes needed.
- Acceptance criteria:
  - Legacy commands still launch and parse args.
- Validate:
```powershell
"quit" | python localrag.py --top-k 2
"quit" | python localrag_no_rewrite.py
"quit" | python emailrag2.py
python retrieval.py --query "banana" --top-k 2
python phase4_validate.py --query "banana" --top-k 2
```
- Status: `todo`

### T014
- Goal: Ensure root code cleanup rule is satisfied.
- Files to touch: none unless violations found.
- Acceptance criteria:
  - No non-shim root Python modules remain.
- Validate:
```powershell
$allowed = @('localrag.py','localrag_no_rewrite.py','emailrag2.py','upload.py','collect_emails.py','index_embeddings.py','migrate_vault.py','retrieval.py','phase4_validate.py','debug_retrieval.py')
Get-ChildItem *.py | Where-Object { $allowed -notcontains $_.Name }
```
Expected: no output.
- Status: `todo`

### T015
- Goal: Update contributor guidance for new module paths.
- Files to touch: `AGENTS.md`.
- Acceptance criteria:
  - Commands and file references point to `app/` package layout.
- Validate:
```powershell
rg -n "app/|app\\" AGENTS.md
```
- Status: `todo`

### T016
- Goal: Update user documentation for modular architecture.
- Files to touch: `README.md`.
- Acceptance criteria:
  - README documents both package paths and legacy shim commands.
- Validate:
```powershell
rg -n "app/|localrag.py|python -m" README.md
```
- Status: `todo`

### T017
- Goal: Keep spec files aligned after execution.
- Files to touch:
  - `specs/002-make-the-code-modular/IMPROVEMENT.md`
  - `specs/002-make-the-code-modular/PLAN.md`
  - `specs/002-make-the-code-modular/TASKS.md`
- Acceptance criteria:
  - Completed tasks are marked accurately and references are consistent.
- Validate:
```powershell
rg -n "T0[0-9]{2}" specs\002-make-the-code-modular\TASKS.md
```
- Status: `todo`
