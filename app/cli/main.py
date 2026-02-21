from __future__ import annotations

import json
from typing import Any, List, Optional, Sequence

import typer
from click.exceptions import ClickException

from app.cli.commands.documents import build_documents_cli
from app.cli.commands.feedback import build_feedback_cli
from app.cli.commands.ingestions import build_ingestions_cli
from app.cli.commands.namespaces import build_namespaces_cli
from app.cli.commands.query import register_query_commands
from app.cli.commands.retrieve import register_retrieval_commands
from app.cli.commands.runs import build_runs_cli
from app.cli.commands.system import build_system_cli
from app.cli.shell import register_shell_command
from cmd.actions import format_actions_table, list_actions, run_action

app = typer.Typer(
    name="rag",
    no_args_is_help=True,
    add_completion=False,
    help="Direct-to-app CLI for local RAG workflows.",
)

_SYSTEM_COMMANDS, _CONFIG_APP = build_system_cli()
_NAMESPACES_APP = build_namespaces_cli()
_DOCUMENTS_APP = build_documents_cli()
_FEEDBACK_APP = build_feedback_cli()
_INGESTIONS_APP = build_ingestions_cli()
_RUNS_APP = build_runs_cli()
app.add_typer(_CONFIG_APP, name="config")
app.add_typer(_NAMESPACES_APP, name="ns")
app.add_typer(_DOCUMENTS_APP, name="doc")
app.add_typer(_FEEDBACK_APP, name="feedback")
app.add_typer(_INGESTIONS_APP, name="ingest")
app.add_typer(_RUNS_APP, name="run")
register_query_commands(app)
register_retrieval_commands(app)
register_shell_command(app)


def _build_context(json_output: bool, verbose: bool) -> dict[str, Any]:
    return {
        "json": json_output,
        "verbose": verbose,
    }


@app.callback()
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output when supported."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose diagnostics."),
) -> None:
    """Root command with shared global options."""
    ctx.obj = _build_context(json_output=json_output, verbose=verbose)


@app.command(
    "actions",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def actions_command(
    ctx: typer.Context,
    action: Optional[str] = typer.Argument(None, help="Legacy action name."),
) -> None:
    """Run legacy action-dispatch commands."""
    if not action:
        typer.echo(format_actions_table())
        return

    extra_args = list(ctx.args)
    code = run_action(action, extra_args)
    raise typer.Exit(code=code)


@app.command("actions-list")
def actions_list_command() -> None:
    """List legacy actions."""
    for spec in list_actions():
        typer.echo(f"{spec.name}\t{spec.description}")


@app.command("health")
def health_command(ctx: typer.Context) -> None:
    payload = _SYSTEM_COMMANDS["health"]()
    if bool((ctx.obj or {}).get("json")):
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(str(payload))


@app.command("healthz")
def healthz_command(ctx: typer.Context) -> None:
    payload = _SYSTEM_COMMANDS["healthz"]()
    if bool((ctx.obj or {}).get("json")):
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(str(payload))


@app.command("readyz")
def readyz_command(ctx: typer.Context) -> None:
    payload = _SYSTEM_COMMANDS["readyz"]()
    if bool((ctx.obj or {}).get("json")):
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(str(payload))
    if not bool(payload.get("ok")):
        raise typer.Exit(code=1)


@app.command("version")
def version_command(ctx: typer.Context) -> None:
    payload = _SYSTEM_COMMANDS["version"]()
    if bool((ctx.obj or {}).get("json")):
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(f"{payload.get('version')} ({payload.get('api')})")


@app.command("capabilities")
def capabilities_command(ctx: typer.Context) -> None:
    payload = _SYSTEM_COMMANDS["capabilities"]()
    if bool((ctx.obj or {}).get("json")):
        typer.echo(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return
    typer.echo(str(payload))


def run(argv: Sequence[str]) -> int:
    try:
        app(
            args=list(argv),
            standalone_mode=False,
            prog_name="python .\\cmd\\app.py --cli",
        )
        return 0
    except typer.Exit as exc:
        return int(exc.exit_code)
    except ClickException as exc:
        exc.show()
        return 2


__all__: List[str] = ["app", "run"]
