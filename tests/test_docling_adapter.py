from __future__ import annotations

from app.document_conversion.docling_adapter import convert_bytes, convert_file, detect_source_format
from app.document_conversion.models import ConvertedBlock, ConvertedDocument


def test_convert_bytes_markdown_has_required_metadata() -> None:
    raw = b"# Title\n\nBody text"
    converted = convert_bytes("fixture.md", raw)

    assert converted.text_markdown
    assert converted.blocks
    assert converted.metadata["source_path"] == "fixture.md"
    assert converted.metadata["source_format"] == "md"
    assert converted.metadata["content_hash"]
    assert converted.metadata["extracted_at"]


def test_detect_source_format_xml_hints_and_docling_json() -> None:
    jats = b'<?xml version="1.0"?><article xmlns="http://jats.nlm.nih.gov">x</article>'
    uspto = (
        b'<?xml version="1.0"?><us-patent-grant><patent-title>x</patent-title></us-patent-grant>'
    )
    docling_json = b'{"schema_name":"docling_document","texts":["a"]}'

    assert detect_source_format("sample.xml", jats) == "xml-jats"
    assert detect_source_format("sample.xml", uspto) == "xml-uspto"
    assert detect_source_format("sample.json", docling_json) == "docling-json"


def test_convert_file_produces_non_empty_output(tmp_path) -> None:
    path = tmp_path / "fixture.vtt"
    path.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nhello", encoding="utf-8")

    converted = convert_file(str(path))
    assert converted.text_markdown
    assert converted.metadata["source_path"] == str(path)
    assert converted.metadata["source_format"] == "vtt"


def test_convert_bytes_pdf_tries_docling_without_ocr(monkeypatch) -> None:
    from app.document_conversion import docling_adapter

    called = {"value": False}

    def _fake_convert_with_docling(name: str, raw: bytes, source_format: str) -> ConvertedDocument:  # noqa: ARG001
        called["value"] = True
        return ConvertedDocument(
            text_markdown="Extracted PDF text",
            blocks=[ConvertedBlock(text="Extracted PDF text", locator={}, metadata={})],
        )

    monkeypatch.setattr(docling_adapter, "_convert_with_docling", _fake_convert_with_docling)
    converted = convert_bytes("sample.pdf", b"%PDF-sample", ocr_enabled=False)
    assert called["value"] is True
    assert "Extracted PDF text" in converted.text_markdown
