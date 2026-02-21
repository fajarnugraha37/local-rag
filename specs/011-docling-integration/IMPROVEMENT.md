# Spec 011: Migrate Document Handling to Docling (No Backward Compatibility)

## Problem Statement (Grounded in Current Repo)
Current ingestion is a multi-parser stack wired through `app/ingestion/pipeline.py` + `app/ingestion/extractors/registry.py`, with format logic spread across:
- `app/ingestion/extractors/office.py` (`PyPDF2`, `python-docx`, `python-pptx`, `openpyxl`, `xlrd`, `olefile`)
- `app/ingestion/extractors/structured.py` (`csv`, `html`, `xml`, `bs4`, `lxml`)
- `app/ingestion/extractors/textual.py` (`markdown`, `mdx`, `adoc`, plus config/script text)

This creates inconsistent extraction quality, metadata coverage, and maintenance overhead. Required spec 011 formats are not fully covered today:
- Missing/partial: `.tex`, `.xhtml`, `.vtt`, image OCR formats (`.png/.jpg/.jpeg/.tiff/.bmp/.webp`), explicit USPTO/JATS handling, docling JSON.

## Mandatory Scan Summary

### Ingestion/extractor pipeline and routing
- Registry and allowlist: `app/ingestion/extractors/registry.py`
- Extraction contracts: `app/ingestion/extractors/base.py`
- Current handlers:
  - Text/config/code families: `app/ingestion/extractors/textual.py`
  - Office/binary: `app/ingestion/extractors/office.py`
  - Structured text/web/xml: `app/ingestion/extractors/structured.py`
  - Notebook/data tables: `app/ingestion/extractors/notebook_data.py`
- Pipeline orchestration: `app/ingestion/pipeline.py`

### Chunking and metadata
- Chunking logic: `app/ingestion/chunking.py`, token splitter in `app/context/token_chunking.py`
- Chunk metadata assembly in `_chunks_for_document` (`app/ingestion/pipeline.py`) includes:
  - `source_path`, `source_name`, `source_kind`, `extension`, `special_name`, `doc_type`
  - `content_hash`, `extracted_at`, `chunk_index`
  - unit metadata passthrough (currently `page_number`, `slide_number`, `sheet_name`, `row_number`, etc. where provided)

### Storage, IDs, namespace
- Vector store: `app/storage/chroma_vector_store.py` (single Chroma collection, metadata filters supported)
- Stable IDs: `app/storage/vector_ids.py` (`doc_id`, `chunk_id`, `vector_id`)
- Upsert + metadata namespace/doc/chunk wiring: `app/ingestion/vector_ingest_service.py`
- Doc registry: `app/ingestion/doc_registry_store.py`

### CLI/server ingestion entrypoints
- CLI:
  - `app/cli/ingest_files.py` -> `app/ingestion/file_ingest_gui.py` -> `ingest_paths`
  - `app/cli/ingest_folder.py` -> `app/ingestion/folder_ingest_cli.py` -> `app/ingestion/folder_ingest_service.py`
- Server:
  - Route handler: `app/http/handlers/ingestion.py`
  - HTTP server dispatch: `app/http/server.py`
  - Dependency wiring shell: `app/chat/streaming_server.py`
- SSE folder ingestion progress events already exist in `/ingest/folder` handler.

### Dependencies and tests
- Dependency files: `requirements.txt`, `pyproject.toml`
- Current parsing deps include: `PyPDF2`, `python-docx`, `openpyxl`, `python-pptx`, `xlrd`, `olefile`, `beautifulsoup4`, `lxml`
- Test framework: `pytest` (`pyproject.toml`)
- Relevant ingestion tests:
  - `tests/test_ingestion_extended_formats.py`
  - `tests/test_ingestion_server_routes.py`
  - `tests/test_smoke_ingest.py`
  - `tests/test_folder_scanner.py`
  - `tests/test_folder_ingest_idempotency.py`

## Scope: Formats to Migrate to Docling (Strict)
All extraction for these formats must go through Docling only:
- `pdf`
- `docx`
- `xlsx`
- `pptx`
- `md`, `markdown`, `mdx`
- `adoc`, `asciidoc`
- `tex`
- `html`, `xhtml`
- `csv`
- images: `png`, `jpeg`, `jpg`, `tiff`, `bmp`, `webp`
- `vtt`
- USPTO XML
- JATS XML
- docling JSON (serialized Docling document)

No backward compatibility: old non-docling handlers for these formats are removed.

## Target Design

### 1) Docling Adapter (single conversion source of truth)
Add:
- `app/document_conversion/docling_adapter.py`
- `app/document_conversion/models.py`

Adapter interface:
- `convert_file(path: str) -> ConvertedDocument`
- `convert_bytes(name: str, raw: bytes) -> ConvertedDocument`
- `convert_batch(paths: list[str]) -> Iterable[ConvertedDocument]` (optional but preferred)

`ConvertedDocument` includes:
- `text_markdown` (primary chunk input)
- `metadata`:
  - `source_path`, `source_format`, `content_hash`, `extracted_at`, `warnings`
  - `page_count`, `slide_count`, `sheet_names` (when available)
- `blocks` with locators (page/slide/heading/table/sheet/row/line/tag) where available

### 2) Primary chunking representation choice
Use **Docling Markdown export** as the primary representation for chunking.

Reason:
- Preserves headings and document structure across heterogeneous formats.
- Aligns with existing heading-aware split heuristics in `app/ingestion/chunking.py`.
- Better provenance anchors for citations than plain flattened text.

### 3) Registry integration
Replace targeted format routing in `app/ingestion/extractors/registry.py` to a Docling-backed extractor strategy.

Planned extractor layout:
- `app/ingestion/extractors/docling_extractors.py` (adapter bridge implementing `Extractor` contract)
- Keep non-target extractors only for non-docling formats (e.g. json/jsonl/har/log/ipynb/parquet/feather/arrow, config/script text)

### 4) Chunk metadata + provenance mapping
Normalize Docling block metadata to chunk metadata fields used downstream:
- Common: `doc_id`, `chunk_id`, `namespace`, `source`, `doc_type`, `chunk_index`
- Locators (best available):
  - PDF: `page_number`/`page_range`
  - PPTX: `slide_number`
  - DOCX/Markdown/Asciidoc/LaTeX/HTML: `heading_path` or `section_id`
  - XLSX/CSV: `sheet_name`, `row_range`
  - Images: `page_number=1`, `ocr=true`
  - XML (USPTO/JATS): `xml_schema` + `section_path`/`tag_path`
- Preserve compatibility with citation/retrieval code paths (`app/retrieval/provenance.py`, `app/retrieval/hybrid_search.py`)

## Cleanup Plan (No Backward Compatibility)
- Remove old extractor code paths for migrated formats:
  - `app/ingestion/extractors/office.py` (or reduce to non-target legacy only, then remove if unused)
  - CSV/HTML/XML legacy handlers from `app/ingestion/extractors/structured.py`
  - Markdown/Asciidoc/MDX legacy routing from `app/ingestion/extractors/textual.py`
- Remove now-obsolete config switches tied to removed parsers:
  - `ingest_enable_legacy_office` in `app/config/runtime_settings.py` and docs/config
- Update all call sites to Docling route only.

## Configuration Knobs + Defaults
Add Docling-focused settings in `app/config/runtime_settings.py` + `config.yaml`:
- `ingest_docling_enabled: true`
- `ingest_docling_export_format: "markdown"` (fixed default and preferred mode)
- `ingest_docling_device: "cpu"`
- `ingest_docling_enable_ocr: false`
- `ingest_docling_timeout_s: 30`
- `ingest_docling_max_pages: 200`
- `ingest_docling_max_slides: 300`
- `ingest_docling_max_tables: 2000`
- `ingest_docling_max_images: 200`
- reuse existing `ingest_max_bytes` guard

## Dependency Changes

### Add
- `docling` (single supported conversion engine for target formats)

### Remove (after migration and test pass)
- `PyPDF2`
- `python-docx`
- `openpyxl`
- `python-pptx`
- `xlrd`
- `olefile`
- `beautifulsoup4` and `lxml` for ingestion format extraction (retain only if still required elsewhere, e.g. `app/ingestion/email_ingest_job.py`)

## Documentation Updates Required
Update to match new reality:
- `docs/architecture.md`
- `docs/rag-pipeline.md`
- `docs/configuration.md`
- `docs/development.md`
- `README.md`
- `AGENTS.md`
- `Makefile`

## Definition of Done
- All listed spec 011 formats are routed exclusively through Docling.
- No old parser fallback remains for those formats.
- CLI and server ingestion paths (`/ingest/files`, `/ingest/upload`, `/ingest/folder`) use same Docling conversion flow.
- Chunk metadata includes useful locators/provenance when available.
- Tests validate routing + metadata mapping + smoke ingestion for required formats.
- Docs/README/AGENTS/Makefile are updated and accurate.

## Non-Goals
- Backward compatibility with old per-format extractors.
- Remote URL ingestion or git clone ingestion.
- Authn/authz changes.

## Risks and Mitigations
- Docling runtime/performance cost on large docs:
  - Mitigate with byte/page/slide/time limits and explicit warnings.
- OCR cost on images/PDF scans:
  - OCR default off; configurable.
- Metadata loss during migration:
  - Add explicit locator mapping tests and regression checks.
- Dependency/platform friction:
  - Document install caveats and provide `make install`/setup guidance.

## Progress and Completion Update

Spec 011 migration is complete across tasks `T001` through `T010`.

Implemented outcomes:
- Docling conversion foundation added under `app/document_conversion/`.
- Docling extractor bridge added under `app/ingestion/extractors/docling_extractors.py`.
- Registry routing cut over so required spec 011 formats resolve to Docling path.
- Legacy migrated-format handlers removed from legacy extractor modules.
- Chunk metadata/provenance mapping updated for page/slide/sheet/heading/xml locator fields.
- CLI and server ingestion entrypoints validated to use shared ingestion pipeline/services.
- Runtime settings and config updated with docling-first knobs/defaults.
- Tests added/updated:
  - `tests/test_docling_adapter.py`
  - `tests/test_docling_routing.py`
  - `tests/test_docling_metadata_mapping.py`
  - `tests/test_docling_ingestion_smoke.py`
  - updated `tests/test_ingestion_extended_formats.py`
- Docs and workflow updated (`docs/*.md`, `README.md`, `AGENTS.md`, `Makefile`).

Dependency note:
- Migrated-format parser dependencies were removed from runtime requirements.
- `xlrd` and `olefile` remain for non-target legacy `.xls/.doc/.ppt` support.
- `beautifulsoup4`/`lxml` remain used by email ingestion (`app/ingestion/email_ingest_job.py`) and are not part of migrated format extraction path.

Final acceptance validation:
- `python -m pytest -q` passed.
- `python cmd/app.py --cli --help` passed.
- `python cmd/app.py --server --help` passed.
