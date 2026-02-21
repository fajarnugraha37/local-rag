from __future__ import annotations

import json
from typing import Any

import typer

from app.cli.adapters.service_container import build_services
from app.common.namespaces import parse_namespaces


def _print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(str(payload))


def _short_text(value: str, max_chars: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def _render_query_sections(result: dict[str, Any]) -> None:
    run_id = result.get("run_id")
    trace_id = result.get("trace_id")
    user_query = result.get("query") or ""
    typer.echo("=" * 72)
    typer.echo("Query Result")
    typer.echo(f"run_id={run_id} trace_id={trace_id}")
    if user_query:
        typer.echo(f"question={user_query}")
    typer.echo("-" * 72)

    typer.echo("Retrieved Documents")
    rows = result.get("results") or []
    if not rows:
        typer.echo("(none)")
    else:
        for row in rows:
            source = row.get("source") or {}
            idx = source.get("citation_index")
            title = source.get("title") or row.get("doc_id") or "Untitled"
            snippet = _short_text(source.get("snippet") or row.get("text") or "")
            typer.echo(f"- [{idx}] {title}")
            if snippet:
                typer.echo(f"  {snippet}")
    typer.echo("-" * 72)

    typer.echo("AI Answer")
    answer = str(result.get("answer") or "").strip()
    if answer:
        typer.echo(answer)
    else:
        typer.echo("(empty)")
    typer.echo("-" * 72)

    typer.echo("Sources")
    sources = result.get("sources") or []
    if not sources:
        typer.echo("(none)")
    else:
        for src in sources:
            idx = src.get("citation_index")
            title = src.get("title") or src.get("doc_id") or "Untitled"
            path = src.get("path") or ""
            typer.echo(f"- [{idx}] {title}")
            if path:
                typer.echo(f"  path: {path}")
    typer.echo("=" * 72)
    typer.echo("")


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
        _render_query_sections(result)

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
        stream = svc.stream_query(
            query=text,
            top_k=top_k,
            rerank=rerank,
            filters=None,
            namespaces=parse_namespaces([namespaces]) if namespaces else None,
        )
        emit_json = bool(as_json or ((ctx.obj or {}).get("json") is True))
        if emit_json:
            events = list(stream)
            _print_payload({"ok": True, "events": events, "count": len(events)}, as_json=True)
            return
        for event in stream:
            name = str(event.get("event") or "")
            data = event.get("data") or {}
            if name == "final_delta":
                typer.echo(str(data.get("text") or ""), nl=False)
            elif name == "meta":
                typer.echo(f"\n[meta] run_id={data.get('run_id')} trace_id={data.get('trace_id')}")
            elif name == "sources":
                typer.echo("\n\n[sources]")
                for src in data.get("sources") or []:
                    idx = src.get("citation_index")
                    title = src.get("title") or src.get("doc_id") or "Untitled"
                    typer.echo(f"- [{idx}] {title}")
            elif name == "citation_stats":
                typer.echo(f"\n[citation_stats] {data.get('stats')}")
            elif name == "done":
                typer.echo("\n\n[done]")
                typer.echo(str(data.get("text") or ""))
            elif name == "error":
                typer.echo(f"\n[error] {data}")


__all__ = ["register_query_commands"]
