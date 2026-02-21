from __future__ import annotations

import uuid
from typing import Any

from app.chat.citation_formatter import render_citation_output
from app.repositories.sqlite.runs_repo import RunsRepository
from app.retrieval import hybrid_search as retrieval


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
        answer = _build_retrieval_answer(sources)
        rendered = render_citation_output(
            answer,
            sources,
            mode="inline",
            max_sources=max_sources,
            max_snippet_chars=max_snippet_chars,
        )

        final_answer = rendered.get("answer", answer)
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
            citations=sources,
            timings={"result_count": len(results)},
        )

        return {
            "run_id": run_id,
            "trace_id": trace_id,
            "answer": final_answer,
            "sources": sources,
            "citation_stats": citation_stats,
            "count": len(results),
            "results": results,
        }
