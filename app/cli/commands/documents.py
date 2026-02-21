from __future__ import annotations

import json

import typer

from app.common.namespaces import validate_namespace
from app.repositories.sqlite.documents_repo import DocumentsRepository

from app.cli.adapters.service_container import build_services
from app.cli.render.tables import render_table


def _want_json(ctx: typer.Context, as_json: bool = False) -> bool:
    return bool(as_json or ((ctx.obj or {}).get("json") is True))


def build_documents_cli() -> typer.Typer:
    app = typer.Typer(name="doc", no_args_is_help=True, help="Document operations.")

    @app.command("list")
    def list_documents(
        ctx: typer.Context,
        namespace: str | None = typer.Option(None, "--namespace"),
        limit: int = typer.Option(50, "--limit", min=1, max=500),
        cursor: str | None = typer.Option(None, "--cursor"),
        include_deleted: bool = typer.Option(False, "--include-deleted"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().document_service
        resolved_namespace = (
            validate_namespace(namespace, default_to_default=True) if namespace is not None else None
        )
        payload = svc.list_documents(
            namespace=resolved_namespace,
            limit=limit,
            cursor=cursor,
            include_deleted=include_deleted,
        )
        out = {"ok": True, **payload}
        if _want_json(ctx, as_json):
            typer.echo(json.dumps(out, ensure_ascii=True, indent=2, sort_keys=True))
            return
        table_rows = [
            {
                "namespace": r.get("namespace", "") or "",
                "doc_id": r.get("doc_id", "") or "",
                "updated_at": r.get("updated_at", "") or "",
                "deleted_at": r.get("deleted_at", "") or "",
            }
            for r in payload.get("records", [])
        ]
        typer.echo(
            render_table(
                table_rows,
                [
                    ("namespace", "namespace"),
                    ("doc_id", "doc_id"),
                    ("updated_at", "updated_at"),
                    ("deleted_at", "deleted_at"),
                ],
            )
        )
        if payload.get("next_cursor"):
            typer.echo(f"next_cursor={payload['next_cursor']}")

    @app.command("show")
    def show_document(
        ctx: typer.Context,
        namespace: str = typer.Argument(..., help="Namespace."),
        doc_id: str = typer.Argument(..., help="Document id."),
        include_deleted: bool = typer.Option(False, "--include-deleted"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().document_service
        resolved = validate_namespace(namespace, default_to_default=False)
        record = svc.get_document(resolved, doc_id, include_deleted=include_deleted)
        payload = {"ok": bool(record), "record": record}
        if _want_json(ctx, as_json):
            typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            raise typer.Exit(code=0 if record else 1)
        typer.echo(str(payload))
        if not record:
            raise typer.Exit(code=1)

    @app.command("delete")
    def delete_document(
        ctx: typer.Context,
        doc_id: str = typer.Argument(..., help="Document id."),
        namespace: str = typer.Option("default", "--namespace"),
        hard_delete: bool = typer.Option(False, "--hard-delete"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().document_service
        resolved = validate_namespace(namespace, default_to_default=False)
        deleted = svc.delete_document(resolved, doc_id, hard_delete=hard_delete)
        payload = {
            "ok": True,
            "namespace": resolved,
            "doc_id": doc_id,
            "deleted": bool(deleted),
            "hard_delete": bool(hard_delete),
        }
        if _want_json(ctx, as_json):
            typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            return
        typer.echo(str(payload))

    @app.command("bulk-delete")
    def bulk_delete_documents(
        ctx: typer.Context,
        namespace: str | None = typer.Option(None, "--namespace"),
        doc_ids: str = typer.Option("", "--doc-ids", help="Comma-separated doc_ids."),
        hard_delete: bool = typer.Option(False, "--hard-delete"),
        limit: int = typer.Option(500, "--limit", min=1, max=2000),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().document_service
        resolved_namespace = (
            validate_namespace(namespace, default_to_default=True) if namespace is not None else None
        )
        ids = [item.strip() for item in doc_ids.split(",") if item.strip()] if doc_ids else None
        payload = {
            "ok": True,
            **svc.bulk_delete(
                namespace=resolved_namespace,
                doc_ids=ids,
                hard_delete=hard_delete,
                limit=limit,
            ),
        }
        if _want_json(ctx, as_json):
            typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            return
        typer.echo(str(payload))

    @app.command("purge")
    def purge_soft_deleted(
        ctx: typer.Context,
        retention_days: int = typer.Option(30, "--retention-days", min=0),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        services = build_services()
        repo = DocumentsRepository(services.db_path)
        count = repo.purge_soft_deleted(retention_days=retention_days)
        payload = {"ok": True, "purged": int(count), "retention_days": int(retention_days)}
        if _want_json(ctx, as_json):
            typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            return
        typer.echo(str(payload))

    return app


__all__ = ["build_documents_cli"]

