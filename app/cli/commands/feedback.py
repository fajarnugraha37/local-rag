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


def build_feedback_cli() -> typer.Typer:
    app = typer.Typer(name="feedback", no_args_is_help=True, help="Feedback operations.")

    @app.command("add")
    def add_feedback(
        ctx: typer.Context,
        run_id: str = typer.Option("", "--run-id"),
        thumb: str = typer.Option("", "--thumb", help="up|down"),
        note: str = typer.Option("", "--note"),
        citation_id: str = typer.Option("", "--citation-id"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        thumb_value = thumb.strip().lower() or None
        if thumb_value is not None and thumb_value not in {"up", "down"}:
            raise typer.BadParameter("--thumb must be one of: up, down")
        svc = build_services().feedback_service
        record = svc.add_feedback(
            run_id=run_id.strip() or None,
            thumb=thumb_value,
            note=note if note != "" else None,
            citation_id=citation_id.strip() or None,
        )
        emit_json = bool(as_json or ((ctx.obj or {}).get("json") is True))
        _print_payload({"ok": True, "record": record}, as_json=emit_json)

    @app.command("export")
    def export_feedback(
        ctx: typer.Context,
        run_id: str = typer.Option(..., "--run-id"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().feedback_service
        rows = svc.export_feedback(run_id=run_id)
        payload = {"ok": True, "records": rows, "count": len(rows)}
        emit_json = bool(as_json or ((ctx.obj or {}).get("json") is True))
        _print_payload(payload, as_json=emit_json)

    return app


__all__ = ["build_feedback_cli"]

