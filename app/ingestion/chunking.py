from __future__ import annotations

import re
from typing import Dict, List

from app.context import token_chunking


def _split_heading_blocks(text: str) -> List[str]:
    lines = (text or "").splitlines()
    blocks: List[str] = []
    current: List[str] = []

    heading_pattern = re.compile(r"^(#{1,6}\s+|=+\s*$|-+\s*$|\*\s+|\d+\.\s+|\.\.|[A-Z][A-Za-z\s]{0,80}:$)")
    for line in lines:
        if heading_pattern.match(line.strip()) and current:
            blocks.append("\n".join(current).strip())
            current = [line]
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip())

    return [block for block in blocks if block]


def _split_paragraphs(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text or "") if part.strip()]


def split_for_doc_type(text: str, doc_type: str) -> List[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []

    if doc_type in {"markdown", "mdx", "rst", "adoc"}:
        heading_parts = _split_heading_blocks(normalized)
        pieces: List[str] = []
        for part in heading_parts:
            pieces.extend(_split_paragraphs(part))
        return pieces or [normalized]

    if doc_type in {"jsonl", "csv", "tsv", "ipynb", "parquet", "feather", "arrow", "har"}:
        return [normalized]

    if doc_type == "log":
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        out: List[str] = []
        buf: List[str] = []
        for line in lines:
            if re.match(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}", line) and buf:
                out.append("\n".join(buf))
                buf = [line]
            else:
                buf.append(line)
        if buf:
            out.append("\n".join(buf))
        return out or [normalized]

    return _split_paragraphs(normalized) or [normalized]


def chunk_text_with_tokens(text: str, *, max_tokens: int, overlap_tokens: int) -> List[str]:
    chunks = token_chunking.chunk_by_tokens(
        text,
        max_tokens=max_tokens,
        overlap=overlap_tokens,
    )
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def chunk_unit(text: str, doc_type: str, *, max_tokens: int, overlap_tokens: int) -> List[str]:
    parts = split_for_doc_type(text, doc_type)
    output: List[str] = []
    for part in parts:
        output.extend(chunk_text_with_tokens(part, max_tokens=max_tokens, overlap_tokens=overlap_tokens))
    return output


def normalize_extension(file_name: str) -> Dict[str, str]:
    lower = file_name.lower()
    special_name = ""
    extension = ""
    if lower in {"dockerfile", "makefile"}:
        special_name = lower
    else:
        match = re.search(r"(\.[^.]+)$", lower)
        extension = match.group(1) if match else ""
    return {"extension": extension, "special_name": special_name}
