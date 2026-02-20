# Repository Guidelines

## Project Structure & Module Organization
- `cmd/app.py`: single launcher for all runtime entrypoints.
- `cmd/server/entrypoint.py`: server-mode wrapper.
- `cmd/cli/entrypoint.py`: CLI-mode wrapper.
- `cmd/actions.py`: shared action registry and dispatch (add new actions here).
- `app/`: core implementation modules (`chat`, `ingestion`, `retrieval`, `storage`, `migration`, `context`, `config`).
- `tests/`: pytest smoke/integration-like tests.
- `eval/run_eval.py`: retrieval evaluation runner.
- `data/chroma/`: persistent Chroma data.

## Build, Test, and Development Commands
- `python .\cmd\app.py --help`: launcher help.
- `python .\cmd\app.py --server --host 127.0.0.1 --port 8000`: start HTTP+SSE server.
- `curl http://127.0.0.1:8000/actions` (or `/action`): list server-exposed actions and HTTP support flags.
- `python .\cmd\app.py --cli --help`: list CLI actions.
- `python .\cmd\app.py --cli chat --top-k 6`: main chat flow.
- `python .\cmd\app.py --cli ingest-files --path .\docs\sample.pdf`: non-GUI ingestion (repeat `--path` for many files, add `--recursive` for directories); omit `--path` to open GUI.
- `curl -X POST http://127.0.0.1:8000/ingest/files -H "Content-Type: application/json" -d "{\"paths\":[\"README.md\"]}"`: server-side path ingestion.
- `curl -X POST http://127.0.0.1:8000/ingest/upload -F "file=@README.md"`: server upload ingestion.
- `python .\cmd\app.py --cli query --query "..." --top-k 6`: retrieval inspection.
- `python -m pytest -q`: test suite.
- `make help`, `make test`, `make eval`, `make all`: standardized workflows.
- Postman collection: `tests/postman/easy-local-rag-server.postman_collection.json`.

## Coding Style & Naming Conventions
- Python: 4-space indentation, PEP 8 naming (`snake_case` functions/modules).
- Keep command wiring thin in `cmd/*`; business logic stays in `app/*`.
- Do not add new root-level entrypoint scripts.
- For new runnable capabilities, add one action in `cmd/actions.py` and call existing `app/*` logic.
- For HTTP APIs, add routes in `app/chat/streaming_server.py` and mirror them in `tests/postman/*`.
- For ingestion formats, register extractors in `app/ingestion/extractors/registry.py` and keep parsing/chunking shared through `app/ingestion/pipeline.py`.

## Testing Guidelines
- Add tests under `tests/` using `test_*.py` naming.
- Add format fixtures/tests under `tests/` when changing ingestion extractors (docs/config/data/office groups).
- For launcher changes, validate:
  - `python .\cmd\app.py --help`
  - `python .\cmd\app.py --server --help`
  - `python .\cmd\app.py --cli --help`
- Run `python -m pytest -q` before PRs.

## Commit & Pull Request Guidelines
- Use imperative commit titles (example: `Centralize launcher under cmd/app.py`).
- Keep PRs scoped to one feature/cutover.
- Include validation commands and outcomes in PR description.

## Security & Configuration Tips
- Keep secrets in `.env`; never commit credentials.
- Prefer config/env keys over hardcoded values.
- Treat `data/chroma/` as sensitive if it contains private document/email content.
- Enforce ingestion limits via `ingest_*` config keys to avoid oversized files and parser abuse.
