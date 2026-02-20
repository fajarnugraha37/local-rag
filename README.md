# Easy Local RAG (Ollama + Hybrid Retrieval)

A local-first RAG project for documents and email data. The current codebase uses structured chunk storage, incremental embeddings, and hybrid retrieval (dense + BM25 + reranker) with optional multi-pass answering for small models.

## Current Architecture
- Ingestion: `app/ingestion/file_ingest_gui.py`, `app/ingestion/email_ingest_job.py`, `app/migration/vault_migration.py`
- Indexing: `app/indexing/embedding_indexer.py`
- Retrieval: `app/retrieval/hybrid_search.py` + `app/retrieval/heuristic_reranker.py`
- Context packing: `app/context/token_budget_packer.py` + `app/context/token_chunking.py`
- Chat apps: `app/chat/document_chat_cli.py`, `app/chat/document_chat_baseline_cli.py`, `app/chat/email_chat_cli.py`
- Compatibility shims: root scripts (`localrag.py`, `localrag_no_rewrite.py`, `emailrag2.py`, `upload.py`, etc.) delegate to `app/` modules.
- Data files: `data/chunks.jsonl`, `data/embeddings.jsonl`, `data/index_meta.json`

## Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest
ollama pull mxbai-embed-large
```

## Ingest Data
### Option A: Upload local files (GUI)
```powershell
python -m app.ingestion.file_ingest_gui
# compatibility: python upload.py
```

### Option B: Import emails
Set `.env` with `GMAIL_USERNAME`, `GMAIL_PASSWORD`, `OUTLOOK_USERNAME`, `OUTLOOK_PASSWORD`, then run:
```powershell
python -m app.ingestion.email_ingest_job --keyword "invoice" --startdate 01.01.2025 --enddate 31.01.2025
# compatibility: python collect_emails.py --keyword "invoice" --startdate 01.01.2025 --enddate 31.01.2025
```

### Option C: Migrate legacy `vault.txt`
```powershell
python -m app.migration.vault_migration --vault vault.txt
# compatibility: python migrate_vault.py --vault vault.txt
```

## Build/Update Embedding Index
```powershell
python -m app.indexing.embedding_indexer --embedding-model mxbai-embed-large
# compatibility: python index_embeddings.py --embedding-model mxbai-embed-large
```

## Run Chat
### Main app (rewrite + optional multi-pass)
```powershell
python -m app.chat.document_chat_cli --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest --top-k 6 --multi-pass
# compatibility: python localrag.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest --top-k 6 --multi-pass
```

### Streaming mode (all chat CLIs)
```powershell
python -m app.chat.document_chat_cli --stream --max-continuations 2 --per-call-max-tokens 1024
python -m app.chat.document_chat_baseline_cli --stream --max-continuations 2 --per-call-max-tokens 1024
python -m app.chat.email_chat_cli --stream --max-continuations 2 --per-call-max-tokens 1024
```
- `--stream/--no-stream`: enable or disable token streaming output.
- `--max-continuations`: follow-up calls when a response hits token limit (`finish_reason=length`).
- `--per-call-max-tokens`: token cap per streamed provider call.
- `--enable-thinking-summary/--no-enable-thinking-summary`: optional short reasoning summary event.

### SSE endpoint (optional server)
```powershell
python -m app.chat.streaming_server --host 127.0.0.1 --port 8000
curl -N "http://127.0.0.1:8000/chat/stream?question=What%20is%20the%20summary%3F&top_k=3&max_continuations=2&per_call_max_tokens=512"
```
- Health: `GET /health`
- Stream: `GET /chat/stream`
- Event types: `meta`, `final_delta`, `thinking_delta`, `part_done`, `done`, `error`

### Baseline app (no rewrite)
```powershell
python -m app.chat.document_chat_baseline_cli --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest
# compatibility: python localrag_no_rewrite.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest
```

### Email chat app
```powershell
python -m app.chat.email_chat_cli --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest
# compatibility: python emailrag2.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest
```

## Inspect Retrieval
```powershell
python -m app.retrieval.hybrid_search --query "what are key payment terms?" --top-k 6
# compatibility: python retrieval.py --query "what are key payment terms?" --top-k 6
```

## Test and Evaluate
```powershell
python -m pytest -q
python eval\run_eval.py --questions eval\questions.jsonl --top-k 6 --output eval\results.json
make all
# or: .\run_all.ps1
```

## Configuration
Runtime defaults are in `config.yaml`; environment variables can override core values via `app/config/runtime_settings.py` (for example `OLLAMA_MODEL`, `TOP_K`, `OLLAMA_API_BASE_URL`, `OLLAMA_API_KEY`).

Streaming/continuation keys:
- `enable_streaming`
- `enable_thinking_summary`
- `per_call_max_tokens`
- `max_continuations`
- `flush_interval_ms`
- `provider_timeout_s`
- `continuation_instruction`

## Notes
- Retrieval can still run BM25-only if embeddings are missing, but best quality requires running `index_embeddings.py`.
- `data/chunks.jsonl` may contain sensitive text. Avoid committing private content.
- Thinking summaries can expose higher-level reasoning metadata. Keep `enable_thinking_summary` disabled for stricter privacy/safety environments.
