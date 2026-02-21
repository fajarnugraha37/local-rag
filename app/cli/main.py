from __future__ import annotations

from typing import Any, List, Optional, Sequence

import typer
from click.exceptions import ClickException

from cmd.actions import format_actions_table, list_actions, run_action

app = typer.Typer(
    name="rag",
    no_args_is_help=True,
    add_completion=False,
    help="Direct-to-app CLI for local RAG workflows.",
)


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
