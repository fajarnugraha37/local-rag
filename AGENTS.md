# Repository Guidelines

## Project Structure & Module Organization
This repository is a lightweight Python CLI project for local Retrieval-Augmented Generation (RAG) with Ollama.
- `localrag.py`: main document RAG chat loop (with query rewriting).
- `localrag_no_rewrite.py`: simplified chat loop without rewrite step.
- `upload.py`: ingest files (PDF/TXT/JSON) into `vault.txt`.
- `collect_emails.py` and `emailrag2.py`: email ingestion and chat workflows.
- `config.yaml`: runtime defaults for model/API settings.
- `vault.txt`: local knowledge store used by the chat scripts.
- `logs/`: runtime logs.

Keep new modules at repo root unless you introduce a clear package folder (for example, `src/` + `tests/`) in the same PR.

## Build, Test, and Development Commands
Use Python 3.10+ in a virtual environment.
- `python -m venv .venv`
- `.\.venv\Scripts\Activate.ps1`
- `pip install -r requirements.txt`: install runtime dependencies.
- `python upload.py`: load local files into `vault.txt`.
- `python localrag.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest`: run RAG chat with rewrite.
- `python localrag_no_rewrite.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest`: run baseline chat.
- `python collect_emails.py --keyword "invoice" --startdate 01.01.2025 --enddate 31.01.2025`: ingest mailbox data.
- `python emailrag2.py`: chat over ingested email content.

## Coding Style & Naming Conventions
Follow existing Python style:
- 4-space indentation, UTF-8 files, and PEP 8-compatible spacing.
- `snake_case` for functions/variables, `UPPER_CASE` for constants.
- Keep functions small and CLI arguments explicit via `argparse`.
- Prefer simple, script-friendly modules; avoid unnecessary framework structure.

## Testing Guidelines
There is no automated test suite yet.
- Run smoke checks for each changed script with realistic CLI args.
- Validate both happy-path and failure-path behavior (missing files, bad model name, empty vault).
- For new tests, use `pytest` and place them under `tests/` with names like `test_upload.py`.

## Commit & Pull Request Guidelines
Recent history uses short imperative subjects (for example, `Update README.md`, `Update requirements.txt`). Keep that style, but make scope specific when possible.
- Commit message format: `<Verb> <target>` (example: `Improve context truncation in localrag`).
- PRs should include: purpose, key changes, manual test commands run, and any config/env changes.
- Link related issues and include terminal output snippets when behavior changes.

## Security & Configuration Tips
- Never commit real credentials from `.env`.
- Treat `vault.txt` as sensitive if it contains private documents or emails.
- Keep Ollama endpoint/model values in `config.yaml` and environment variables, not hardcoded secrets.