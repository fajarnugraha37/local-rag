# Spec 011 Execution Plan (Docling Cutover, No Backward Compatibility)

## Principles
- Single conversion engine for target formats: Docling.
- Keep ingestion orchestration stable (`app/ingestion/pipeline.py`, `ingest_paths`, `ingest_uploaded_files`).
- Remove old target-format handlers after routing cutover.
- Validate each phase with fast, concrete commands.

## Phase 1: Add Docling Adapter Layer

### Step 1.1 - Add conversion models and adapter
Files:
- `app/document_conversion/__init__.py`
- `app/document_conversion/models.py`
- `app/document_conversion/docling_adapter.py`

Actions:
- Introduce `ConvertedDocument` and `ConvertedBlock` dataclasses.
- Implement `convert_file`, `convert_bytes`, and optional `convert_batch`.
- Implement format classification helpers for required formats (including xhtml, vtt, image formats, xml subtype hints, docling json).
- Emit normalized metadata + locator-aware blocks.

Validation:
- `python -m pytest -q tests/test_docling_adapter.py`

## Phase 2: Route Required Formats to Docling

### Step 2.1 - Add docling-backed extractor bridge
Files:
- `app/ingestion/extractors/docling_extractors.py`
- `app/ingestion/extractors/base.py` (only if context contract needs Docling knobs)

Actions:
- Bridge Docling `ConvertedDocument` into existing `ExtractedDocument`/`ExtractedUnit`.
- Ensure metadata passthrough is scalar-safe for Chroma metadata writes.

Validation:
- `python -m pytest -q tests/test_docling_routing.py`

### Step 2.2 - Switch registry mapping to Docling for target formats
Files:
- `app/ingestion/extractors/registry.py`

Actions:
- Route all spec 011 target extensions to docling extractor.
- Keep non-target formats on existing extractors.
- Add special handling for docling-json naming/extension convention.

Validation:
- `python -m pytest -q tests/test_docling_routing.py`
- `python -m pytest -q tests/test_ingestion_extended_formats.py`

## Phase 3: Remove Legacy Target-Format Implementations

### Step 3.1 - Delete/cleanup old per-format logic
Files:
- `app/ingestion/extractors/office.py`
- `app/ingestion/extractors/structured.py`
- `app/ingestion/extractors/textual.py`
- `app/ingestion/extractors/__init__.py`

Actions:
- Remove old handlers for migrated formats.
- Keep only non-target format logic in retained modules.
- Remove dead imports/usages from registry and tests.

Validation:
- `python -m pytest -q tests/test_ingestion_extended_formats.py tests/test_smoke_ingest.py`
- `python -m pytest -q`

## Phase 4: Chunking + Provenance Mapping

### Step 4.1 - Add docling-aware chunk metadata mapping
Files:
- `app/ingestion/pipeline.py`
- `app/ingestion/chunking.py`
- (optional) `app/document_conversion/locator_mapping.py`

Actions:
- Keep current token-chunking behavior.
- Add heading-aware/page-aware/slide-aware boundaries from Docling metadata where available.
- Preserve metadata fields used by retrieval/citations.

Validation:
- `python -m pytest -q tests/test_docling_metadata_mapping.py tests/test_citation_source_mapping.py`

## Phase 5: CLI + Server Integration Verification

### Step 5.1 - Confirm all ingestion entrypoints hit same pipeline
Files:
- `app/cli/ingest_files.py`
- `app/cli/ingest_folder.py`
- `app/http/handlers/ingestion.py`
- `app/chat/streaming_server.py`

Actions:
- Ensure no bypass path exists for target formats.
- Ensure uploads and folder ingestion use docling route via registry/pipeline.

Validation:
- `python -m pytest -q tests/test_ingestion_server_routes.py tests/test_folder_scanner.py tests/test_folder_ingest_idempotency.py`
- `python cmd/app.py --cli ingest-files --path README.md`
- `python cmd/app.py --cli ingest-folder --path . --dry-run`

## Phase 6: Dependencies and Config Cutover

### Step 6.1 - Update dependency set and config knobs
Files:
- `requirements.txt`
- `pyproject.toml` (if needed for tooling constraints)
- `app/config/runtime_settings.py`
- `config.yaml`

Actions:
- Add `docling`.
- Remove obsolete parser deps for migrated formats (except libraries still used elsewhere).
- Add Docling config keys and defaults.
- Remove deprecated ingestion flags tied to deleted parsers.

Validation:
- `python -m pytest -q tests/test_runtime_settings_docling.py`
- `python -m pytest -q`

## Phase 7: Documentation and Developer Workflow Alignment

### Step 7.1 - Update docs and top-level guides
Files:
- `docs/architecture.md`
- `docs/rag-pipeline.md`
- `docs/configuration.md`
- `docs/development.md`
- `README.md`
- `AGENTS.md`
- `Makefile`

Actions:
- Document docling-first extraction flow and supported formats.
- Add/update make targets for install/test/lint/fmt and optional ingest smoke.
- Update contributor guidance: new formats must be added via Docling adapter path.

Validation:
- `make help`
- `make lint`
- `make test`

## Phase 8: End-to-End Smoke and Final Cleanup

### Step 8.1 - Validate required formats and remove stale references
Files:
- `tests/test_docling_ingestion_smoke.py`
- `tests/fixtures/*` (lightweight/generated fixtures strategy)
- cleanup references across `docs/`, `README.md`, `AGENTS.md`

Actions:
- Add smoke tests for: pdf, docx, xlsx, pptx, md, html, csv, image, xml (jats/uspto if feasible), vtt.
- Ensure tests assert non-empty extracted text and chunks created.
- Remove stale references to removed parser stack.

Validation:
- `python -m pytest -q tests/test_docling_ingestion_smoke.py`
- `python -m pytest -q`

## Rollback Guidance
- Create checkpoint commits after each phase:
  - `git add -A && git commit -m "spec011 phase X"`
- If a phase fails:
  - `git revert <phase-commit>` (preferred)
  - or reset to prior checkpoint in local branch before opening PR.

## Progress Update (Final)
- Phase 1 completed: Docling adapter and internal conversion models added.
- Phase 2 completed: Docling extractor bridge implemented and registry routing switched for required target formats.
- Phase 3 completed: Legacy migrated-format handlers removed from legacy extractor modules.
- Phase 4 completed: Docling locator metadata mapping added for chunk metadata and retrieval provenance.
- Phase 5 completed: CLI/server ingestion entrypoints verified to use shared ingestion pipeline/services.
- Phase 6 completed: Docling dependency/config cutover completed with runtime defaults and env overrides.
- Phase 7 completed: Documentation and developer workflow updated to docling-first guidance.
- Phase 8 completed: Docling ingestion smoke coverage added and stale parser-stack assumptions removed from tests/docs.

Final validation gate:
- `python -m pytest -q` passed.
- `python cmd/app.py --cli --help` passed.
- `python cmd/app.py --server --help` passed.
