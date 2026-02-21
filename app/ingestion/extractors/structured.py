from __future__ import annotations

import csv
import io
import json
import os
from typing import List, Optional

from bs4 import BeautifulSoup

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


def extract_csv_tsv(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    warnings: List[str] = []
    lower_name = os.path.basename(path).lower()
    delimiter = "\t" if lower_name.endswith(".tsv") else ","

    if raw_bytes is None:
        raw = read_bytes(path, max_bytes=context.max_bytes)
    else:
        raw = raw_bytes

    decoded, _ = safe_decode(raw)
    stream = io.StringIO(decoded)
    reader = csv.DictReader(stream, delimiter=delimiter)

    units: List[ExtractedUnit] = []
    headers = reader.fieldnames or []
    if not headers:
        return ExtractedDocument(doc_type="tsv" if delimiter == "\t" else "csv", units=[])

    for idx, row in enumerate(reader, start=1):
        if idx > context.max_rows:
            warnings.append(f"csv_truncated_at_max_rows={context.max_rows}")
            break
        pairs = [f"{key}: {row.get(key, '')}" for key in headers]
        text = "\n".join(["Headers: " + ", ".join(headers), "Row:", *pairs])
        units.append(ExtractedUnit(text=normalize_text(text), metadata={"row_number": idx}))

    doc_type = "tsv" if delimiter == "\t" else "csv"
    return ExtractedDocument(doc_type=doc_type, units=units, warnings=warnings)


def extract_html_svg(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    if raw_bytes is None:
        raw = read_bytes(path, max_bytes=context.max_bytes)
    else:
        raw = raw_bytes
    decoded, _ = safe_decode(raw)

    soup = BeautifulSoup(decoded, "lxml")
    for tag in soup(["script", "style"]):
        tag.extract()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    body = soup.get_text("\n", strip=True)
    full_text = normalize_text((f"Title: {title}\n\n{body}" if title else body))

    lower_name = os.path.basename(path).lower()
    doc_type = "svg" if lower_name.endswith(".svg") else "html"
    return ExtractedDocument(doc_type=doc_type, units=[ExtractedUnit(text=full_text)])


def extract_xml(
    path: str, raw_bytes: Optional[bytes], context: ExtractorContext
) -> ExtractedDocument:
    warnings: List[str] = []
    if raw_bytes is None:
        raw = read_bytes(path, max_bytes=context.max_bytes)
    else:
        raw = raw_bytes

    try:
        from lxml import etree

        parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=True)
        root = etree.fromstring(raw, parser=parser)
        text_parts = []
        for elem in root.iter():
            if elem.text and elem.text.strip():
                text_parts.append(elem.text.strip())
            if elem.tail and elem.tail.strip():
                text_parts.append(elem.tail.strip())
        text = normalize_text("\n".join(text_parts))
    except Exception as exc:
        decoded, _ = safe_decode(raw)
        text = normalize_text(decoded)
        warnings.append(f"xml_parse_failed_fallback_text: {exc}")

    return ExtractedDocument(doc_type="xml", units=[ExtractedUnit(text=text)], warnings=warnings)


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
