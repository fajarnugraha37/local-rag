from __future__ import annotations

from typing import Any, Dict, Optional

from app.document_conversion import docling_adapter

from .base import (
    ExtractedDocument,
    ExtractedUnit,
    Extractor,
    ExtractorContext,
    ExtractorError,
    MissingDependencyError,
)


def _scalar_safe_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    safe: Dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe[key] = value
            continue
        safe[key] = str(value)
    return safe


def extract_docling(
    path: str,
    raw_bytes: Optional[bytes],
    context: ExtractorContext,  # noqa: ARG001
) -> ExtractedDocument:
    try:
        converted = (
            docling_adapter.convert_file(path)
            if raw_bytes is None
            else docling_adapter.convert_bytes(path, raw_bytes)
        )
    except Exception as exc:
        message = str(exc)
        lowered = message.lower()
        if "docling dependency is not available" in lowered or "no module named" in lowered:
            raise MissingDependencyError(message) from exc
        raise ExtractorError(message) from exc

    units = []
    for block in converted.blocks:
        text = (block.text or "").strip()
        if not text:
            continue
        unit_meta: Dict[str, Any] = {}
        unit_meta.update(_scalar_safe_metadata(block.locator))
        unit_meta.update(_scalar_safe_metadata(block.metadata))
        units.append(ExtractedUnit(text=text, metadata=unit_meta))

    if not units and converted.text_markdown.strip():
        units = [ExtractedUnit(text=converted.text_markdown.strip(), metadata={})]

    metadata = _scalar_safe_metadata(converted.metadata)
    metadata["source_format"] = metadata.get("source_format", "docling")
    return ExtractedDocument(
        doc_type=str(metadata.get("source_format", "docling")),
        units=units,
        metadata=metadata,
        warnings=list(converted.warnings),
    )


def build_docling_extractor(name: str = "docling", doc_type: str = "docling") -> Extractor:
    return Extractor(name=name, doc_type=doc_type, extract=extract_docling)
