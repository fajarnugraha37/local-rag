from __future__ import annotations

import json
from typing import Any

import typer

from app.config import runtime_settings as settings
from app.health.checks import run_readiness_checks

_PATCHABLE_CONFIG_KEYS = {
    "top_k",
    "ollama_model",
    "enable_streaming",
    "enable_thinking_summary",
    "provider_timeout_s",
    "flush_interval_ms",
    "citations",
    "citations_mode",
    "citation_max_sources",
    "citation_max_snippet_chars",
    "general_knowledge_fallback",
    "general_knowledge_min_sources",
    "general_knowledge_min_term_hits",
    "general_knowledge_min_answer_chars",
    "general_knowledge_max_sentences",
}


def _want_json(ctx: typer.Context, local_json: bool = False) -> bool:
    return bool(local_json or ((ctx.obj or {}).get("json") is True))


def _print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(str(payload))


def _version_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "version": "0.1.0",
        "api": "fastapi",
    }


def _capabilities_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "capabilities": {
            "streaming": True,
            "citations": True,
            "namespaces": True,
            "docling_ingestion": bool(settings.CONFIG.get("ingest_docling_enabled", True)),
            "legacy_endpoints": True,
        },
    }


def _parse_value(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    try:
        return json.loads(value)
    except Exception:
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == "null":
            return None
        return raw


def build_system_cli() -> tuple[dict[str, Any], typer.Typer]:
    config_app = typer.Typer(
        name="config",
        no_args_is_help=True,
        help="Read and patch runtime config values.",
    )

    @config_app.command("get")
    def config_get(
        ctx: typer.Context,
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        """Get current runtime config snapshot."""
        payload = {"ok": True, "config": dict(settings.CONFIG)}
        _print_payload(payload, as_json=_want_json(ctx, as_json))

    @config_app.command("set")
    def config_set(
        ctx: typer.Context,
        key: str = typer.Option(..., "--key", help="Patchable config key."),
        value: str = typer.Option(..., "--value", help="Value (JSON literal or string)."),
        as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
    ) -> None:
        """Patch one runtime config key."""
        updates = {key: _parse_value(value)}
        applied: dict[str, Any] = {}
        rejected: dict[str, Any] = {}
        for update_key, update_value in updates.items():
            if update_key not in _PATCHABLE_CONFIG_KEYS:
                rejected[update_key] = "key is not patchable"
                continue
            settings.CONFIG[update_key] = update_value
            applied[update_key] = update_value

        snapshot = dict(settings.CONFIG)
        snapshot["_applied"] = applied
        snapshot["_rejected"] = rejected
        payload = {"ok": True, "config": snapshot}
        _print_payload(payload, as_json=_want_json(ctx, as_json))
        if rejected:
            raise typer.Exit(code=2)

    commands = {
        "health": lambda: {"ok": True},
        "healthz": lambda: {"ok": True},
        "readyz": lambda: run_readiness_checks(settings.CONFIG),
        "version": _version_payload,
        "capabilities": _capabilities_payload,
    }
    return commands, config_app


__all__ = ["build_system_cli"]
