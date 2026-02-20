# Repository Guidelines

## Project Structure & Module Organization
This repo is a local-first Python RAG stack using Ollama and hybrid retrieval.
- `localrag.py`: main CLI chat loop (query rewrite + optional multi-pass refinement).
- `localrag_no_rewrite.py`: baseline chat path without rewrite.
- `emailrag2.py`: chat flow for email-ingested corpora.
- `upload.py`, `collect_emails.py`, `migrate_vault.py`: ingestion and migration utilities.
- `index_embeddings.py`: incremental embedding indexer for `data/embeddings.jsonl`.
- `retrieval.py`, `reranker.py`, `context_packer.py`, `chunking.py`, `hashing.py`, `settings.py`: retrieval and packing core.
- `data/`: runtime index artifacts (`chunks.jsonl`, `embeddings.jsonl`, `index_meta.json`).
- `tests/`: smoke tests.
- `eval/`: evaluation dataset, metrics runner, thresholds.
- `specs/001-basic-improvements/`: planning docs.

## Build, Test, and Development Commands
Use Python 3.10+.
- `python -m venv .venv`
- `.\.venv\Scripts\Activate.ps1`
- `pip install -r requirements.txt`
- `python upload.py`: GUI uploader for PDF/TXT/JSON into `data/chunks.jsonl`.
- `python collect_emails.py --keyword "invoice" --startdate 01.01.2025 --enddate 31.01.2025`: ingest mailbox content.
- `python migrate_vault.py --vault vault.txt`: migrate legacy vault into structured chunks.
- `python index_embeddings.py --embedding-model mxbai-embed-large`: generate incremental embeddings.
- `python localrag.py --model gemma3:1b --top-k 6 --multi-pass`: main chat run.
- `python retrieval.py --query "your question" --top-k 6`: inspect retrieval output.
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
- Treat `data/chunks.jsonl` as sensitive when it contains private documents or email content.