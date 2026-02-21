# Repository Guidelines

## Project Structure & Module Organization
- `cmd/app.py`: single launcher for all runtime entrypoints.
- `cmd/server/entrypoint.py`: server-mode wrapper.
- `cmd/cli/entrypoint.py`: CLI-mode wrapper.
- `cmd/actions.py`: shared action registry and dispatch (add new actions here).
- `app/http/`: HTTP/SSE server bootstrap, request parsing, and route handlers.
- `app/chat/`: chat orchestration and CLI wrappers (server compatibility entrypoint remains in `app/chat/streaming_server.py`).
- `app/ingestion/`: extraction, scanning, pipeline and ingestion services.
- `app/cli/`: thin CLI wrappers for ingestion commands.
- `app/embeddings/`: canonical embedding service module.
- `app/`: other core implementation modules (`retrieval`, `storage`, `migration`, `context`, `config`, `logging`).
- `tests/`: pytest smoke/integration-like tests.
- `eval/run_eval.py`: retrieval evaluation runner.
- `data/chroma/`: persistent Chroma data.
- `docs/`: canonical documentation set (`architecture`, `rag-pipeline`, `configuration`, `development`, `cli`, `server`, `contributing`).

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
- For HTTP APIs, add routes in `app/http/handlers/*` and wire dispatch in `app/http/server.py` (keep `app/chat/streaming_server.py` as compatibility shell).
- For ingestion formats, register extractors in `app/ingestion/extractors/registry.py` and keep parsing/chunking shared through `app/ingestion/pipeline.py`.
- For document formats in spec 011 scope, add support through `app/document_conversion/docling_adapter.py` and docling extractor routing, not legacy per-format parsers.

## Module Boundaries
- Keep orchestration/presentation in wrapper modules (`cmd/*`, `app/cli/*`, `app/chat/*` CLI files).
- Keep reusable business logic in service modules (`app/http/handlers/*`, `app/ingestion/*`, `app/retrieval/*`, `app/embeddings/*`).
- Preserve compatibility import paths when moving modules (add shims instead of breaking old imports).
- Keep HTTP response envelopes consistent (`ok` + `error` on failures).

## Testing Guidelines
- Add tests under `tests/` using `test_*.py` naming.
- Add format fixtures/tests under `tests/` when changing ingestion extractors (docs/config/data/office groups).
- For launcher changes, validate:
  - `python .\cmd\app.py --help`
  - `python .\cmd\app.py --server --help`
  - `python .\cmd\app.py --cli --help`
- Run `python -m pytest -q` before PRs.

## Validation Sequence
- For CLI/server contract changes, run:
  - `python .\cmd\app.py --help`
  - `python .\cmd\app.py --cli --help`
  - `python .\cmd\app.py --server --help`
- For quality gate:
  - `make fmt`
  - `make lint`
  - `make test`
- Add targeted tests for touched modules before full test suite.

## Commit & Pull Request Guidelines
- Use imperative commit titles (example: `Centralize launcher under cmd/app.py`).
- Keep PRs scoped to one feature/cutover.
- Include validation commands and outcomes in PR description.
- Prefer safe, small diffs that preserve behavior unless behavior change is explicitly required.

## Security & Configuration Tips
- Keep secrets in `.env`; never commit credentials.
- Prefer config/env keys over hardcoded values.
- Treat `data/chroma/` as sensitive if it contains private document/email content.
- Enforce ingestion limits via `ingest_*` config keys to avoid oversized files and parser abuse.
