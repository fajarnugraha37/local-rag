from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from app.document_conversion.models import ConvertedBlock, ConvertedDocument

_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "tiff", "bmp", "webp"}
_DOCLING_TARGET_EXTENSIONS = {
    "pdf",
    "docx",
    "xlsx",
    "pptx",
    "md",
    "markdown",
    "mdx",
    "adoc",
    "asciidoc",
    "tex",
    "html",
    "xhtml",
    "csv",
    "vtt",
    "xml",
    "json",
    *_IMAGE_EXTENSIONS,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _content_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file_extension(name: str) -> str:
    return os.path.splitext(name or "")[1].lower().lstrip(".")


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def _looks_like_vtt(text: str) -> bool:
    return text.lstrip().startswith("WEBVTT")


def _looks_like_xhtml(text: str) -> bool:
    lower = text.lower()
    return "<html" in lower and "xhtml" in lower


def _xml_schema_hint(text: str) -> Optional[str]:
    lower = text.lower()
    if "jats" in lower or "journalpublishing" in lower or "<article" in lower:
        return "jats"
    if "us-patent" in lower or "patent-" in lower or "<patent" in lower:
        return "uspto"
    return None


def _looks_like_docling_json(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("schema_name") == "docling_document":
        return True
    if "document" in payload and isinstance(payload["document"], dict):
        return True
    if "texts" in payload and isinstance(payload["texts"], list):
        return True
    return False


def detect_source_format(name: str, raw: bytes) -> str:
    ext = _file_extension(name)
    if ext in _IMAGE_EXTENSIONS:
        return ext
    if ext in _DOCLING_TARGET_EXTENSIONS and ext not in {"xml", "json", "html"}:
        return ext

    text = _decode_text(raw[:100000])

    if ext == "json":
        try:
            parsed = json.loads(text)
            if _looks_like_docling_json(parsed):
                return "docling-json"
        except Exception:
            pass
        return "json"

    if ext in {"xml"}:
        hint = _xml_schema_hint(text)
        if hint == "jats":
            return "xml-jats"
        if hint == "uspto":
            return "xml-uspto"
        return "xml"

    if ext in {"html", "xhtml"}:
        if _looks_like_xhtml(text):
            return "xhtml"
        return "html"

    if _looks_like_vtt(text):
        return "vtt"
    return ext or "unknown"


def _markdown_to_blocks(text_markdown: str) -> List[ConvertedBlock]:
    lines = [line.strip() for line in text_markdown.splitlines()]
    blocks: List[ConvertedBlock] = []
    heading_path: List[str] = []
    for line in lines:
        if not line:
            continue
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        locator: Dict[str, Any] = {}
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_path = heading_path[: max(level - 1, 0)] + [title]
            locator = {"heading_path": " > ".join(heading_path)}
        elif heading_path:
            locator = {"heading_path": " > ".join(heading_path)}
        blocks.append(ConvertedBlock(text=line, locator=locator))
    if not blocks and text_markdown.strip():
        blocks.append(ConvertedBlock(text=text_markdown.strip(), locator={}))
    return blocks


def _convert_with_docling(name: str, raw: bytes, source_format: str) -> ConvertedDocument:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"docling dependency is not available for {source_format}") from exc

    converter = DocumentConverter()
    result = converter.convert(raw)
    markdown = ""
    if hasattr(result, "document") and result.document is not None:
        doc = result.document
        if hasattr(doc, "export_to_markdown"):
            markdown = (doc.export_to_markdown() or "").strip()
        elif hasattr(doc, "to_markdown"):
            markdown = (doc.to_markdown() or "").strip()
    if not markdown:
        markdown = str(getattr(result, "text", "") or "").strip()
    if not markdown:
        raise RuntimeError(f"docling returned empty output for format '{source_format}'")

    return ConvertedDocument(text_markdown=markdown, blocks=_markdown_to_blocks(markdown))


def convert_bytes(name: str, raw: bytes) -> ConvertedDocument:
    source_format = detect_source_format(name, raw)
    extracted_at = _utc_now_iso()
    warnings: List[str] = []

    markdown = ""
    blocks: List[ConvertedBlock] = []

    if source_format in {
        "md",
        "markdown",
        "mdx",
        "adoc",
        "asciidoc",
        "tex",
        "csv",
        "html",
        "xhtml",
        "vtt",
        "xml",
        "xml-jats",
        "xml-uspto",
        "json",
        "docling-json",
    }:
        markdown = _decode_text(raw).strip()
        blocks = _markdown_to_blocks(markdown)
    else:
        try:
            converted = _convert_with_docling(name=name, raw=raw, source_format=source_format)
            markdown = converted.text_markdown
            blocks = converted.blocks
            warnings.extend(converted.warnings)
        except Exception as exc:
            text_fallback = _decode_text(raw).strip()
            if text_fallback:
                markdown = text_fallback
                blocks = _markdown_to_blocks(markdown)
                warnings.append(str(exc))
            else:
                raise

    if not markdown.strip():
        raise RuntimeError(f"conversion produced empty text for '{name}'")

    metadata = {
        "source_path": name,
        "source_format": source_format,
        "content_hash": _content_hash(raw),
        "extracted_at": extracted_at,
    }
    return ConvertedDocument(
        text_markdown=markdown, metadata=metadata, blocks=blocks, warnings=warnings
    )


def convert_file(path: str) -> ConvertedDocument:
    with open(path, "rb") as handle:
        raw = handle.read()
    converted = convert_bytes(path, raw)
    converted.metadata["source_path"] = path
    return converted


def convert_batch(paths: List[str]) -> Iterable[ConvertedDocument]:
    for path in paths:
        yield convert_file(path)
