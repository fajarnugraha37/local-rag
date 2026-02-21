# Configuration

Config file: `config.yaml`
Env overlays: `app/config/runtime_settings.py`

## FastAPI/Server
- `sqlite_db_path`
- `idempotency_ttl_s`
- `soft_delete_retention_days`

## Model/Embedding
- `ollama_model`
- `ollama_api.base_url`
- `ollama_api.api_key`
- `embedding_model`

## Retrieval/Citations
- `top_k`
- `citations`
- `citations_mode`
- `citation_max_sources`
- `citation_max_snippet_chars`

## Streaming
- `enable_streaming`
- `enable_thinking_summary`
- `per_call_max_tokens`
- `max_continuations`
- `flush_interval_ms`
- `provider_timeout_s`

## Ingestion
- `ingest_max_bytes`, `ingest_max_rows`, `ingest_max_objects`
- `ingest_max_pages`, `ingest_max_slides`, `ingest_max_sheets`
- `ingest_zip_max_entries`, `ingest_zip_max_uncompressed_bytes`
- `ingest_enable_parquet`, `ingest_enable_legacy_office`
- Docling keys:
  - `ingest_docling_enabled`
  - `ingest_docling_export_format`
  - `ingest_docling_device`
  - `ingest_docling_enable_ocr`
  - `ingest_docling_timeout_s`
  - `ingest_docling_max_pages`, `ingest_docling_max_slides`
  - `ingest_docling_max_tables`, `ingest_docling_max_images`

## Purge Helpers
- `make idempotency-purge`
- `make purge-soft-deletes SOFT_DELETE_RETENTION_DAYS=30`
