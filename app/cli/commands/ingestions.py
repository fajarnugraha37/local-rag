from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import typer

from app.cli.adapters.service_container import build_services
from app.cli.idempotency import (
    build_idempotency_key,
    build_signature,
    execute_with_idempotency,
)
from app.cli.render.events import render_events
from app.common.namespaces import validate_namespace
from app.services.ingestion_service import UploadPayload


def _want_json(ctx: typer.Context, as_json: bool = False) -> bool:
    return bool(as_json or ((ctx.obj or {}).get("json") is True))


def _print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(str(payload))


def _render_wait_progress(*, elapsed_s: float, record: dict[str, Any] | None, tick: int) -> None:
    spinner = ["|", "/", "-", "\\"]
    mark = spinner[tick % len(spinner)]
    status = str((record or {}).get("status") or "queued")
    counters = (record or {}).get("counters") or {}
    ingested = int(counters.get("ingested") or 0)
    skipped = int(counters.get("skipped") or 0)
    failed = int(counters.get("failed") or 0)
    line = (
        f"\r{mark} waiting... status={status} "
        f"ingested={ingested} skipped={skipped} failed={failed} "
        f"elapsed={int(elapsed_s)}s"
    )
    sys.stdout.write(line)
    sys.stdout.flush()


def build_ingestions_cli() -> typer.Typer:
    app = typer.Typer(name="ingest", no_args_is_help=True, help="Ingestion jobs and logs.")

    @app.command("start")
    def start_ingestion(
        ctx: typer.Context,
        namespace: str = typer.Option("default", "--namespace"),
        source: str = typer.Option(..., "--source", help="folder|repo|files"),
        path: str = typer.Option("", "--path", help="Folder path for source=folder."),
        repo: str = typer.Option("", "--repo", help="Repository URL for source=repo."),
        revision: str = typer.Option("", "--revision", help="Optional git revision."),
        paths: str = typer.Option("", "--paths", help="Comma-separated file paths for source=files."),
        embedding_model: str = typer.Option("", "--embedding-model"),
        dry_run: bool = typer.Option(False, "--dry-run"),
        force: bool = typer.Option(False, "--force"),
        include: str = typer.Option("", "--include", help="Comma-separated include globs."),
        exclude: str = typer.Option("", "--exclude", help="Comma-separated exclude globs."),
        idempotency_key: str = typer.Option("", "--idempotency-key"),
        wait: bool = typer.Option(False, "--wait/--no-wait", help="Wait until job reaches terminal state."),
        wait_timeout_s: int = typer.Option(300, "--wait-timeout-s", min=1, help="Max seconds to wait when --wait is enabled."),
        wait_poll_interval: float = typer.Option(1.0, "--wait-poll-interval", min=0.2, help="Polling interval in seconds while waiting."),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        services = build_services()
        svc = services.ingestion_service
        repo_id = services.idempotency_repo
        ns = validate_namespace(namespace, default_to_default=True)
        source_type = source.strip().lower()

        if source_type not in {"folder", "repo", "files"}:
            raise typer.BadParameter("--source must be one of: folder, repo, files")

        include_patterns = [s.strip() for s in include.split(",") if s.strip()]
        exclude_patterns = [s.strip() for s in exclude.split(",") if s.strip()]
        payload_signature_data: dict[str, Any] = {
            "namespace": ns,
            "source": source_type,
            "path": path,
            "repo": repo,
            "revision": revision,
            "paths": paths,
            "embedding_model": embedding_model,
            "dry_run": dry_run,
            "force": force,
            "include": include_patterns,
            "exclude": exclude_patterns,
        }
        signature = build_signature(payload_signature_data)
        auto_key = build_idempotency_key(
            operation=f"ingest-{source_type}",
            payload=payload_signature_data,
        )
        effective_key = idempotency_key or auto_key

        def _create_response() -> dict[str, Any]:
            if source_type == "folder":
                if not path.strip():
                    raise typer.BadParameter("--path is required when --source folder")
                record = svc.create_job(
                    namespace=ns,
                    source_type="folder",
                    source_spec={
                        "path": path,
                        "recursive": True,
                        "include": include_patterns,
                        "exclude": exclude_patterns,
                        "dry_run": bool(dry_run),
                        "force": bool(force),
                        "embedding_model": embedding_model or None,
                    },
                )
            elif source_type == "repo":
                if not repo.strip():
                    raise typer.BadParameter("--repo is required when --source repo")
                record = svc.create_job(
                    namespace=ns,
                    source_type="repo",
                    source_spec={
                        "repo": repo,
                        "revision": revision or None,
                        "include": include_patterns,
                        "exclude": exclude_patterns,
                        "dry_run": bool(dry_run),
                        "force": bool(force),
                        "embedding_model": embedding_model or None,
                    },
                )
            else:
                file_paths = [s.strip() for s in paths.split(",") if s.strip()]
                if not file_paths:
                    raise typer.BadParameter("--paths is required when --source files")
                uploads: list[tuple[str, bytes]] = []
                for file_path in file_paths:
                    p = Path(file_path)
                    if not p.exists() or not p.is_file():
                        raise typer.BadParameter(f"file does not exist: {file_path}")
                    uploads.append((p.name, p.read_bytes()))
                record = svc.create_job(
                    namespace=ns,
                    source_type="upload",
                    source_spec={"embedding_model": embedding_model or None},
                    upload_payload=UploadPayload(files=uploads, fields={"namespace": ns}),
                )
            return {"ok": True, "ingestion_id": record.get("ingestion_id"), "record": record}

        if idempotency_key:
            response, replayed = execute_with_idempotency(
                repo=repo_id,
                key=effective_key,
                method="POST",
                path="/v1/ingestions",
                signature=signature,
                ttl_seconds=int(services.config.get("idempotency_ttl_s") or 86400),
                fn=_create_response,
            )
        else:
            # Auto-generated key is informational by default; avoid stale replay traps.
            response = _create_response()
            replayed = False
        response["idempotency_key"] = effective_key
        response["idempotency_replayed"] = bool(replayed)

        if wait:
            ingestion_id = str(response.get("ingestion_id") or "")
            if ingestion_id:
                deadline = time.time() + max(1, int(wait_timeout_s))
                terminal_states = {"done", "failed", "cancelled"}
                last_record = None
                started = time.time()
                tick = 0
                show_progress = not _want_json(ctx, as_json)
                while time.time() < deadline:
                    last_record = svc.get_job(ingestion_id)
                    if show_progress:
                        _render_wait_progress(
                            elapsed_s=time.time() - started,
                            record=last_record,
                            tick=tick,
                        )
                        tick += 1
                    if last_record and str(last_record.get("status") or "") in terminal_states:
                        break
                    time.sleep(max(0.2, float(wait_poll_interval)))
                if show_progress:
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                if last_record:
                    response["record"] = last_record
                    response["final_status"] = last_record.get("status")
                else:
                    response["final_status"] = "unknown"
                response["waited"] = True
                response["wait_timeout_s"] = int(wait_timeout_s)
                if str(response.get("final_status") or "") not in {"done", "failed", "cancelled"}:
                    response["wait_timed_out"] = True
        _print_payload(response, as_json=_want_json(ctx, as_json))

    @app.command("status")
    def ingestion_status(
        ctx: typer.Context,
        ingestion_id: str = typer.Argument(...),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().ingestion_service
        record = svc.get_job(ingestion_id)
        if record is None:
            payload = {"ok": False, "error": "not_found"}
            _print_payload(payload, as_json=_want_json(ctx, as_json))
            raise typer.Exit(code=1)
        payload = {"ok": True, "record": record}
        _print_payload(payload, as_json=_want_json(ctx, as_json))

    @app.command("cancel")
    def ingestion_cancel(
        ctx: typer.Context,
        ingestion_id: str = typer.Argument(...),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().ingestion_service
        cancel_requested = svc.cancel_job(ingestion_id)
        payload = {
            "ok": True,
            "ingestion_id": ingestion_id,
            "cancel_requested": bool(cancel_requested),
        }
        _print_payload(payload, as_json=_want_json(ctx, as_json))

    @app.command("logs")
    def ingestion_logs(
        ctx: typer.Context,
        ingestion_id: str = typer.Argument(...),
        limit: int = typer.Option(500, "--limit", min=1, max=5000),
        follow: bool = typer.Option(False, "--follow"),
        poll_interval: float = typer.Option(1.0, "--poll-interval"),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        svc = build_services().ingestion_service
        last_count = 0
        terminal_states = {"done", "failed", "cancelled"}
        while True:
            events = svc.list_events(ingestion_id, limit=limit)
            if _want_json(ctx, as_json):
                payload = {"ok": True, "events": events, "count": len(events)}
                typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            else:
                if len(events) > last_count:
                    typer.echo(render_events(events[last_count:]))
                    last_count = len(events)
                elif not follow:
                    typer.echo("(no events)")

            if not follow:
                break

            record = svc.get_job(ingestion_id)
            if record and str(record.get("status") or "") in terminal_states:
                break
            time.sleep(max(0.2, float(poll_interval)))

    return app


__all__ = ["build_ingestions_cli"]
