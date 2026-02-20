# Plan - Centralized Entrypoint Cutover

## Preconditions
- Run from repo root.
- Python env has dependencies from `requirements.txt`.

## Step 1: Inventory and Freeze Old Entrypoints
- Confirm all legacy launchers and call sites.
- Files to inspect: root `*.py` script shims, `app/*` modules with `if __name__ == "__main__"`, `Makefile`, `README.md`, `AGENTS.md`.
- Validation:
  - `rg --line-number "__main__" -g "*.py"`

## Step 2: Add New Launcher Layer Under `cmd/`
- Create:
  - `cmd/app.py` (single dispatcher)
  - `cmd/actions.py` (shared action registry + execution)
  - `cmd/server/entrypoint.py` (server wrapper)
  - `cmd/cli/entrypoint.py` (CLI wrapper)
- Design:
  - `--server` and `--cli` are mutually exclusive.
  - Delegate mode-specific args without mangling.
  - `--help` works for launcher and pass-through mode help.
- Validation:
  - `python .\cmd\app.py --help`
  - `python .\cmd\app.py --server --help`
  - `python .\cmd\app.py --cli --help`

## Step 3: Wire Actions and Remove Duplicated Entrypoint Logic
- Register all previous runnable actions in `cmd/actions.py`:
  - server, chat, chat-baseline, chat-email, ingest-files, ingest-email, migrate-vault, backfill-vectors, query, validate-phase4, debug-retrieval, eval.
- Remove `if __name__ == "__main__"` blocks from action modules to enforce centralized execution.
- Validation:
  - `python .\cmd\app.py --cli query --help`
  - `python .\cmd\app.py --cli chat --help`

## Step 4: Remove Legacy Root Entrypoint Scripts
- Delete root files:
  - `localrag.py`, `localrag_no_rewrite.py`, `emailrag2.py`, `upload.py`, `collect_emails.py`, `migrate_vault.py`, `index_embeddings.py`, `retrieval.py`, `phase4_validate.py`, `debug_retrieval.py`.
- Validation:
  - `Get-ChildItem *.py`

## Step 5: Update Build/Run Surfaces
- Update `Makefile` so all app workflows call `python cmd\app.py --server|--cli`.
- Replace old run instructions in `README.md` and `AGENTS.md` with unified launcher examples.
- Validation:
  - `make help`
  - `make run-cli`

## Step 6: Smoke + Regression Validation
- Server smoke:
  - `python .\cmd\app.py --server --host 127.0.0.1 --port 8010`
  - Check startup logs; optional `Invoke-WebRequest http://127.0.0.1:8010/health` in another shell.
- CLI smoke (representative):
  - `python .\cmd\app.py --cli query --query "test" --top-k 1`
  - `python .\cmd\app.py --cli eval --questions eval\questions.jsonl --top-k 1 --output eval\results-spec005.json`
- Test suite:
  - `python -m pytest -q`

## Rollback
- Inspect current diff: `git status --short`
- Revert feature safely: `git restore .`
- If deletions must be recovered selectively: `git restore <path>`

## Debug Checklist
- `--server --help` shows launcher help instead of server help: verify help forwarding logic in `cmd/app.py`.
- Unknown action errors: confirm action key exists in `cmd/actions.py`.
- Args not reaching action parser: confirm `run_action()` resets `sys.argv` with passthrough args.
- Import errors from launcher: ensure `cmd/app.py` prepends repo root path when run as script.
