# Development

## Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Common Commands
```powershell
make fmt
make lint
make test
make run-server
make run-cli
make shell
make cli-smoke
make query-verbose Q="what are key payment terms?" TOP_K=6
make config-get
make config-set CONFIG_KEY="general_knowledge_fallback" CONFIG_VALUE=true
```

## Launcher
```powershell
python .\cmd\app.py --cli --help
python .\cmd\app.py --cli --verbose query "what is reclaiming?"
python .\cmd\app.py --server --help
```

## Server Docs
- Swagger: `http://127.0.0.1:8000/api/docs`
- ReDoc: `http://127.0.0.1:8000/api/redoc`

## API Test Targets
```powershell
python -m pytest -q tests/test_fastapi_system_endpoints.py
python -m pytest -q tests/test_fastapi_documents.py tests/test_fastapi_namespaces.py
python -m pytest -q tests/test_fastapi_ingestions.py
python -m pytest -q tests/test_fastapi_query_runs.py tests/test_fastapi_sse.py
python -m pytest -q tests/test_fastapi_retrieve_rerank.py
python -m pytest -q tests/test_fastapi_idempotency.py tests/test_fastapi_pagination.py
```

## CLI Test Targets
```powershell
python -m pytest -q tests/test_cli_basic.py tests/test_cli_pagination.py tests/test_cli_streaming.py tests/test_cli_idempotency.py
```

## Cleanup Utilities
```powershell
make idempotency-purge
make purge-soft-deletes SOFT_DELETE_RETENTION_DAYS=30
```
