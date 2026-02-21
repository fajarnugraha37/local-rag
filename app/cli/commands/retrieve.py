from __future__ import annotations

import json
from typing import Any

import typer

from app.cli.adapters.service_container import build_services


def _print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(str(payload))


def register_retrieval_commands(app: typer.Typer) -> None:
    @app.command("retrieve")
    def retrieve_command(
        ctx: typer.Context,
        text: str = typer.Argument(..., help="Query text."),
        top_k: int = typer.Option(6, "--top-k", min=1, max=100),
        rerank: bool = typer.Option(True, "--rerank/--no-rerank"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().query_service
        result = svc.retrieve(
            query=text,
            top_k=top_k,
            rerank=rerank,
            filters=None,
            namespaces=None,
        )
        emit_json = bool(as_json or ((ctx.obj or {}).get("json") is True))
        _print_payload({"ok": True, **result}, as_json=emit_json)

    @app.command("rerank")
    def rerank_command(
        ctx: typer.Context,
        query: str = typer.Option(..., "--query"),
        candidates_json: str = typer.Option(..., "--candidates"),
        top_k: int | None = typer.Option(None, "--top-k"),
        weights_json: str = typer.Option("", "--weights"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        try:
            candidates_raw = json.loads(candidates_json)
        except Exception as exc:
            raise typer.BadParameter(f"invalid --candidates JSON: {exc}")
        if not isinstance(candidates_raw, list):
            raise typer.BadParameter("--candidates must be a JSON array")
        weights: dict[str, float] | None = None
        if weights_json.strip():
            try:
                parsed = json.loads(weights_json)
            except Exception as exc:
                raise typer.BadParameter(f"invalid --weights JSON: {exc}")
            if not isinstance(parsed, dict):
                raise typer.BadParameter("--weights must be a JSON object")
            weights = {str(k): float(v) for k, v in parsed.items()}

        svc = build_services().query_service
        result = svc.rerank_candidates(
            query=query,
            candidates=[dict(item) for item in candidates_raw],
            top_k=top_k,
            weights=weights,
        )
        emit_json = bool(as_json or ((ctx.obj or {}).get("json") is True))
        _print_payload({"ok": True, **result}, as_json=emit_json)


__all__ = ["register_retrieval_commands"]

