# Easy Local RAG (Ollama + Hybrid Retrieval)

A local-first RAG project for documents and email data. The current codebase uses structured chunk storage, incremental embeddings, and hybrid retrieval (dense + BM25 + reranker) with optional multi-pass answering for small models.

## Current Architecture
- Ingestion: `upload.py`, `collect_emails.py`, `migrate_vault.py`
- Indexing: `index_embeddings.py`
- Retrieval: `retrieval.py` + `reranker.py`
- Context packing: `context_packer.py` + `chunking.py`
- Chat apps: `localrag.py`, `localrag_no_rewrite.py`, `emailrag2.py`
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
python upload.py
```

### Option B: Import emails
Set `.env` with `GMAIL_USERNAME`, `GMAIL_PASSWORD`, `OUTLOOK_USERNAME`, `OUTLOOK_PASSWORD`, then run:
```powershell
python collect_emails.py --keyword "invoice" --startdate 01.01.2025 --enddate 31.01.2025
```

### Option C: Migrate legacy `vault.txt`
```powershell
python migrate_vault.py --vault vault.txt
```

## Build/Update Embedding Index
```powershell
python index_embeddings.py --embedding-model mxbai-embed-large
```

## Run Chat
### Main app (rewrite + optional multi-pass)
```powershell
python localrag.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest --top-k 6 --multi-pass
```

### Baseline app (no rewrite)
```powershell
python localrag_no_rewrite.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest
```

### Email chat app
```powershell
python emailrag2.py --model hf.co/mradermacher/Gemma-3-1B-it-GLM-4.7-Flash-Heretic-Uncensored-Thinking-i1-GGUF:latest
```

## Inspect Retrieval
```powershell
python retrieval.py --query "what are key payment terms?" --top-k 6
```

## Test and Evaluate
```powershell
python -m pytest -q
python eval\run_eval.py --questions eval\questions.jsonl --top-k 6 --output eval\results.json
make all
# or: .\run_all.ps1
```

## Configuration
Runtime defaults are in `config.yaml`; environment variables can override core values via `settings.py` (for example `OLLAMA_MODEL`, `TOP_K`, `OLLAMA_API_BASE_URL`, `OLLAMA_API_KEY`).

## Notes
- Retrieval can still run BM25-only if embeddings are missing, but best quality requires running `index_embeddings.py`.
- `data/chunks.jsonl` may contain sensitive text. Avoid committing private content.