"""Citation marker extraction, validation, and rendering helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Set


_CITATION_RE = re.compile(r"\[(\d+)\]")


def extract_citation_ids(text: str) -> List[int]:
    if not text:
        return []
    return [int(match) for match in _CITATION_RE.findall(text)]


def validate_citation_ids(
    citation_ids: Iterable[int], sources: Iterable[Dict[str, Any]]
) -> Dict[str, Any]:
    valid_ids: Set[int] = {
        int(item.get("citation_index"))
        for item in (sources or [])
        if str(item.get("citation_index", "")).isdigit()
    }
    ids = list(citation_ids or [])
    invalid = sorted({cid for cid in ids if cid not in valid_ids})
    used_valid = sorted({cid for cid in ids if cid in valid_ids})
    return {
        "valid_ids": sorted(valid_ids),
        "used_valid_ids": used_valid,
        "invalid_ids": invalid,
        "is_valid": len(invalid) == 0,
    }


def strip_citation_markers(text: str) -> str:
    if not text:
        return ""
    cleaned = _CITATION_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+\n", "\n", cleaned)
    return cleaned.strip()


def _render_sources_section(
    sources: Iterable[Dict[str, Any]], max_sources: int, max_snippet_chars: int
) -> str:
    selected = list(sources or [])[: max(0, max_sources)]
    if not selected:
        return "Sources: none."
    lines = ["Sources:"]
    for src in selected:
        idx = src.get("citation_index")
        title = str(src.get("title") or "Untitled")
        locator = str(src.get("locator") or "").strip()
        snippet = str(src.get("snippet") or "").strip()
        if max_snippet_chars >= 0:
            snippet = snippet[:max_snippet_chars]
        suffix = f" ({locator})" if locator else ""
        lines.append(f"[{idx}] {title}{suffix}")
        if snippet:
            lines.append(f"  {snippet}")
    return "\n".join(lines)


def render_citation_output(
    answer: str,
    sources: Iterable[Dict[str, Any]],
    *,
    mode: str = "inline",
    max_sources: int = 8,
    max_snippet_chars: int = 240,
) -> Dict[str, Any]:
    mode = (mode or "inline").strip().lower()
    if mode not in {"none", "inline", "inline+sources"}:
        mode = "inline"

    source_list = list(sources or [])
    citation_ids = extract_citation_ids(answer or "")
    stats = validate_citation_ids(citation_ids, source_list)

    rendered_answer = (answer or "").strip()
    if mode == "none":
        rendered_answer = strip_citation_markers(rendered_answer)
    if not source_list and mode != "none":
        rendered_answer = strip_citation_markers(rendered_answer)
        if rendered_answer:
            rendered_answer = f"{rendered_answer}\n\n(Note: no sources were retrieved.)"
        else:
            rendered_answer = "(Note: no sources were retrieved.)"

    sources_text = ""
    if mode == "inline+sources":
        sources_text = _render_sources_section(
            source_list,
            max_sources=max_sources,
            max_snippet_chars=max_snippet_chars,
        )

    return {
        "answer": rendered_answer,
        "sources_text": sources_text,
        "stats": stats,
        "mode": mode,
    }
