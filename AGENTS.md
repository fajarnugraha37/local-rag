# Repository Guidelines

## Project Structure & Module Organization
This repo is a local-first Python RAG stack using Ollama and hybrid retrieval.
- `app/chat/document_chat_cli.py`: main CLI chat loop (query rewrite + optional multi-pass refinement).
- `app/chat/document_chat_baseline_cli.py`: baseline chat path without rewrite.
- `app/chat/email_chat_cli.py`: chat flow for email-ingested corpora.
- `app/ingestion/file_ingest_gui.py`, `app/ingestion/email_ingest_job.py`, `app/migration/vault_migration.py`: ingestion and migration utilities.
- `app/indexing/embedding_indexer.py`: incremental embedding indexer for `data/embeddings.jsonl`.
- `app/retrieval/hybrid_search.py`, `app/retrieval/heuristic_reranker.py`, `app/context/token_budget_packer.py`, `app/context/token_chunking.py`, `app/common/content_hashing.py`, `app/config/runtime_settings.py`: retrieval and packing core.
- Root `*.py` entrypoints are compatibility shims that delegate to `app/*` modules.
- `data/`: runtime index artifacts (`chunks.jsonl`, `embeddings.jsonl`, `index_meta.json`).
- `tests/`: smoke tests.
- `eval/`: evaluation dataset, metrics runner, thresholds.
- `specs/001-basic-improvements/`: planning docs.

## Build, Test, and Development Commands
Use Python 3.10+.
- `python -m venv .venv`
- `.\.venv\Scripts\Activate.ps1`
- `pip install -r requirements.txt`
- `python -m app.ingestion.file_ingest_gui`: GUI uploader for PDF/TXT/JSON into `data/chunks.jsonl`.
- `python -m app.ingestion.email_ingest_job --keyword "invoice" --startdate 01.01.2025 --enddate 31.01.2025`: ingest mailbox content.
- `python -m app.migration.vault_migration --vault vault.txt`: migrate legacy vault into structured chunks.
- `python -m app.indexing.embedding_indexer --embedding-model mxbai-embed-large`: generate incremental embeddings.
- `python -m app.chat.document_chat_cli --model gemma3:1b --top-k 6 --multi-pass`: main chat run.
- `python -m app.chat.document_chat_cli --stream --max-continuations 2 --per-call-max-tokens 1024`: main chat run with streaming + continuation.
- `python -m app.chat.document_chat_baseline_cli --stream --max-continuations 2 --per-call-max-tokens 1024`: baseline streaming run.
- `python -m app.chat.email_chat_cli --stream --max-continuations 2 --per-call-max-tokens 1024`: email chat streaming run.
- `python -m app.chat.streaming_server --host 127.0.0.1 --port 8000`: optional SSE server (`/chat/stream`, `/health`).
- `python -m app.retrieval.hybrid_search --query "your question" --top-k 6`: inspect retrieval output.
- `python -m pytest -q`, `make test`, `make eval`, `make all`, or `.\run_all.ps1`.

## Coding Style & Naming Conventions
- 4-space indentation, UTF-8, and PEP 8-compatible formatting.
- Use `snake_case` for variables/functions and concise module-level helpers.
- Keep config in `config.yaml` / `.env`; avoid hardcoded model or endpoint values.
- For chunk/embedding files, keep JSONL format stable (one object per line, deterministic keys).

## Testing Guidelines
- Add tests under `tests/` as `test_smoke_<feature>.py` for fast smoke validation.
- Run `python -m pytest -q` before PRs.
- For retrieval changes, run `python eval/run_eval.py --questions eval/questions.jsonl --top-k 6 --output eval/results.json` and compare with `eval/thresholds.md`.

## Commit & Pull Request Guidelines
- Use concise imperative commit subjects (for example, `Add hybrid retrieval fallback`).
- Keep commits scoped to one logical change.
- PRs should include: summary, affected files, validation commands, and metric changes (if retrieval/eval touched).

## Security & Configuration Tips
- Never commit real credentials in `.env`.
- Supported env overrides include `OLLAMA_MODEL`, `OLLAMA_API_BASE_URL`, `OLLAMA_API_KEY`, `TOP_K`, and email credentials (`GMAIL_*`, `OUTLOOK_*`).
- Streaming env/config controls include `ENABLE_STREAMING`, `ENABLE_THINKING_SUMMARY`, `PER_CALL_MAX_TOKENS`, `MAX_CONTINUATIONS`, `FLUSH_INTERVAL_MS`, `PROVIDER_TIMEOUT_S`, and `CONTINUATION_INSTRUCTION`.
- Treat `data/chunks.jsonl` as sensitive when it contains private documents or email content.
- Thinking summaries should be disabled (`--no-enable-thinking-summary` or `enable_thinking_summary: false`) for stricter privacy/safety requirements.
