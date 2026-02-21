from __future__ import annotations

from app.document_conversion.docling_adapter import convert_bytes, convert_file, detect_source_format


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
    uspto = b'<?xml version="1.0"?><us-patent-grant><patent-title>x</patent-title></us-patent-grant>'
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
