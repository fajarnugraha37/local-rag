"""Citation-aware prompt composition shared by CLI and server chat paths."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from app.retrieval.provenance import normalize_snippet, normalize_title


STRICT_CITATION_INSTRUCTION = (
    "Use only the provided sources. Do not invent facts or citations. "
    "If the sources are insufficient, say so explicitly. "
    "When you use source-backed facts, cite them inline as [n]."
)


def build_source_blocks(
    retrieved_chunks: Iterable[Dict[str, Any]],
    *,
    max_sources: int | None = None,
    max_snippet_chars: int = 500,
) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    for row in retrieved_chunks:
        source = row.get("source") or {}
        citation_index = int(source.get("citation_index") or (len(blocks) + 1))
        block = {
            "citation_index": citation_index,
            "source_id": str(source.get("source_id") or f"S{citation_index}"),
            "title": normalize_title(source.get("title") or row.get("doc_id") or "Untitled"),
            "locator": str(source.get("locator") or "").strip(),
            "doc_id": str(source.get("doc_id") or row.get("doc_id") or ""),
            "namespace": str(source.get("namespace") or row.get("namespace") or ""),
            "path": str(source.get("path") or row.get("source_path") or ""),
            "snippet": normalize_snippet(
                source.get("snippet") or row.get("text") or "", max_chars=max_snippet_chars
            ),
        }
        blocks.append(block)
        if max_sources is not None and len(blocks) >= max_sources:
            break
    return blocks


def format_source_blocks_text(source_blocks: Iterable[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for block in source_blocks:
        locator = block.get("locator")
        locator_part = f" | {locator}" if locator else ""
        lines.append(f"[{block['citation_index']}] {block['title']}{locator_part}")
        lines.append(
            f"doc_id={block['doc_id']} namespace={block['namespace']} path={block['path']}"
        )
        lines.append(str(block.get("snippet") or ""))
        lines.append("")
    return "\n".join(lines).strip()


def build_citation_prompt(
    question: str,
    retrieved_chunks: Iterable[Dict[str, Any]],
    *,
    max_sources: int | None = None,
    max_snippet_chars: int = 500,
) -> Tuple[str, List[Dict[str, Any]]]:
    source_blocks = build_source_blocks(
        retrieved_chunks,
        max_sources=max_sources,
        max_snippet_chars=max_snippet_chars,
    )
    if not source_blocks:
        return question, []

    source_text = format_source_blocks_text(source_blocks)
    user_text = (
        f"Question:\n{question}\n\n"
        f"Sources:\n{source_text}\n\n"
        f"Instructions:\n{STRICT_CITATION_INSTRUCTION}"
    )
    return user_text, source_blocks
