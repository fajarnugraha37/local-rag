from __future__ import annotations

import io
import json
import os
import re
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Tuple


def normalize_text(raw: str) -> str:
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_decode(raw: bytes) -> Tuple[str, str]:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding), encoding
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def read_bytes(path: str, *, max_bytes: int) -> bytes:
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"file exceeds max bytes ({size} > {max_bytes}): {path}")
    with open(path, "rb") as handle:
        return handle.read()


def read_text(path: str, *, max_bytes: int) -> Tuple[str, str]:
    raw = read_bytes(path, max_bytes=max_bytes)
    text, encoding = safe_decode(raw)
    return normalize_text(text), encoding


def strip_json_comments(text: str) -> str:
    # Lightweight JSONC stripper: removes // and /* */ comments while preserving quoted strings.
    out: List[str] = []
    i = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "/":
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def json_pretty(data: Any) -> str:
    return normalize_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def flatten_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for key, value in (meta or {}).items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            flat[key] = value
            continue
        if isinstance(value, (list, tuple, set)):
            flat[key] = ", ".join(str(v) for v in value)
            continue
        flat[key] = str(value)
    return flat


def check_zip_safety(raw: bytes, *, max_entries: int, max_uncompressed_bytes: int) -> Optional[str]:
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        return None
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) > max_entries:
            return f"zip entries exceed limit ({len(names)} > {max_entries})"
        total_uncompressed = sum(info.file_size for info in archive.infolist())
        if total_uncompressed > max_uncompressed_bytes:
            return (
                "zip uncompressed bytes exceed limit "
                f"({total_uncompressed} > {max_uncompressed_bytes})"
            )
    return None


def batch_lines(lines: Iterable[str], *, max_chars: int) -> List[str]:
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for line in lines:
        safe = (line or "").strip("\n")
        if not safe:
            continue
        extra = len(safe) + (1 if current else 0)
        if current and current_len + extra > max_chars:
            chunks.append("\n".join(current).strip())
            current = [safe]
            current_len = len(safe)
            continue
        current.append(safe)
        current_len += extra
    if current:
        chunks.append("\n".join(current).strip())
    return chunks
