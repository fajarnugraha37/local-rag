# Feature 006 Improvement Spec: Capability to Ingest Additional Extensions

## Current State (Repo Scan)
- CLI ingestion entrypoint: `app/ingestion/file_ingest_gui.py` (action: `ingest-files` in `cmd/actions.py`).
- Server ingestion endpoints: `POST /ingest/chunks`, `POST /ingest/text` in `app/chat/streaming_server.py`.
- Existing file-type support before this feature was hardcoded to `.pdf`, `.txt`, `.json` in `app/ingestion/file_ingest_gui.py`.
- Loader/parser architecture before this feature was single-function branching (no plugin registry).
- Chunking before this feature used sentence/char splitting (`chunk_sentences`) and token utilities in `app/context/token_chunking.py`.
- Metadata before this feature was minimal (`doc_id`, `doc_key`, `chunk_id`, `source`, `token_count`) in `app/ingestion/vector_ingest_service.py`.
- Dependencies are managed in `requirements.txt`.
- Existing ingestion tests: `tests/test_smoke_ingest.py`.

## Problems
- Unsupported formats block real repository/document ingestion.
- CLI and server ingestion paths were inconsistent and not shareable.
- No extractor plugin architecture, limited safety controls, and sparse observability.

## Implemented Approach
- Added pluggable extractor system under `app/ingestion/extractors/`:
  - `base.py`, `registry.py`, `textual.py`, `structured.py`, `notebook_data.py`, `office.py`, `utils.py`.
- Added shared pipeline `app/ingestion/pipeline.py` and format-aware chunking `app/ingestion/chunking.py`.
- Updated CLI ingestion (`app/ingestion/file_ingest_gui.py`) to use shared pipeline.
- Added server parity endpoints:
  - `POST /ingest/files` (server-local paths)
  - `POST /ingest/upload` (multipart upload)
- Extended metadata per chunk: `source_path`, `source_name`, `source_kind`, `extension/special_name`, `doc_type`, `content_hash`, `extracted_at`, plus format-specific fields.
- Added safety controls: file size caps, row/object/page/slide/sheet limits, zip safety checks, safe XML parser settings, graceful skip/warnings.

## Format Strategy
- Must-have docs/config/data/spec/script/markup formats are supported.
- Nice-to-have formats supported: `.txt`, `.log`, `.ipynb`, `.feather`, `.arrow`, `.har`.
- Office formats supported: `.pdf`, `.docx`, `.doc`, `.pptx`, `.ppt`, `.xlsx`, `.xls`.
- Legacy `.doc/.ppt/.xls` are best-effort (pure Python; gracefully skipped with warnings when not extractable).

## Dependency Plan
- Added parser dependencies in `requirements.txt`: `python-docx`, `openpyxl`, `python-pptx`, `pyarrow`, `nbformat`, `xlrd==1.2.0`, `olefile`.
- Existing dependencies reused: `PyPDF2`, `pyyaml`, `beautifulsoup4`, `lxml`.

## Config Knobs
Added in `config.yaml` + `app/config/runtime_settings.py`:
- `ingest_max_bytes`, `ingest_max_rows`, `ingest_max_objects`
- `ingest_max_pages`, `ingest_max_slides`, `ingest_max_sheets`
- `ingest_timeout_s`
- `ingest_zip_max_entries`, `ingest_zip_max_uncompressed_bytes`
- `ingest_enable_parquet`, `ingest_enable_legacy_office`

## Definition of Done
- Shared registry-based ingestion works in both CLI and server.
- Must-have format groups ingest to chunks.
- Office happy-path extractors are covered.
- Invalid/unsupported inputs do not crash runs.
- Limits are enforced and tests pass.

## Non-Goals
- OCR for scanned PDFs/images.
- Semantic table reconstruction beyond text extraction.
- Perfect fidelity for legacy binary Office formats.

## Risks & Mitigations
- Legacy binary quality variance: handled via best-effort + explicit warnings.
- Parser dependency drift: pinned `xlrd==1.2.0`, centralized extractor errors.
- Oversized/hostile files: strict configurable caps + zip safety checks.
