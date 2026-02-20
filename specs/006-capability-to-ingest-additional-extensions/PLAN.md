# Feature 006 Implementation Plan

## Goal
Extend ingestion to support broad document/config/data extensions with one shared extraction pipeline for CLI and server.

## Step 1: Add Extractor Registry + Base Types
- Create `app/ingestion/extractors/base.py` and `app/ingestion/extractors/registry.py`.
- Add `ExtractorContext`, `ExtractedDocument`, `ExtractedUnit`, and routing by extension/special filename.
- Validate:
  - `python -m pytest -q tests/test_ingestion_extended_formats.py::test_registry_supports_special_names`

## Step 2: Implement Must-Have Extractors
- Add text/config/spec/script handlers in `app/ingestion/extractors/textual.py`.
- Add structured handlers in `app/ingestion/extractors/structured.py` for json/jsonc/jsonl/ndjson/csv/tsv/html/xml/svg.
- Ensure `.openapi.yaml/.yml/.json` mapping and `Dockerfile`/`Makefile` support.
- Validate:
  - `python -m pytest -q tests/test_ingestion_extended_formats.py::test_ingest_paths_for_must_have_formats`

## Step 3: Implement Nice-to-Have + Columnar/Notebook
- Add `.ipynb`, `.parquet`, `.feather`, `.arrow`, `.har` in `app/ingestion/extractors/notebook_data.py`.
- Add config switch behavior via `ingest_enable_parquet`.
- Validate:
  - `python -m pytest -q tests/test_ingestion_extended_formats.py::test_parquet_enabled_by_default`

## Step 4: Implement Office Extractors
- Add `app/ingestion/extractors/office.py` for `.pdf/.docx/.pptx/.xlsx` and legacy `.doc/.ppt/.xls`.
- Implement best-effort legacy parsing with warnings, not crashes.
- Validate:
  - `python -m pytest -q tests/test_ingestion_extended_formats.py::test_office_happy_path_extractors`
  - `python -m pytest -q tests/test_ingestion_extended_formats.py::test_legacy_office_graceful_failure`

## Step 5: Add Shared Ingestion Pipeline + Format-Aware Chunking
- Add `app/ingestion/pipeline.py` and `app/ingestion/chunking.py`.
- Include size/page/row/zip safety limits.
- Enrich chunk metadata and call `ingest_chunks`.
- Validate:
  - `python -m pytest -q tests/test_ingestion_extended_formats.py::test_ingest_size_limit_skips_file`

## Step 6: Wire CLI and Server to Shared Pipeline
- Update CLI: `app/ingestion/file_ingest_gui.py`.
- Update server routes in `app/chat/streaming_server.py`:
  - `POST /ingest/files`
  - `POST /ingest/upload`
- Keep existing `/ingest/chunks` and `/ingest/text`.
- Validate:
  - `python cmdpp.py --cli ingest-files --path README.md`
  - `python cmdpp.py --server --host 127.0.0.1 --port 8000`
  - `curl -X POST http://127.0.0.1:8000/ingest/files -H "Content-Type: application/json" -d "{"paths":["README.md"]}"`

## Step 7: Update Config, Docs, and Postman
- Update `config.yaml`, `app/config/runtime_settings.py`, `requirements.txt`.
- Update `README.md`, `AGENTS.md`, and `tests/postman/easy-local-rag-server.postman_collection.json`.
- Validate:
  - `python -m pytest -q`

## Rollback
- `git status`
- `git restore app/ingestion app/chat/streaming_server.py app/config/runtime_settings.py config.yaml requirements.txt README.md AGENTS.md tests`
- Re-run `python -m pytest -q` to confirm baseline.

## Debug Checklist
- If parser skips files: inspect `reason` and `warnings` in ingestion summary.
- If upload fails: ensure `multipart/form-data` and field name `file`.
- If duplicate vector IDs appear: verify `ingest_chunks` receives chunk dictionaries and disambiguation logic is active.
- If XML parsing fails: confirm safe parser fallback warnings are present.
