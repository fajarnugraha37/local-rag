from __future__ import annotations

from app.document_conversion.models import ConvertedBlock, ConvertedDocument
from app.ingestion.extractors.base import ExtractorContext, MissingDependencyError, UnsupportedFormatError
from app.ingestion.extractors.docling_extractors import build_docling_extractor
from app.ingestion.extractors.registry import ExtractorRegistry, build_default_registry


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

    def _fake_convert_bytes(
        name: str, raw: bytes, *, ocr_enabled: bool = False
    ) -> ConvertedDocument:  # noqa: ARG001
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

    def _boom(name: str, raw: bytes, *, ocr_enabled: bool = False):  # noqa: ARG001
        raise RuntimeError("docling dependency is not available for pdf")

    monkeypatch.setattr(docling_adapter, "convert_bytes", _boom)
    try:
        registry.extract_from_bytes("sample.pdf", b"%PDF", _ctx())
    except MissingDependencyError:
        pass
    else:
        raise AssertionError("expected MissingDependencyError")


def test_docling_ocr_disabled_maps_to_skipped_unsupported(monkeypatch) -> None:
    registry = ExtractorRegistry()
    registry.register_extension(".pdf", build_docling_extractor(doc_type="pdf"))

    from app.document_conversion import docling_adapter

    def _boom(name: str, raw: bytes, *, ocr_enabled: bool = False):  # noqa: ARG001
        raise RuntimeError("OCR disabled; PDF appears scanned/image-only for 'sample.pdf'.")

    monkeypatch.setattr(docling_adapter, "convert_bytes", _boom)
    try:
        registry.extract_from_bytes("sample.pdf", b"%PDF", _ctx())
    except UnsupportedFormatError:
        pass
    else:
        raise AssertionError("expected UnsupportedFormatError")


def test_docling_empty_pdf_without_ocr_maps_to_unsupported(monkeypatch) -> None:
    registry = ExtractorRegistry()
    registry.register_extension(".pdf", build_docling_extractor(doc_type="pdf"))

    from app.document_conversion import docling_adapter

    def _boom(name: str, raw: bytes, *, ocr_enabled: bool = False):  # noqa: ARG001
        raise RuntimeError("docling returned empty output for format 'pdf'")

    monkeypatch.setattr(docling_adapter, "convert_bytes", _boom)
    try:
        registry.extract_from_bytes("sample.pdf", b"%PDF", _ctx())
    except UnsupportedFormatError:
        pass
    else:
        raise AssertionError("expected UnsupportedFormatError")


def test_required_extensions_resolve_to_docling_extractor() -> None:
    registry = build_default_registry()
    required = [
        "sample.pdf",
        "sample.docx",
        "sample.xlsx",
        "sample.pptx",
        "sample.md",
        "sample.markdown",
        "sample.mdx",
        "sample.adoc",
        "sample.asciidoc",
        "sample.tex",
        "sample.html",
        "sample.xhtml",
        "sample.csv",
        "sample.xml",
        "sample.vtt",
        "sample.png",
        "sample.jpg",
        "sample.jpeg",
        "sample.tiff",
        "sample.bmp",
        "sample.webp",
        "sample.docling.json",
    ]
    for path in required:
        extractor = registry.resolve(path)
        assert extractor.name == "docling", path
