from __future__ import annotations

import json
from typing import Any

import typer

from app.cli.adapters.service_container import build_services
from app.cli.render.events import render_events
from app.common.namespaces import parse_namespaces


def _print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(str(payload))


def register_query_commands(app: typer.Typer) -> None:
    @app.command("query")
    def query_command(
        ctx: typer.Context,
        text: str = typer.Argument(..., help="Query text."),
        top_k: int = typer.Option(6, "--top-k", min=1, max=100),
        rerank: bool = typer.Option(True, "--rerank/--no-rerank"),
        namespaces: str = typer.Option("", "--namespaces", help="Comma-separated namespaces."),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().query_service
        result = svc.run_query(
            query=text,
            top_k=top_k,
            rerank=rerank,
            filters=None,
            namespaces=parse_namespaces([namespaces]) if namespaces else None,
            mode="non_stream",
        )
        payload = {"ok": True, **result}
        emit_json = bool(as_json or ((ctx.obj or {}).get("json") is True))
        if emit_json:
            _print_payload(payload, as_json=True)
            return
        typer.echo(f"run_id={result.get('run_id')} trace_id={result.get('trace_id')}")
        typer.echo(result.get("answer") or "")
        sources = result.get("sources") or []
        if sources:
            typer.echo("sources:")
            for src in sources:
                idx = src.get("citation_index")
                title = src.get("title") or src.get("doc_id") or "Untitled"
                typer.echo(f"- [{idx}] {title}")

    @app.command("query-stream")
    def query_stream_command(
        ctx: typer.Context,
        text: str = typer.Argument(..., help="Query text."),
        top_k: int = typer.Option(6, "--top-k", min=1, max=100),
        rerank: bool = typer.Option(True, "--rerank/--no-rerank"),
        namespaces: str = typer.Option("", "--namespaces", help="Comma-separated namespaces."),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().query_service
        result = svc.run_query(
            query=text,
            top_k=top_k,
            rerank=rerank,
            filters=None,
            namespaces=parse_namespaces([namespaces]) if namespaces else None,
            mode="stream",
        )
        events = [
            {
                "ts": "",
                "event": "meta",
                "payload": {"run_id": result["run_id"], "trace_id": result["trace_id"]},
            },
            {"ts": "", "event": "final_delta", "payload": {"text": result["answer"]}},
            {"ts": "", "event": "sources", "payload": {"sources": result["sources"]}},
            {"ts": "", "event": "citation_stats", "payload": {"stats": result["citation_stats"]}},
            {"ts": "", "event": "done", "payload": {"cancelled": False, "text": result["answer"]}},
        ]
        emit_json = bool(as_json or ((ctx.obj or {}).get("json") is True))
        if emit_json:
            _print_payload({"ok": True, "events": events, "count": len(events)}, as_json=True)
            return
        typer.echo(render_events(events))


__all__ = ["register_query_commands"]

