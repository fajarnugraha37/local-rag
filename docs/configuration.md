# Configuration

## Sources
- Primary: `config.yaml`.
- Environment overlays are loaded through `app/config/runtime_settings.py`.

## High-Impact Keys
- Model/API:
- `ollama_model`
- `ollama_api.base_url`
- `ollama_api.api_key`
- `embedding_model`

- Retrieval/citations:
- `top_k`
- `citations`
- `citations_mode`
- `citation_max_sources`
- `citation_max_snippet_chars`

- Streaming:
- `enable_streaming`
- `enable_thinking_summary`
- `per_call_max_tokens`
- `max_continuations`
- `flush_interval_ms`
- `provider_timeout_s`
- `continuation_instruction`

- Ingestion limits:
- `ingest_max_bytes`, `ingest_max_rows`, `ingest_max_objects`
- `ingest_max_pages`, `ingest_max_slides`, `ingest_max_sheets`
- `ingest_zip_max_entries`, `ingest_zip_max_uncompressed_bytes`
- `ingest_enable_parquet`, `ingest_enable_legacy_office`
- Docling:
- `ingest_docling_enabled`
- `ingest_docling_export_format` (default `markdown`)
- `ingest_docling_device` (default `cpu`)
- `ingest_docling_enable_ocr` (default `false`)
- `ingest_docling_timeout_s`
- `ingest_docling_max_pages`, `ingest_docling_max_slides`
- `ingest_docling_max_tables`, `ingest_docling_max_images`

- Storage:
- `vector_db_persist_dir`
- `vector_db_collection`
- `doc_registry_path`

## Namespace Behavior
- Default namespace is used when not supplied.
- Namespace is validated before ingest/delete/list operations.

## Operational Guidance
- Keep credentials out of version control.
- Validate config changes with `python .\cmd\app.py --help` and smoke tests before wider rollout.
