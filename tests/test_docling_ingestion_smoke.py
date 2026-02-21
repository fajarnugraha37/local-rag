from __future__ import annotations

from app.config import runtime_settings as settings
from app.document_conversion.models import ConvertedBlock, ConvertedDocument
from app.ingestion import vector_ingest_service
from app.ingestion.pipeline import build_options, ingest_uploaded_files


def _fake_embed(*args, **kwargs):
    return {"embedding": [0.1, 0.2, 0.3, 0.4], "model": "fake", "used_fallback": False}


def _configure_store(tmp_path):
    settings.CONFIG["vector_db_persist_dir"] = str(tmp_path / "chroma")
    settings.CONFIG["vector_db_collection"] = "test_docling_ingestion_smoke"
    settings.CONFIG["embedding_dim"] = 4
    settings.CONFIG["vector_db_batch_size"] = 8


def test_docling_ingestion_smoke_for_required_formats(tmp_path, monkeypatch) -> None:
    _configure_store(tmp_path)
    monkeypatch.setattr(vector_ingest_service, "embed_text", _fake_embed)

    from app.document_conversion import docling_adapter

    called: list[str] = []

    def _fake_convert_bytes(name: str, raw: bytes) -> ConvertedDocument:  # noqa: ARG001
        called.append(name)
        text = f"# Converted\n\n{name}"
        return ConvertedDocument(
            text_markdown=text,
            metadata={
                "source_path": name,
                "source_format": "docling-smoke",
                "content_hash": "abc123",
                "extracted_at": "2026-01-01T00:00:00+00:00",
            },
            blocks=[ConvertedBlock(text=text, locator={"page_number": 1}, metadata={})],
        )

    monkeypatch.setattr(docling_adapter, "convert_bytes", _fake_convert_bytes)

    uploaded = [
        ("fixture.pdf", b"bin"),
        ("fixture.docx", b"bin"),
        ("fixture.xlsx", b"bin"),
        ("fixture.pptx", b"bin"),
        ("fixture.md", b"# md"),
        ("fixture.mdx", b"# mdx"),
        ("fixture.adoc", b"= adoc"),
        ("fixture.tex", b"\\section{Intro}"),
        ("fixture.html", b"<html><body>hi</body></html>"),
        ("fixture.xhtml", b"<html xmlns='http://www.w3.org/1999/xhtml'></html>"),
        ("fixture.csv", b"a,b\n1,2"),
        ("fixture.vtt", b"WEBVTT\n\n00:00.000 --> 00:01.000\nhello"),
        ("fixture.xml", b"<article>jats text</article>"),
        ("fixture.png", b"png"),
        ("fixture.jpg", b"jpg"),
        ("fixture.jpeg", b"jpeg"),
        ("fixture.tiff", b"tiff"),
        ("fixture.bmp", b"bmp"),
        ("fixture.webp", b"webp"),
        ("fixture.docling.json", b'{"schema_name":"docling_document","texts":["x"]}'),
    ]

    summary = ingest_uploaded_files(uploaded, options=build_options())
    assert summary["failed"] == 0
    assert summary["extracted"] == len(uploaded)
    assert summary["total_chunks"] > 0
    assert len(called) == len(uploaded)
