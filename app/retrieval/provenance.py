"""Shared provenance models and helpers for citation-capable retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class Source:
    """Normalized source-level provenance for a retrieved chunk."""

    source_id: str
    citation_index: int
    namespace: str
    doc_id: str
    path: str
    title: str
    locator: str
    snippet: str


@dataclass(frozen=True)
class RetrievedChunk:
    """Retrieved chunk payload with score and source provenance."""

    chunk_id: str
    text: str
    score: float
    source: Source
    metadata: Dict[str, Any]


def normalize_title(value: Any, fallback: str = "Untitled") -> str:
    title = str(value or "").strip()
    if not title:
        return fallback
    return re.sub(r"\s+", " ", title)


def normalize_snippet(value: Any, max_chars: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars == 1:
        return "…"
    return text[: max_chars - 1].rstrip() + "…"


def normalize_locator(metadata: Optional[Dict[str, Any]]) -> str:
    data = metadata or {}
    page = data.get("page_number")
    if page not in (None, ""):
        return f"page {page}"
    slide = data.get("slide_number")
    if slide not in (None, ""):
        return f"slide {slide}"
    sheet = data.get("sheet_name")
    row = data.get("row_number")
    if sheet not in (None, "") and row not in (None, ""):
        return f"sheet {sheet} row {row}"
    if sheet not in (None, ""):
        return f"sheet {sheet}"
    chunk_index = data.get("chunk_index")
    if chunk_index not in (None, ""):
        return f"chunk {chunk_index}"
    return ""


def assign_source_indices(sources: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Assign deterministic `citation_index` and `source_id` preserving order."""
    assigned: List[Dict[str, Any]] = []
    for i, src in enumerate(sources, start=1):
        row = dict(src)
        row["citation_index"] = i
        row["source_id"] = f"S{i}"
        assigned.append(row)
    return assigned

