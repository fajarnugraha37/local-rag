# Feature 006 Task Breakdown and Progress Tracker

## Progress Tracker
- Total tasks: 10
- Done: 10
- Doing: 0
- Blocked: 0
- Todo: 0

## T001
- status: done
- goal: Introduce extractor plugin base and registry.
- files to touch: `app/ingestion/extractors/base.py`, `app/ingestion/extractors/registry.py`, `app/ingestion/extractors/__init__.py`
- steps:
  1. Add extractor dataclasses/interfaces.
  2. Add extension/special-name/suffix routing.
- acceptance criteria: registry resolves known extensions and special names.
- validation commands: `python -m pytest -q tests/test_ingestion_extended_formats.py::test_registry_supports_special_names`

## T002
- status: done
- goal: Implement text/config/spec/script extractors.
- files to touch: `app/ingestion/extractors/textual.py`
- steps:
  1. Add markdown/config/script/schema handlers.
  2. Parse yaml/toml/ini/properties/env safely.
- acceptance criteria: textual formats ingest and produce normalized text.
- validation commands: `python -m pytest -q tests/test_ingestion_extended_formats.py::test_ingest_paths_for_must_have_formats`

## T003
- status: done
- goal: Implement structured extractors.
- files to touch: `app/ingestion/extractors/structured.py`
- steps:
  1. Add json/jsonc/jsonl/ndjson extractors.
  2. Add csv/tsv/html/xml/svg/har extractors.
- acceptance criteria: structured formats produce units; invalid lines are warnings not crashes.
- validation commands: `python -m pytest -q tests/test_ingestion_extended_formats.py::test_ingest_paths_for_must_have_formats`

## T004
- status: done
- goal: Implement notebook and columnar data extractors.
- files to touch: `app/ingestion/extractors/notebook_data.py`
- steps:
  1. Add ipynb parser.
  2. Add parquet/feather/arrow extractors.
- acceptance criteria: parquet-like ingestion works when dependency is present.
- validation commands: `python -m pytest -q tests/test_ingestion_extended_formats.py::test_parquet_enabled_by_default`

## T005
- status: done
- goal: Implement office extractors including legacy binaries.
- files to touch: `app/ingestion/extractors/office.py`
- steps:
  1. Add pdf/docx/pptx/xlsx extractors.
  2. Add best-effort doc/ppt/xls extractors.
  3. Add zip-safety checks.
- acceptance criteria: office happy-path fixtures ingest; legacy failures are graceful warnings.
- validation commands:
  - `python -m pytest -q tests/test_ingestion_extended_formats.py::test_office_happy_path_extractors`
  - `python -m pytest -q tests/test_ingestion_extended_formats.py::test_legacy_office_graceful_failure`

## T006
- status: done
- goal: Build shared ingestion pipeline + format-aware chunking.
- files to touch: `app/ingestion/pipeline.py`, `app/ingestion/chunking.py`, `app/ingestion/vector_ingest_service.py`
- steps:
  1. Add ingest options/context and per-file summaries.
  2. Add chunk metadata enrichment and safety checks.
  3. Extend `ingest_chunks` to accept chunk dictionaries.
- acceptance criteria: per-file summary includes status/reason/warnings/chunks_count; no ingestion-run crashes.
- validation commands: `python -m pytest -q tests/test_ingestion_extended_formats.py::test_ingest_size_limit_skips_file`

## T007
- status: done
- goal: Wire CLI ingestion to shared pipeline.
- files to touch: `app/ingestion/file_ingest_gui.py`, `cmd/actions.py`
- steps:
  1. Replace hardcoded extension branch with shared pipeline.
  2. Add CLI filters/limits (`--recursive`, `--include`, `--exclude`, size/page/row options).
- acceptance criteria: CLI path ingestion supports new formats and prints file-level summary.
- validation commands: `python cmdpp.py --cli ingest-files --path README.md`

## T008
- status: done
- goal: Wire server ingestion to shared pipeline.
- files to touch: `app/chat/streaming_server.py`
- steps:
  1. Add `POST /ingest/files` for path ingestion.
  2. Add `POST /ingest/upload` for multipart uploads.
- acceptance criteria: server supports both JSON path ingestion and multipart uploads.
- validation commands:
  - `python cmdpp.py --server --host 127.0.0.1 --port 8000`
  - `curl -X POST http://127.0.0.1:8000/ingest/files -H "Content-Type: application/json" -d "{"paths":["README.md"]}"`

## T009
- status: done
- goal: Update config and dependency surface.
- files to touch: `config.yaml`, `app/config/runtime_settings.py`, `requirements.txt`
- steps:
  1. Add ingestion safety/format feature flags.
  2. Add parsing dependencies.
- acceptance criteria: config/env keys load correctly and parser modules resolve when installed.
- validation commands: `python -m pytest -q tests/test_streaming_continuation.py::test_streaming_config_toggles_are_loaded`

## T010
- status: done
- goal: Update tests, Postman, and docs.
- files to touch: `tests/test_ingestion_extended_formats.py`, `tests/postman/easy-local-rag-server.postman_collection.json`, `README.md`, `AGENTS.md`
- steps:
  1. Add format/safety/office/parquet tests.
  2. Add Postman requests for `/ingest/files` and `/ingest/upload`.
  3. Document supported extensions and run commands.
- acceptance criteria: docs and collection match implemented endpoints and capabilities.
- validation commands: `python -m pytest -q`
