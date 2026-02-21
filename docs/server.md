# Server Reference

Launch server:
```powershell
python .\cmd\app.py --server --host 127.0.0.1 --port 8000
```

## Main Endpoints
- `GET /health`
- `GET /actions` and `GET /action`
- `GET /docs`
- `GET /chat/stream`
- `POST /ingest/chunks`
- `POST /ingest/text`
- `POST /ingest/files`
- `POST /ingest/folder`
- `POST /ingest/upload`
- `POST /vectors/delete-doc`
- `POST /retrieval/query`
- `POST /actions/run`
- `DELETE /docs/{doc_id}`

## Response Shape
- Success payloads include `ok: true` where applicable.
- Error payloads include `ok: false` and `error` message.

## SSE Notes (`/chat/stream`)
- Emits streamed delta events and completion events.
- Emits `sources` and `citation_stats` events on completion.
- Keepalive/meta events may be emitted for long generations.

## Ingestion Notes
- `/ingest/folder` supports streaming progress events.
- Namespace validation applies to ingest and doc management APIs.
