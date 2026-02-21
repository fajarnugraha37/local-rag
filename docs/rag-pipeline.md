# RAG Pipeline

## Ingestion Pipeline
1. Input acquisition:
- CLI file/folder ingestion (`ingest-files`, `ingest-folder`).
- HTTP ingestion (`/ingest/files`, `/ingest/folder`, `/ingest/upload`, `/ingest/chunks`, `/ingest/text`).
- Email ingestion (`ingest-email`).

2. Extraction:
- File type is resolved by extractor registry.
- Spec 011 migrated formats are routed to the Docling extractor bridge.
- Docling adapter emits normalized markdown text + locator-aware blocks + metadata.

3. Chunking:
- Units are split with token-based chunking and overlap settings.
- Chunk metadata includes source path/name, document type, hash, and normalized locators (page/slide/sheet/heading/xml fields when present).

4. Embedding + upsert:
- `app/embeddings/service.py` computes embeddings.
- Chunks are upserted into Chroma with namespace/doc metadata.

5. Registry/state update:
- Doc registry and folder ingest state are updated for idempotency and delete/list operations.

## Query Pipeline
1. User question arrives from CLI or `/chat/stream`.
2. Retrieval (`app/retrieval/hybrid_search.py`) fetches scored chunks.
3. Citation prompt builder produces context blocks and user prompt.
4. LLM response is streamed or returned in one shot.
5. Citation formatter applies inline markers and optional source appendix.

## Streaming Pipeline
- SSE endpoint: `GET /chat/stream`.
- Emits ordered events including response deltas and completion markers.
- On completion, server emits source blocks and citation stats.

## Safety/Robustness Notes
- Ingestion supports size/page/rows limits and pattern filtering.
- Docling knobs are configurable (`ingest_docling_*`) with CPU-safe defaults.
- Folder scan supports `.gitignore`/`.ragignore` and dry-run/force modes.
- Streaming supports continuation when model output is token-limited.
