# API Reference

FastAPI serves both legacy-compatible routes and new `/v1/*` routes.

## OpenAPI / Swagger
- Swagger UI: `GET /api/docs`
- ReDoc: `GET /api/redoc`

## Health + System
- `GET /health`
- `GET /healthz`
- `GET /readyz`
- `GET /version`
- `GET /v1/capabilities`
- `GET /v1/config`
- `PATCH /v1/config`

## Legacy Compatibility Routes
- `GET /actions`, `GET /action`
- `POST /actions/run`, `POST /action/run`
- `GET /docs`
- `DELETE /docs/{doc_id}`
- `GET /chat/stream` (SSE)
- `POST /ingest/chunks`
- `POST /ingest/text`
- `POST /ingest/files`, `POST /ingestion/files`
- `POST /ingest/folder`
- `POST /ingest/upload`, `POST /ingestion/upload`
- `POST /vectors/delete-doc`
- `POST /retrieval/query`

## Namespaces + Documents
- `GET /v1/namespaces`
- `POST /v1/namespaces`
- `DELETE /v1/namespaces/{namespace}`
- `GET /v1/documents`
- `GET /v1/documents/{namespace}/{doc_id}`
- `DELETE /v1/documents/{namespace}/{doc_id}`
- `POST /v1/documents:bulk_delete`

## Ingestion Jobs
- `POST /v1/ingestions`
- `POST /v1/ingestions/upload`
- `GET /v1/ingestions`
- `GET /v1/ingestions/{ingestion_id}`
- `GET /v1/ingestions/{ingestion_id}/events`
- `POST /v1/ingestions/{ingestion_id}/cancel`

### Ingestion Tuning Fields
Use these fields to improve ingestion throughput:
- `chunk_max_tokens` (int): larger chunks = fewer embeddings.
- `chunk_overlap_tokens` (int): overlap between chunks.
- `ocr_enabled` (bool): when `false`, image files and likely scanned/image-only PDFs are skipped.
- `parallel_workers` (int, folder jobs): number of files processed concurrently.

Example (`POST /v1/ingestions`):
```json
{
  "namespace": "default",
  "source_type": "folder",
  "source_spec": {
    "path": "C:/docs",
    "chunk_max_tokens": 720,
    "chunk_overlap_tokens": 72,
    "ocr_enabled": false,
    "parallel_workers": 4
  }
}
```

## Query + Runs
- `POST /v1/query`
- `POST /v1/query/stream` (SSE)
- `POST /v1/retrieve`
- `POST /v1/rerank`
- `GET /v1/runs/{run_id}`
- `GET /v1/runs/{run_id}/steps`
- `GET /v1/runs/{run_id}/events`
- `GET /v1/runs/{run_id}/replay` (SSE replay)

Notes:
- If `general_knowledge_fallback` is enabled, answers may include an explicitly labeled
  "General knowledge ..." section when sources are thin or missing.

## Idempotency
Mutating endpoints support `Idempotency-Key`:
- same key + same payload -> cached response replayed
- same key + different payload -> `409`

## Pagination + Soft Delete
- Documents and namespaces exclude soft-deleted rows by default.
- Use query flags like `include_deleted=true` where supported.
- Documents list supports stable cursor pagination.
