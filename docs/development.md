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
python .\cmd\app.py --cli --help
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

## Cleanup Utilities
```powershell
make idempotency-purge
make purge-soft-deletes SOFT_DELETE_RETENTION_DAYS=30
```
