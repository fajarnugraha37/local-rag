from __future__ import annotations

import json
import os
import re
from typing import List, Optional

from .base import ExtractedDocument, ExtractedUnit, ExtractorContext
from .utils import (
    batch_lines,
    json_pretty,
    normalize_text,
    read_bytes,
    read_text,
    safe_decode,
    strip_json_comments,
)


def extract_json(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    warnings: List[str] = []
    if raw_bytes is None:
        raw_text, _ = read_text(path, max_bytes=context.max_bytes)
    else:
        decoded, _ = safe_decode(raw_bytes)
        raw_text = normalize_text(decoded)

    lower_name = os.path.basename(path).lower()
    is_jsonc = lower_name.endswith(".jsonc")

    source = strip_json_comments(raw_text) if is_jsonc else raw_text
    try:
        data = json.loads(source)
        text = json_pretty(data)
    except Exception as exc:
        warnings.append(f"json_parse_failed: {exc}")
        text = normalize_text(raw_text)

    doc_type = (
        "openapi" if lower_name.endswith(".openapi.json") else ("jsonc" if is_jsonc else "json")
    )
    return ExtractedDocument(doc_type=doc_type, units=[ExtractedUnit(text=text)], warnings=warnings)


def extract_json_lines(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    warnings: List[str] = []
    if raw_bytes is None:
        text, _ = read_text(path, max_bytes=context.max_bytes)
    else:
        decoded, _ = safe_decode(raw_bytes)
        text = normalize_text(decoded)

    units: List[ExtractedUnit] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if idx > context.max_objects:
            warnings.append(f"jsonl_truncated_at_max_objects={context.max_objects}")
            break
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
            payload = json_pretty(data)
        except Exception:
            payload = normalize_text(stripped)
            warnings.append(f"jsonl_line_parse_failed_at_line={idx}")
        units.append(
            ExtractedUnit(text=payload, metadata={"row_number": idx, "json_pointer": f"/{idx}"})
        )

    return ExtractedDocument(doc_type="jsonl", units=units, warnings=warnings)


def extract_svg(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    if raw_bytes is None:
        raw = read_bytes(path, max_bytes=context.max_bytes)
    else:
        raw = raw_bytes
    decoded, _ = safe_decode(raw)
    stripped = re.sub(r"<[^>]+>", " ", decoded)
    text = normalize_text(stripped)
    return ExtractedDocument(doc_type="svg", units=[ExtractedUnit(text=text)])


def extract_har(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    warnings: List[str] = []
    doc = extract_json(path, raw_bytes, context)
    try:
        payload = json.loads(doc.units[0].text)
    except Exception:
        return ExtractedDocument(
            doc_type="har", units=doc.units, warnings=[*doc.warnings, "har_json_decode_failed"]
        )

    entries = payload.get("log", {}).get("entries", []) if isinstance(payload, dict) else []
    units: List[ExtractedUnit] = []
    for idx, entry in enumerate(entries, start=1):
        if idx > context.max_objects:
            warnings.append(f"har_truncated_at_max_objects={context.max_objects}")
            break
        request = (entry or {}).get("request", {})
        response = (entry or {}).get("response", {})
        unit_text = (
            f"Request URL: {request.get('url', '')}\n"
            f"Method: {request.get('method', '')}\n"
            f"Status: {response.get('status', '')}\n"
            f"MimeType: {(response.get('content') or {}).get('mimeType', '')}"
        )
        units.append(ExtractedUnit(text=normalize_text(unit_text), metadata={"row_number": idx}))

    if not units:
        units = [ExtractedUnit(text=doc.units[0].text)]
    return ExtractedDocument(doc_type="har", units=units, warnings=[*doc.warnings, *warnings])


def extract_log(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    if raw_bytes is None:
        text, _ = read_text(path, max_bytes=context.max_bytes)
    else:
        decoded, _ = safe_decode(raw_bytes)
        text = normalize_text(decoded)
    chunks = batch_lines(text.splitlines(), max_chars=4000)
    return ExtractedDocument(doc_type="log", units=[ExtractedUnit(text=part) for part in chunks])
