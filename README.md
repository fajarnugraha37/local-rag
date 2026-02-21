# Easy Local RAG

Local-first RAG with FastAPI server, Docling-based ingestion, and hybrid retrieval.

## Entrypoint
```powershell
python .\cmd\app.py --server [args]
python .\cmd\app.py --cli [args]
```

## Server
```powershell
python .\cmd\app.py --server --host 127.0.0.1 --port 8000
```

Docs:
- Swagger: `http://127.0.0.1:8000/api/docs`
- ReDoc: `http://127.0.0.1:8000/api/redoc`

Key routes:
- Legacy compatibility: `/actions`, `/docs`, `/chat/stream`, `/ingest/*`, `/retrieval/query`
- v1 APIs: `/v1/namespaces`, `/v1/documents`, `/v1/ingestions`, `/v1/query`, `/v1/runs`, `/v1/retrieve`, `/v1/rerank`

## CLI
```powershell
python .\cmd\app.py --cli --help
```

## Make targets
```powershell
make help
make fmt
make lint
make test
make run-server
make idempotency-purge
make purge-soft-deletes SOFT_DELETE_RETENTION_DAYS=30
```

## Docs
- `docs/api.md`
- `docs/server.md`
- `docs/architecture.md`
- `docs/configuration.md`
- `docs/development.md`
- `docs/cli.md`
