# Spec 011 Tasks

Dispatch format:
`please follow specs/011-docling-integration/PLAN.md and do task T00X`

## T001
Goal: Add Docling conversion foundation with stable internal model.
Files to touch:
- `app/document_conversion/__init__.py`
- `app/document_conversion/models.py`
- `app/document_conversion/docling_adapter.py`
Steps:
- Create `ConvertedDocument` and `ConvertedBlock` data models.
- Implement `convert_file` and `convert_bytes`.
- Add format detection for all spec 011 target formats.
Acceptance criteria:
- Adapter returns non-empty normalized output for valid fixtures.
- Adapter includes metadata (`source_path`, `source_format`, `content_hash`, `extracted_at`).
Validation commands:
- `python -m pytest -q tests/test_docling_adapter.py`
Status: done

## T002
Goal: Wire Docling through extractor strategy contract.
Files to touch:
- `app/ingestion/extractors/docling_extractors.py`
- `app/ingestion/extractors/base.py`
- `app/ingestion/extractors/__init__.py`
Steps:
- Implement extractor bridge from `ConvertedDocument` to `ExtractedDocument`.
- Preserve locator metadata in `ExtractedUnit.metadata`.
- Ensure errors map to ingestion-friendly warnings/exceptions.
Acceptance criteria:
- Registry can call docling extractor through existing extractor interface.
- Locator metadata survives extractor boundary.
Validation commands:
- `python -m pytest -q tests/test_docling_routing.py tests/test_docling_metadata_mapping.py`
Status: done

## T003
Goal: Route all required formats exclusively to Docling.
Files to touch:
- `app/ingestion/extractors/registry.py`
- `app/ingestion/extractors/textual.py`
- `app/ingestion/extractors/structured.py`
- `app/ingestion/extractors/office.py`
Steps:
- Replace extension mappings for required formats with docling extractor mapping.
- Add mapping for `.xhtml`, `.tex`, `.vtt`, target image extensions, docling JSON.
- Remove legacy routing entries for migrated formats.
Acceptance criteria:
- Required format extension resolution always selects Docling extractor.
- No registry fallback to old handlers for migrated formats.
Validation commands:
- `python -m pytest -q tests/test_docling_routing.py`
- `python -m pytest -q tests/test_ingestion_extended_formats.py`
Status: done

## T004
Goal: Remove legacy migrated-format parser implementations and dependencies in code.
Files to touch:
- `app/ingestion/extractors/office.py`
- `app/ingestion/extractors/structured.py`
- `app/ingestion/extractors/textual.py`
- related imports in `app/ingestion/extractors/registry.py`
Steps:
- Delete migrated-format code paths from old modules.
- Keep non-target format handlers only.
- Remove dead imports and unreachable functions.
Acceptance criteria:
- Old migrated-format handlers are deleted or no longer present.
- Codebase has a single implementation path for required formats.
Validation commands:
- `python -m pytest -q tests/test_ingestion_extended_formats.py tests/test_smoke_ingest.py`
- `python -m pytest -q`
Status: todo

## T005
Goal: Add docling-aware chunk/provenance metadata mapping.
Files to touch:
- `app/ingestion/pipeline.py`
- `app/ingestion/chunking.py`
- `app/retrieval/provenance.py`
Steps:
- Map docling locator metadata into chunk metadata fields used by retrieval/citations.
- Keep chunk size bounds and deterministic chunk indexing.
- Ensure page/slide/sheet/heading metadata is retained when available.
Acceptance criteria:
- Ingested chunks carry useful locators for migrated formats.
- Retrieval source locator formatting remains valid.
Validation commands:
- `python -m pytest -q tests/test_docling_metadata_mapping.py tests/test_citation_source_mapping.py`
Status: todo

## T006
Goal: Ensure CLI and server ingestion routes consistently use Docling path.
Files to touch:
- `app/cli/ingest_files.py`
- `app/cli/ingest_folder.py`
- `app/ingestion/file_ingest_gui.py`
- `app/http/handlers/ingestion.py`
- `app/chat/streaming_server.py`
Steps:
- Verify all ingestion entrypoints continue to call `ingest_paths`/`ingest_uploaded_files`/`ingest_folder`.
- Remove any direct parser-specific bypass logic.
- Keep SSE progress behavior unchanged for folder ingestion.
Acceptance criteria:
- CLI and server ingest required formats through same pipeline path.
- No endpoint-specific parsing divergence remains.
Validation commands:
- `python -m pytest -q tests/test_ingestion_server_routes.py tests/test_folder_ingest_idempotency.py`
- `python cmd/app.py --cli ingest-files --path README.md`
- `python cmd/app.py --cli ingest-folder --path . --dry-run`
Status: todo

## T007
Goal: Cut over dependency and configuration story to Docling.
Files to touch:
- `requirements.txt`
- `pyproject.toml`
- `app/config/runtime_settings.py`
- `config.yaml`
Steps:
- Add `docling` dependency.
- Remove obsolete migrated-format parsing dependencies unless still required by non-ingestion modules.
- Add Docling config keys and defaults; remove obsolete parser toggles.
Acceptance criteria:
- Dependency list reflects Docling-first ingestion.
- Config exposes docling knobs with CPU-safe defaults.
Validation commands:
- `python -m pytest -q tests/test_runtime_settings_docling.py`
- `python -m pytest -q`
Status: todo

## T008
Goal: Add and update tests proving docling path is used.
Files to touch:
- `tests/test_docling_adapter.py`
- `tests/test_docling_routing.py`
- `tests/test_docling_metadata_mapping.py`
- `tests/test_docling_ingestion_smoke.py`
- updates to `tests/test_ingestion_extended_formats.py`
Steps:
- Add unit tests for extension routing and metadata mapping.
- Add lightweight smoke tests for required formats with generated fixtures where practical.
- Remove assumptions tied to old parser stack.
Acceptance criteria:
- Routing tests fail if old extractors are used for migrated formats.
- Smoke tests prove non-empty extraction and chunk creation for required formats.
Validation commands:
- `python -m pytest -q tests/test_docling_adapter.py tests/test_docling_routing.py tests/test_docling_ingestion_smoke.py`
- `python -m pytest -q`
Status: todo

## T009
Goal: Update repository documentation and contributor guidance for docling-first ingestion.
Files to touch:
- `docs/architecture.md`
- `docs/rag-pipeline.md`
- `docs/configuration.md`
- `docs/development.md`
- `README.md`
- `AGENTS.md`
- `Makefile`
Steps:
- Replace old parser architecture descriptions with Docling adapter flow.
- Update supported format list to spec 011 reality.
- Document setup and validation commands; add/update make targets (`install/setup`, `test`, `lint`, `fmt`, optional `ingest-smoke`).
- Add explicit AGENTS guidance: add new document formats through Docling adapter.
Acceptance criteria:
- Docs match code reality and ingestion flow.
- Top-level developer workflow remains executable.
Validation commands:
- `make help`
- `make lint`
- `make test`
Status: todo

## T010
Goal: Final cleanup and acceptance verification.
Files to touch:
- `specs/011-docling-integration/IMPROVEMENT.md`
- `specs/011-docling-integration/PLAN.md`
- `specs/011-docling-integration/TASKS.md`
- cleanup references across repository docs/tests
Steps:
- Remove stale mentions of removed parser paths/dependencies.
- Run full quality gate and smoke validations.
- Capture final migration notes in spec docs.
Acceptance criteria:
- All acceptance criteria below are met.
Validation commands:
- `python -m pytest -q`
- `python cmd/app.py --cli --help`
- `python cmd/app.py --server --help`
Status: todo

## Global Acceptance Criteria
- All listed formats are handled via Docling adapter exclusively.
- Old implementation for those formats is removed.
- CLI and server ingestion both work for migrated formats.
- Chunking emits stable chunks with useful locators/provenance.
- Docs (`docs/*.md`), `README.md`, `AGENTS.md`, and `Makefile` are updated and accurate.
- Validation and tests pass.
