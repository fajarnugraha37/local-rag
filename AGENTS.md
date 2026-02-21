# Repository Guidelines

## Project Structure & Module Organization
- `cmd/app.py`: single launcher.
- `cmd/actions.py`: action registry and dispatch.
- `app/http/fastapi_app.py`: FastAPI app factory.
- `app/http/fastapi_server.py`: uvicorn runner used by `--server`.
- `app/http/routers/*`: endpoint routers (legacy + `/v1/*`).
- `app/http/middleware/*`: request id and idempotency middleware.
- `app/http/sse_utils.py`: SSE frame utility.
- `app/services/*`: API orchestration services.
- `app/repositories/sqlite/*`: sqlite persistence layer.
- `app/ingestion/*`, `app/document_conversion/*`, `app/retrieval/*`, `app/storage/*`: core RAG pipeline.
- `tests/*`: pytest suite.

## Build, Test, and Development Commands
- `python .\cmd\app.py --server --help`
- `python .\cmd\app.py --cli --help`
- `make fmt`
- `make lint`
- `make test`
- `make run-server`

## Coding Style & Naming Conventions
- Python 3.10+
- 4 spaces, `snake_case`
- Keep router functions thin and place orchestration in `app/services/*`.

## Testing Guidelines
- Add tests under `tests/` as `test_fastapi_*.py` for API behavior.
- Run targeted tests first, then full suite (`python -m pytest -q`).

## Commit & Pull Request Guidelines
- Small, scoped commits per task.
- Include validation commands and results in PR notes.

## Security & Configuration Tips
- Do not commit credentials.
- Use `config.yaml` + env overrides.
- Use idempotency and soft-delete purge controls for server maintenance:
  - `make idempotency-purge`
  - `make purge-soft-deletes SOFT_DELETE_RETENTION_DAYS=30`
