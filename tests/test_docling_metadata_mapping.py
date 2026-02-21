from __future__ import annotations

from app.document_conversion.models import ConvertedBlock, ConvertedDocument
from app.ingestion.extractors.base import ExtractorContext
from app.ingestion.extractors.docling_extractors import extract_docling


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
