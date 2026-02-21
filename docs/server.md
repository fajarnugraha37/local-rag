# Server Reference

Run server:
```powershell
python .\cmd\app.py --server --host 127.0.0.1 --port 8000
```

FastAPI docs:
- `GET /api/docs`
- `GET /api/redoc`

## Endpoint Groups
- Health/system: `/health`, `/healthz`, `/readyz`, `/version`, `/v1/capabilities`, `/v1/config`
- Legacy compatibility: `/actions`, `/docs`, `/chat/stream`, `/ingest/*`, `/retrieval/query`, `/vectors/delete-doc`
- v1 APIs: `/v1/namespaces`, `/v1/documents`, `/v1/ingestions`, `/v1/query`, `/v1/runs`, `/v1/retrieve`, `/v1/rerank`

## SSE Endpoints
- `GET /chat/stream`
- `POST /v1/query/stream`
- `GET /v1/runs/{run_id}/replay`

Typical event names:
- `meta`, `final_delta`, `sources`, `citation_stats`, `done`, `error`

## Notes
- Legacy `GET /docs` remains available for backward compatibility.
- Swagger is intentionally moved away from `/docs` to avoid route collision.
