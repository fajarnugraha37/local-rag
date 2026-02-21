from __future__ import annotations

from app.document_conversion.models import ConvertedBlock, ConvertedDocument
from app.ingestion.extractors.base import ExtractorContext, MissingDependencyError
from app.ingestion.extractors.docling_extractors import build_docling_extractor
from app.ingestion.extractors.registry import ExtractorRegistry


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


def test_registry_can_call_docling_extractor(monkeypatch) -> None:
    registry = ExtractorRegistry()
    registry.register_extension(".pdf", build_docling_extractor(doc_type="pdf"))

    from app.document_conversion import docling_adapter

    def _fake_convert_bytes(name: str, raw: bytes) -> ConvertedDocument:  # noqa: ARG001
        return ConvertedDocument(
            text_markdown="# Title\n\nhello",
            metadata={
                "source_path": name,
                "source_format": "pdf",
                "content_hash": "abc",
                "extracted_at": "2026-01-01T00:00:00+00:00",
            },
            blocks=[
                ConvertedBlock(
                    text="hello",
                    locator={"page_number": 1},
                    metadata={"heading_path": ["Title"]},
                )
            ],
        )

    monkeypatch.setattr(docling_adapter, "convert_bytes", _fake_convert_bytes)
    doc = registry.extract_from_bytes("sample.pdf", b"%PDF", _ctx())

    assert doc.doc_type == "pdf"
    assert len(doc.units) == 1
    assert doc.units[0].metadata["page_number"] == 1
    assert isinstance(doc.units[0].metadata["heading_path"], str)


def test_docling_dependency_error_maps_to_missing_dependency(monkeypatch) -> None:
    registry = ExtractorRegistry()
    registry.register_extension(".pdf", build_docling_extractor(doc_type="pdf"))

    from app.document_conversion import docling_adapter

    def _boom(name: str, raw: bytes):  # noqa: ARG001
        raise RuntimeError("docling dependency is not available for pdf")

    monkeypatch.setattr(docling_adapter, "convert_bytes", _boom)
    try:
        registry.extract_from_bytes("sample.pdf", b"%PDF", _ctx())
    except MissingDependencyError:
        pass
    else:
        raise AssertionError("expected MissingDependencyError")
