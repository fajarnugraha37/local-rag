# Spec 005 - Centralized Entrypoint Implementations

## Current State (Repo Scan)
Before cutover, runtime entrypoints were split across many files:
- Root script shims: `localrag.py`, `localrag_no_rewrite.py`, `emailrag2.py`, `upload.py`, `collect_emails.py`, `migrate_vault.py`, `index_embeddings.py`, `retrieval.py`, `phase4_validate.py`, `debug_retrieval.py`.
- Server entrypoint lived in `app/chat/streaming_server.py`.
- CLI actions lived in separate modules with independent `argparse` parsers:
  - chat: `app/chat/document_chat_cli.py`, `app/chat/document_chat_baseline_cli.py`, `app/chat/email_chat_cli.py`
  - ingestion/migration: `app/ingestion/file_ingest_gui.py`, `app/ingestion/email_ingest_job.py`, `app/migration/vault_migration.py`, `app/migration/backfill_vector_db.py`
  - retrieval/tools/eval: `app/retrieval/hybrid_search.py`, `app/validation/phase4_validation_cli.py`, `app/tools/retrieval_debug_cli.py`, `eval/run_eval.py`
- `Makefile` only had `test`, `eval`, `all` and did not expose a unified app run contract.

## Pain Points
- Too many script surfaces to maintain and document.
- Hard to add a web UI adapter because command contracts are fragmented.
- Duplicate entrypoint logic across root shims and module `__main__` blocks.

## Target Structure and Command Contract
```
cmd/
  app.py
  actions.py
  cli/entrypoint.py
  server/entrypoint.py
```
Only supported execution:
- `python .\cmd\app.py --server [server args]`
- `python .\cmd\app.py --cli [action args]`

## Mapping (Old -> New)
- `python localrag.py ...` -> `python .\cmd\app.py --cli chat ...`
- `python localrag_no_rewrite.py ...` -> `python .\cmd\app.py --cli chat-baseline ...`
- `python emailrag2.py ...` -> `python .\cmd\app.py --cli chat-email ...`
- `python upload.py` -> `python .\cmd\app.py --cli ingest-files`
- `python collect_emails.py ...` -> `python .\cmd\app.py --cli ingest-email ...`
- `python migrate_vault.py ...` -> `python .\cmd\app.py --cli migrate-vault ...`
- `python index_embeddings.py ...` -> `python .\cmd\app.py --cli backfill-vectors ...`
- `python retrieval.py ...` -> `python .\cmd\app.py --cli query ...`
- `python phase4_validate.py ...` -> `python .\cmd\app.py --cli validate-phase4 ...`
- `python debug_retrieval.py` -> `python .\cmd\app.py --cli debug-retrieval`
- `python -m app.chat.streaming_server ...` -> `python .\cmd\app.py --server ...`

## Definition of Done
- `cmd/app.py` is the single launcher for all runtime actions.
- Old root entrypoint files are removed.
- App/action modules are no longer directly executable via `__main__` blocks.
- `Makefile`, `README.md`, and `AGENTS.md` use only the new launcher.
- Help and smoke runs pass: launcher help, server help/start, representative CLI actions, tests.

## Non-Goals
- Adding authentication for server routes.
- Changing core retrieval/chat behavior.
- Rewriting business logic in `app/*`.

## Risks and Mitigations
- Arg pass-through bugs: use `parse_known_args` in `cmd/app.py` and delegate untouched tail args.
- Import path issues when running as script: `cmd/app.py` injects repo root into `sys.path` before importing launcher modules.
- Hidden breaking changes in docs/make targets: enforce explicit mapping + smoke validation commands.
