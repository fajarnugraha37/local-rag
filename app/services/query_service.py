from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, Generator

from openai import OpenAI

from app.chat.citation_formatter import render_citation_output
from app.chat.streaming_llm_client import stream_chat_with_continuation
from app.common import stream_protocol as protocol
from app.repositories.sqlite.runs_repo import RunsRepository
from app.retrieval import heuristic_reranker
from app.retrieval import hybrid_search as retrieval

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}


def _query_terms(query: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", (query or "").lower())
    terms = [tok for tok in tokens if tok not in _STOPWORDS and len(tok) > 2]
    return terms


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _clean_repetitive_phrases(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\bThe final answer is\b[:\s]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bFinal answer\b[:\s]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(Note:[^)]+\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bAs an AI[^.]*\.", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:\[[0-9]+\]\s*){2,}$", "", cleaned).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _dedupe_sentences(sentences: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for sent in sentences:
        key = re.sub(r"[^a-z0-9]+", "", sent.lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(sent)
    return out


def _ensure_trailing_citations(text: str, sources: list[dict[str, Any]]) -> str:
    if not sources:
        return text
    cited = sorted(
        {
            int(src.get("citation_index"))
            for src in sources
            if str(src.get("citation_index") or "").isdigit()
        }
    )
    if not cited:
        return text
    existing = {int(x) for x in re.findall(r"\[(\d+)\]", text)}
    if existing:
        return text
    top = cited[:2]
    return f"{text.rstrip()} [{' '.join(f'[{i}]' for i in top)}]"


def _normalize_final_answer(text: str, sources: list[dict[str, Any]]) -> str:
    cleaned = _clean_repetitive_phrases(text)
    if not cleaned:
        return cleaned
    sentences = _dedupe_sentences(_split_sentences(cleaned))
    if not sentences:
        return cleaned
    # Force concise final style: keep 2-3 sentences.
    kept = sentences[:3]
    if len(kept) == 1 and len(cleaned.split()) > 30:
        # If model returned one long run-on line, hard-wrap as one concise sentence.
        kept = [cleaned]
    normalized = " ".join(kept).strip()
    normalized = _ensure_trailing_citations(normalized, sources)
    return normalized


def _source_text(src: dict[str, Any]) -> str:
    return " ".join(
        [
            str(src.get("title") or ""),
            str(src.get("doc_id") or ""),
            str(src.get("locator") or ""),
            str(src.get("snippet") or ""),
        ]
    ).lower()


def _filter_sources_for_query(
    query: str,
    sources: list[dict[str, Any]],
    *,
    max_sources: int,
) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    if not terms:
        return sources[:max_sources]

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for idx, src in enumerate(sources):
        haystack = _source_text(src)
        hit_count = sum(1 for term in terms if term in haystack)
        scored.append((hit_count, -idx, src))

    scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
    focused = [row[2] for row in scored if row[0] > 0]
    if focused:
        return focused[:max_sources]
    return sources[:max_sources]


def _extract_sources(results: list[dict], max_sources: int = 8) -> list[dict]:
    sources: list[dict] = []
    seen = set()
    for row in results:
        src = row.get("source")
        if not isinstance(src, dict):
            continue
        idx = src.get("citation_index")
        key = (idx, src.get("doc_id"), src.get("path"))
        if key in seen:
            continue
        seen.add(key)
        sources.append(src)
        if len(sources) >= max_sources:
            break
    return sources


def _build_retrieval_answer(sources: list[dict]) -> str:
    if not sources:
        return "No relevant sources found."
    lines = ["Retrieved relevant sources:"]
    for src in sources:
        idx = src.get("citation_index")
        title = src.get("title") or src.get("doc_id") or "Untitled"
        snippet = str(src.get("snippet") or "").strip()
        if snippet:
            lines.append(f"- {title}: {snippet} [{idx}]")
        else:
            lines.append(f"- {title} [{idx}]")
    return "\n".join(lines)


def _build_focused_fallback_answer(query: str, sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "I could not find enough relevant source text to answer that question."
    def _compact_snippet(src: dict[str, Any], max_chars: int = 180) -> str:
        text = " ".join(str(src.get("snippet") or "").split())
        if not text:
            return ""
        # Keep first clause for clearer fallback output.
        split_idx = len(text)
        for sep in [".", ";", ":"]:
            pos = text.find(sep)
            if pos > 20:
                split_idx = min(split_idx, pos + 1)
        text = text[:split_idx].strip()
        if len(text) > max_chars:
            return text[: max_chars - 1].rstrip() + "..."
        return text

    first = sources[0]
    second = sources[1] if len(sources) > 1 else None
    idx1 = first.get("citation_index")
    idx2 = second.get("citation_index") if second else idx1
    s1 = _compact_snippet(first)
    s2 = _compact_snippet(second) if second else ""

    q = query.strip()
    if not s1:
        return f"Definition: I could not extract a clear definition for \"{q}\" from the top sources [{idx1}]."

    definition = f"Definition: {s1} [{idx1}]"
    if s2:
        explanation = f"Explanation: In context, this means {s2.lower()} [{idx2}]"
    else:
        explanation = f"Explanation: This directly addresses \"{q}\" based on the most relevant source [{idx1}]."
    return f"{definition}\n{explanation}"


def _build_llm_messages(query: str, sources: list[dict]) -> list[dict[str, str]]:
    source_lines: list[str] = []
    for src in sources:
        idx = src.get("citation_index")
        title = src.get("title") or src.get("doc_id") or "Untitled"
        snippet = str(src.get("snippet") or "").strip()
        locator = str(src.get("locator") or "").strip()
        parts = [f"[{idx}] {title}"]
        if locator:
            parts.append(f"({locator})")
        if snippet:
            parts.append(f": {snippet}")
        source_lines.append(" ".join(parts))

    system_message = (
        "You are a precise assistant. Answer the question using only the provided sources. "
        "If sources are insufficient, say so clearly. "
        "Use citation markers like [1], [2] inline for claims."
    )
    user_message = (
        f"Question:\n{query}\n\n"
        "Sources:\n"
        + ("\n".join(source_lines) if source_lines else "(none)")
        + "\n\nReturn only the final answer."
    )
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]


def _build_answer_with_llm(query: str, sources: list[dict], config: dict[str, Any]) -> str | None:
    if not sources:
        return "I could not find relevant sources for this question."
    model = str(config.get("ollama_model") or "").strip()
    if not model:
        return None
    api_cfg = config.get("ollama_api") or {}
    base_url = str(api_cfg.get("base_url") or "http://localhost:11434/v1")
    api_key = api_cfg.get("api_key")
    client = OpenAI(base_url=base_url, api_key=api_key)

    messages = _build_llm_messages(query, sources)
    try:
        final_text = ""
        streamed = []
        for event in stream_chat_with_continuation(
            client,
            model=model,
            messages=messages,
            per_call_max_tokens=int(
                config.get("per_call_max_tokens", config.get("chat_max_tokens", 4000))
            ),
            continuation_instruction=str(
                config.get(
                    "continuation_instruction",
                    "Continue exactly where you left off. Do not repeat prior text.",
                )
            ),
            max_continuations=int(config.get("max_continuations", 2)),
            timeout=float(config.get("provider_timeout_s", 300)),
            flush_interval_ms=int(config.get("flush_interval_ms", 250)),
            enable_thinking_summary=bool(config.get("enable_thinking_summary", False)),
            temperature=0.1,
        ):
            ev_name = str(event.get("event") or "")
            ev_data = event.get("data") or {}
            if ev_name == "final_delta":
                streamed.append(str(ev_data.get("text") or ""))
            elif ev_name == "done":
                final_text = str(ev_data.get("text") or "")

        text = (final_text or "".join(streamed)).strip()
        # Guard against incomplete short fragments from small/unstable local models.
        if len(text) < 40 or len(text.split()) < 8:
            return None
        low = text.lower()
        if "retrieved relevant sources" in low:
            return None
        return text
    except Exception:
        return None


class QueryService:
    def __init__(self, db_path: str, config: dict[str, Any]) -> None:
        self.runs_repo = RunsRepository(db_path)
        self.config = config

    def run_query(
        self,
        *,
        query: str,
        top_k: int = 6,
        rerank: bool = True,
        filters: dict[str, Any] | None = None,
        namespaces: list[str] | None = None,
        mode: str = "non_stream",
    ) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())

        self.runs_repo.create(
            run_id=run_id,
            trace_id=trace_id,
            query=query,
            mode=mode,
            status="running",
            inputs={
                "top_k": top_k,
                "rerank": bool(rerank),
                "filters": filters or {},
                "namespaces": namespaces or [],
            },
        )
        self.runs_repo.add_event(run_id, "meta", {"run_id": run_id, "trace_id": trace_id})

        results = retrieval.scored_chunks(
            query,
            top_k=int(top_k),
            rerank=bool(rerank),
            filters=filters,
            namespaces=namespaces,
        )

        max_sources = int(self.config.get("citation_max_sources", top_k))
        max_snippet_chars = int(self.config.get("citation_max_snippet_chars", 240))
        sources = _extract_sources(results, max_sources=max_sources)
        focused_sources = _filter_sources_for_query(query, sources, max_sources=max_sources)
        answer = _build_answer_with_llm(query, focused_sources, self.config) or _build_focused_fallback_answer(
            query, focused_sources
        )
        rendered = render_citation_output(
            answer,
            focused_sources,
            mode="inline",
            max_sources=max_sources,
            max_snippet_chars=max_snippet_chars,
        )

        final_answer = _normalize_final_answer(rendered.get("answer", answer), focused_sources)
        citation_stats = rendered.get("stats", {})

        self.runs_repo.add_step(
            run_id,
            step_index=0,
            summary="retrieval_completed",
            tool="hybrid_search",
            scores={"count": len(results)},
            doc_ids=[str(r.get("doc_id") or "") for r in results if r.get("doc_id")],
        )
        self.runs_repo.add_event(run_id, "final_delta", {"text": final_answer})
        self.runs_repo.add_event(run_id, "sources", {"sources": sources})
        self.runs_repo.add_event(run_id, "citation_stats", {"stats": citation_stats})
        self.runs_repo.add_event(run_id, "done", {"cancelled": False, "text": final_answer})

        self.runs_repo.update_result(
            run_id=run_id,
            status="done",
            answer=final_answer,
            citations=focused_sources,
            timings={"result_count": len(results)},
        )

        return {
            "query": query,
            "run_id": run_id,
            "trace_id": trace_id,
            "answer": final_answer,
            "sources": focused_sources,
            "citation_stats": citation_stats,
            "count": len(results),
            "results": results,
        }

    def stream_query(
        self,
        *,
        query: str,
        top_k: int = 6,
        rerank: bool = True,
        filters: dict[str, Any] | None = None,
        namespaces: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        run_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())

        self.runs_repo.create(
            run_id=run_id,
            trace_id=trace_id,
            query=query,
            mode="stream",
            status="running",
            inputs={
                "top_k": top_k,
                "rerank": bool(rerank),
                "filters": filters or {},
                "namespaces": namespaces or [],
            },
        )
        meta_event = protocol.meta(run_id=run_id, trace_id=trace_id, query=query)
        self.runs_repo.add_event(run_id, "meta", {"run_id": run_id, "trace_id": trace_id, "query": query})
        yield meta_event

        results = retrieval.scored_chunks(
            query,
            top_k=int(top_k),
            rerank=bool(rerank),
            filters=filters,
            namespaces=namespaces,
        )
        max_sources = int(self.config.get("citation_max_sources", top_k))
        max_snippet_chars = int(self.config.get("citation_max_snippet_chars", 240))
        sources = _extract_sources(results, max_sources=max_sources)
        focused_sources = _filter_sources_for_query(query, sources, max_sources=max_sources)

        self.runs_repo.add_step(
            run_id,
            step_index=0,
            summary="retrieval_completed",
            tool="hybrid_search",
            scores={"count": len(results)},
            doc_ids=[str(r.get("doc_id") or "") for r in results if r.get("doc_id")],
        )

        model = str(self.config.get("ollama_model") or "").strip()
        api_cfg = self.config.get("ollama_api") or {}
        base_url = str(api_cfg.get("base_url") or "http://localhost:11434/v1")
        api_key = api_cfg.get("api_key")
        client = OpenAI(base_url=base_url, api_key=api_key)
        messages = _build_llm_messages(query, focused_sources)

        final_text = ""
        streamed_any_delta = False
        try:
            for event in stream_chat_with_continuation(
                client,
                model=model,
                messages=messages,
                per_call_max_tokens=int(
                    self.config.get("per_call_max_tokens", self.config.get("chat_max_tokens", 4000))
                ),
                continuation_instruction=str(
                    self.config.get(
                        "continuation_instruction",
                        "Continue exactly where you left off. Do not repeat prior text.",
                    )
                ),
                max_continuations=int(self.config.get("max_continuations", 2)),
                timeout=float(self.config.get("provider_timeout_s", 300)),
                flush_interval_ms=int(self.config.get("flush_interval_ms", 250)),
                enable_thinking_summary=bool(self.config.get("enable_thinking_summary", False)),
                temperature=0.1,
            ):
                ev_name = str(event.get("event") or "")
                ev_data = event.get("data") or {}
                if ev_name == "meta":
                    # Internal streaming meta/keepalive; not part of external API contract here.
                    continue
                if ev_name == "final_delta":
                    streamed_any_delta = True
                    text = str(ev_data.get("text") or "")
                    if text:
                        self.runs_repo.add_event(run_id, "final_delta", {"text": text})
                    yield event
                elif ev_name == "thinking_delta":
                    self.runs_repo.add_event(run_id, "thinking_delta", {"text": str(ev_data.get("text") or "")})
                    yield event
                elif ev_name == "error":
                    self.runs_repo.add_event(run_id, "error", dict(ev_data))
                    yield event
                elif ev_name == "done":
                    final_text = str(ev_data.get("text") or "")
                    continue
        except Exception as exc:
            self.runs_repo.add_event(run_id, "error", {"message": str(exc)})
            yield protocol.error("stream_query_failed", detail=str(exc))

        if not final_text:
            final_text = _build_answer_with_llm(query, focused_sources, self.config) or _build_focused_fallback_answer(
                query, focused_sources
            )
            if not streamed_any_delta:
                self.runs_repo.add_event(run_id, "final_delta", {"text": final_text})
                yield protocol.final_delta(final_text)

        rendered = render_citation_output(
            final_text,
            focused_sources,
            mode="inline",
            max_sources=max_sources,
            max_snippet_chars=max_snippet_chars,
        )
        final_answer = _normalize_final_answer(rendered.get("answer", final_text), focused_sources)
        citation_stats = rendered.get("stats", {})

        citation_stats_event = protocol.citation_stats(citation_stats)
        done_event = protocol.done(cancelled=False, text=final_answer)
        self.runs_repo.add_event(run_id, "sources", {"sources": focused_sources})
        self.runs_repo.add_event(run_id, "citation_stats", {"stats": citation_stats})
        self.runs_repo.add_event(run_id, "done", {"cancelled": False, "text": final_answer})
        yield protocol.sources(focused_sources)
        yield citation_stats_event
        yield done_event

        self.runs_repo.update_result(
            run_id=run_id,
            status="done",
            answer=final_answer,
            citations=focused_sources,
            timings={"result_count": len(results)},
        )

    def retrieve(
        self,
        *,
        query: str,
        top_k: int = 6,
        rerank: bool = True,
        filters: dict[str, Any] | None = None,
        namespaces: list[str] | None = None,
    ) -> dict[str, Any]:
        results = retrieval.scored_chunks(
            query=query,
            top_k=int(top_k),
            rerank=bool(rerank),
            filters=filters,
            namespaces=namespaces,
        )
        candidates = [self._normalize_candidate(row, idx) for idx, row in enumerate(results)]
        return {
            "query": query,
            "count": len(candidates),
            "candidates": candidates,
        }

    def rerank_candidates(
        self,
        *,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int | None = None,
        weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        prepared = []
        for idx, row in enumerate(candidates):
            candidate = dict(row)
            candidate.setdefault("id", self._stable_candidate_id(candidate, idx))
            candidate.setdefault("chunk_id", candidate.get("id"))
            candidate.setdefault("text", str(candidate.get("text") or ""))
            candidate.setdefault("dense_score", float(candidate.get("dense_score") or 0.0))
            candidate.setdefault("bm25_score", float(candidate.get("bm25_score") or 0.0))
            prepared.append(candidate)
        ranked = heuristic_reranker.rerank(prepared, query, weights=weights, top_k=top_k)
        normalized = [self._normalize_candidate(row, idx) for idx, row in enumerate(ranked)]
        return {
            "query": query,
            "count": len(normalized),
            "candidates": normalized,
        }

    @staticmethod
    def _stable_candidate_id(row: dict[str, Any], index: int) -> str:
        raw = "|".join(
            [
                str(row.get("id") or ""),
                str(row.get("chunk_id") or ""),
                str(row.get("doc_id") or ""),
                str(row.get("source_path") or ""),
                str(index),
            ]
        )
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return f"cand_{digest}"

    def _normalize_candidate(self, row: dict[str, Any], index: int) -> dict[str, Any]:
        candidate_id = str(row.get("id") or self._stable_candidate_id(row, index))
        return {
            "candidate_id": candidate_id,
            "chunk_id": row.get("chunk_id"),
            "doc_id": row.get("doc_id"),
            "text": row.get("text"),
            "scores": {
                "rrf": float(row.get("score") or 0.0),
                "dense": float(row.get("dense_score") or 0.0),
                "bm25": float(row.get("bm25_score") or 0.0),
                "rerank": float(row.get("rerank_score") or 0.0),
            },
            "rerank_rank": row.get("rerank_rank"),
            "namespace": row.get("namespace"),
            "source": row.get("source"),
        }
