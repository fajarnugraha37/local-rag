from __future__ import annotations

import json
from typing import Any

import typer

from app.common.namespaces import validate_namespace
from app.services.namespace_service import NamespaceService

from app.cli.adapters.service_container import build_services
from app.cli.render.tables import render_table


def _want_json(ctx: typer.Context, as_json: bool = False) -> bool:
    return bool(as_json or ((ctx.obj or {}).get("json") is True))


def build_namespaces_cli() -> typer.Typer:
    app = typer.Typer(name="ns", no_args_is_help=True, help="Namespace operations.")

    @app.command("list")
    def list_namespaces(
        ctx: typer.Context,
        include_deleted: bool = typer.Option(False, "--include-deleted"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().namespace_service
        records = svc.list_namespaces(include_deleted=include_deleted)
        payload = {"ok": True, "records": records, "count": len(records)}
        if _want_json(ctx, as_json):
            typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            return
        table_rows = [
            {
                "namespace": r.get("namespace", ""),
                "deleted_at": r.get("deleted_at", "") or "",
                "created_at": r.get("created_at", "") or "",
            }
            for r in records
        ]
        typer.echo(render_table(table_rows, [("namespace", "namespace"), ("deleted_at", "deleted_at"), ("created_at", "created_at")]))

    @app.command("create")
    def create_namespace(
        ctx: typer.Context,
        name: str = typer.Argument(..., help="Namespace name."),
        defaults_json: str = typer.Option("{}", "--defaults-json"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        namespace = validate_namespace(name, default_to_default=False)
        defaults: dict[str, Any] = {}
        try:
            parsed = json.loads(defaults_json)
            if isinstance(parsed, dict):
                defaults = parsed
        except Exception:
            raise typer.BadParameter("defaults-json must be a JSON object.")
        svc = build_services().namespace_service
        record = svc.create_namespace(namespace, defaults=defaults)
        payload = {"ok": True, "record": record}
        if _want_json(ctx, as_json):
            typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            return
        typer.echo(f"namespace={record.get('namespace')} created")

    @app.command("delete")
    def delete_namespace(
        ctx: typer.Context,
        name: str = typer.Argument(..., help="Namespace name."),
        dry_run: bool = typer.Option(False, "--dry-run"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        namespace = validate_namespace(name, default_to_default=False)
        svc = build_services().namespace_service
        payload = {"ok": True, **svc.delete_namespace(namespace, dry_run=dry_run)}
        if _want_json(ctx, as_json):
            typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            return
        typer.echo(str(payload))

    return app


__all__ = ["build_namespaces_cli"]

