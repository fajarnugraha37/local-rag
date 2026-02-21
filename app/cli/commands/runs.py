from __future__ import annotations

import json
import time
from typing import Any

import typer

from app.cli.adapters.service_container import build_services
from app.cli.render.events import render_events


def _want_json(ctx: typer.Context, as_json: bool = False) -> bool:
    return bool(as_json or ((ctx.obj or {}).get("json") is True))


def _print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(str(payload))


def build_runs_cli() -> typer.Typer:
    app = typer.Typer(name="run", no_args_is_help=True, help="Inspect run records, steps, and events.")

    @app.command("show")
    def show_run(
        ctx: typer.Context,
        run_id: str = typer.Argument(...),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().run_service
        record = svc.get_run(run_id)
        if record is None:
            _print_payload({"ok": False, "error": "not_found"}, as_json=_want_json(ctx, as_json))
            raise typer.Exit(code=1)
        _print_payload({"ok": True, "record": record}, as_json=_want_json(ctx, as_json))

    @app.command("steps")
    def run_steps(
        ctx: typer.Context,
        run_id: str = typer.Argument(...),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().run_service
        steps = svc.get_steps(run_id)
        _print_payload({"ok": True, "steps": steps, "count": len(steps)}, as_json=_want_json(ctx, as_json))

    @app.command("events")
    def run_events(
        ctx: typer.Context,
        run_id: str = typer.Argument(...),
        limit: int = typer.Option(1000, "--limit", min=1, max=5000),
        follow: bool = typer.Option(False, "--follow"),
        poll_interval: float = typer.Option(1.0, "--poll-interval"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().run_service
        last_count = 0
        while True:
            events = svc.get_events(run_id, limit=limit)
            if _want_json(ctx, as_json):
                _print_payload({"ok": True, "events": events, "count": len(events)}, as_json=True)
            else:
                if len(events) > last_count:
                    typer.echo(render_events(events[last_count:]))
                    last_count = len(events)
                elif not follow:
                    typer.echo("(no events)")
            if not follow:
                break
            run_record = svc.get_run(run_id)
            if run_record and str(run_record.get("status") or "") in {"done", "failed", "cancelled"}:
                break
            time.sleep(max(0.2, float(poll_interval)))

    @app.command("replay")
    def run_replay(
        ctx: typer.Context,
        run_id: str = typer.Argument(...),
        limit: int = typer.Option(1000, "--limit", min=1, max=5000),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().run_service
        events = svc.get_events(run_id, limit=limit)
        if _want_json(ctx, as_json):
            _print_payload({"ok": True, "events": events, "count": len(events)}, as_json=True)
            return
        typer.echo(render_events(events))

    return app


__all__ = ["build_runs_cli"]

