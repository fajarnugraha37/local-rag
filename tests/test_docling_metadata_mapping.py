from __future__ import annotations

from app.document_conversion.models import ConvertedBlock, ConvertedDocument
from app.ingestion.extractors.base import ExtractedDocument, ExtractedUnit
from app.ingestion.extractors.base import ExtractorContext
from app.ingestion.extractors.docling_extractors import extract_docling
from app.ingestion.pipeline import _chunks_for_document, _context, build_options


def _ctx() -> ExtractorContext:
    return ExtractorContext(
        max_bytes=1024 * 1024,
        max_rows=1000,
        max_objects=1000,
        max_pages=200,
        max_slides=300,
        max_sheets=50,
        max_zip_entries=10000,
        max_zip_uncompressed_bytes=128 * 1024 * 1024,
        ingest_timeout_s=30,
        enable_parquet=True,
        enable_legacy_office=True,
        extracted_at="2026-01-01T00:00:00+00:00",
    )


def test_locator_metadata_survives_extractor_boundary(monkeypatch) -> None:
    from app.document_conversion import docling_adapter

    def _fake_convert_bytes(name: str, raw: bytes) -> ConvertedDocument:  # noqa: ARG001
        return ConvertedDocument(
            text_markdown="# Intro\nParagraph",
            metadata={
                "source_path": name,
                "source_format": "docx",
                "content_hash": "abc123",
                "extracted_at": "2026-01-01T00:00:00+00:00",
                "sheet_names": ["Sheet1", "Sheet2"],
            },
            blocks=[
                ConvertedBlock(
                    text="Paragraph",
                    locator={"page_number": 3, "heading_path": ["Intro"]},
                    metadata={"tags": ["a", "b"]},
                )
            ],
        )

    monkeypatch.setattr(docling_adapter, "convert_bytes", _fake_convert_bytes)
    doc = extract_docling("sample.docx", b"binary", _ctx())

    assert doc.units
    unit_meta = doc.units[0].metadata
    assert unit_meta["page_number"] == 3
    assert isinstance(unit_meta["heading_path"], str)
    assert isinstance(unit_meta["tags"], str)
    assert isinstance(doc.metadata["sheet_names"], str)


def test_docling_locator_metadata_maps_into_chunks() -> None:
    doc = ExtractedDocument(
        doc_type="docling",
        units=[
            ExtractedUnit(
                text="# Heading\n\nBody",
                metadata={
                    "page_number": 2,
                    "page_range": [2, 3],
                    "heading_path": ["Heading", "Sub"],
                    "sheet_name": "Sheet1",
                    "row_range": [10, 12],
                    "xml_schema": "jats",
                    "section_path": ["body", "sec-1"],
                },
            )
        ],
        metadata={"source_format": "pdf"},
    )
    options = build_options(chunk_max_tokens=200, chunk_overlap_tokens=20)
    chunks = _chunks_for_document("sample.pdf", doc, options, _context(options))
    assert chunks
    meta = chunks[0]["metadata"]
    assert meta["page_number"] == 2
    assert meta["page_range"] == "2-3"
    assert meta["heading_path"] == "Heading > Sub"
    assert meta["row_range"] == "10-12"
    assert meta["section_path"] == "body > sec-1"
