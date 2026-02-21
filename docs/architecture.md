# Architecture

## Overview
Easy Local RAG is a local-first Python application with a single launcher (`cmd/app.py`) and two runtime modes:
- CLI mode (`--cli`) for chat, ingestion, retrieval, migration, and evaluation actions.
- Server mode (`--server`) for HTTP/SSE APIs.

Core flow:
1. Ingest source documents/emails into chunk records.
2. Generate embeddings and upsert into persistent Chroma vector storage.
3. Run hybrid retrieval for user queries.
4. Build citation-aware prompts and produce responses via streaming or non-streaming chat.

## Main Packages
- `app/chat`: chat orchestration, streaming client, CLI wrappers, citation prompting/formatting.
- `app/http`: HTTP/SSE server, request parsing, route handlers.
- `app/ingestion`: extraction, chunking, folder scanning, ingest pipeline/services.
- `app/embeddings`: embedding service abstraction over Ollama embeddings.
- `app/retrieval`: hybrid retrieval, reranking, provenance helpers.
- `app/storage`: Chroma vector-store wrapper and vector-id helpers.
- `app/migration`: backfill and legacy migration flows.
- `app/config`: runtime settings loader and defaults.

## Entrypoints
- `cmd/app.py` is the required launcher.
- CLI actions are registered in `cmd/actions.py`.
- Server action points to `app/chat/streaming_server.py` (compatibility entrypoint), which delegates to `app/http/server.py`.

## Data Stores
- Persistent vectors: `data/chroma/`.
- Registry/state metadata: `data/doc_registry.json` (configured path), folder ingest state files.
- Legacy migration inputs: `data/chunks.jsonl`, `data/embeddings.jsonl`, `data/index_meta.json`.

## Extension Points
- Add new extractors in `app/ingestion/extractors/` and register in extractor registry.
- Add new CLI actions in `cmd/actions.py`.
- Add new HTTP routes in `app/http/handlers/*` and wire in `app/http/server.py`.
- Add retrieval logic in `app/retrieval/*` while preserving result/source shape used by citation code.
