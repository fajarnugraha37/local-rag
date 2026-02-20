# Easy Local RAG (Ollama + Hybrid Retrieval)

Local-first RAG for documents and email with persistent vector storage (Chroma), hybrid retrieval, and optional SSE streaming chat.

## Unified Entrypoint (Required)
The project now uses a single launcher:

```powershell
python .\cmd\app.py --server [server args]
python .\cmd\app.py --cli [action args]
```

Legacy root-level scripts were removed. Use `cmd/app.py` only.

## Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest
ollama pull mxbai-embed-large
```

## Server Mode (HTTP + SSE)
```powershell
python .\cmd\app.py --server --host 127.0.0.1 --port 8000
```
- Health: `GET /health`
- Action inventory: `GET /actions` (alias: `GET /action`)
- Stream: `GET /chat/stream?question=...&top_k=...&max_continuations=...&per_call_max_tokens=...`
- Ingest chunks: `POST /ingest/chunks`
- Ingest raw text: `POST /ingest/text`
- Delete vectors by doc: `POST /vectors/delete-doc`
- Retrieval query: `POST /retrieval/query`
- Run non-interactive CLI actions via HTTP: `POST /actions/run`

Example:
```powershell
curl -N "http://127.0.0.1:8000/chat/stream?question=What%20is%20the%20summary%3F&top_k=3"
```

HTTP JSON examples:
```powershell
# list actions
curl "http://127.0.0.1:8000/actions"

# ingest chunks
curl -X POST "http://127.0.0.1:8000/ingest/chunks" `
  -H "Content-Type: application/json" `
  -d "{\"chunks\":[\"payment due in 30 days\"],\"doc_id\":\"demo_doc\"}"

# retrieval query
curl -X POST "http://127.0.0.1:8000/retrieval/query" `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"payment terms\",\"top_k\":3,\"rerank\":true}"
```

Postman assets:
- `tests/postman/easy-local-rag-server.postman_collection.json`
- `tests/postman/easy-local-rag-local.postman_environment.json`

## CLI Mode
List commands:
```powershell
python .\cmd\app.py --cli --help
```

Common commands:
```powershell
# Main chat (rewrite + optional multi-pass)
python .\cmd\app.py --cli chat --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest --top-k 6 --multi-pass

# Streaming chat
python .\cmd\app.py --cli chat --stream --max-continuations 2 --per-call-max-tokens 1024

# Baseline chat / email chat
python .\cmd\app.py --cli chat-baseline --stream
python .\cmd\app.py --cli chat-email --stream

# Ingestion
python .\cmd\app.py --cli ingest-files
python .\cmd\app.py --cli ingest-files --path .\docs\sample.pdf
python .\cmd\app.py --cli ingest-files --path .\docs\a.txt --path .\docs\b.json
python .\cmd\app.py --cli ingest-email --keyword "invoice" --startdate 01.01.2025 --enddate 31.01.2025
python .\cmd\app.py --cli migrate-vault --vault vault.txt

# Backfill legacy JSONL to vector DB
python .\cmd\app.py --cli backfill-vectors --batch-size 64

# Retrieval and validation
python .\cmd\app.py --cli query --query "what are key payment terms?" --top-k 6
python .\cmd\app.py --cli validate-phase4 --query "common case overview" --top-k 8
python .\cmd\app.py --cli debug-retrieval

# Eval
python .\cmd\app.py --cli eval --questions eval\questions.jsonl --top-k 6 --output eval\results.json
```
`ingest-files --path ...` now shows progress bars (PDF page read + embedding/upsert) so ingestion status is visible.

## Make Targets
```powershell
make help
make run-server
make run-cli
make chat
make ingest
make query Q="what are key payment terms?" TOP_K=6
make test
make eval
make all
```

## Data and Configuration
- Runtime config: `config.yaml`
- Env overrides: `app/config/runtime_settings.py`
- Vector DB data: `data/chroma/`
- Legacy migration artifacts (input only): `data/chunks.jsonl`, `data/embeddings.jsonl`, `data/index_meta.json`

Streaming/continuation config keys:
- `enable_streaming`
- `enable_thinking_summary`
- `per_call_max_tokens`
- `max_continuations`
- `flush_interval_ms`
- `provider_timeout_s`
- `continuation_instruction`

## Backup / Restore
```powershell
# backup
Copy-Item -Recurse -Force data\chroma data\chroma.backup

# restore
Remove-Item -Recurse -Force data\chroma
Copy-Item -Recurse -Force data\chroma.backup data\chroma
```

## Test
```powershell
python -m pytest -q
```
