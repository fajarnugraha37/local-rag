from __future__ import annotations

import typer

from app.cli.interactive import parse_command_line, run_cli_subcommand

_MENU = """\
Interactive Shell
1. Query
2. Namespaces List
3. Documents List
4. Ingestion Status
5. Run Show
6. Config Get
7. Run Any CLI Subcommand
0. Exit
"""


def _prompt(prompt: str) -> str:
    return input(prompt).strip()


def register_shell_command(app: typer.Typer) -> None:
    @app.command("shell")
    def shell_command() -> None:
        """Start interactive CLI shell."""
        typer.echo("Starting interactive shell. Enter 0 to exit.")
        while True:
            typer.echo(_MENU)
            choice = _prompt("Select menu: ")
            if choice == "0":
                typer.echo("Shell closed.")
                return
            if choice == "1":
                q = _prompt("Query text: ")
                if not q:
                    typer.echo("Query text is required.")
                    continue
                run_cli_subcommand(["query", q])
                continue
            if choice == "2":
                run_cli_subcommand(["ns", "list"])
                continue
            if choice == "3":
                run_cli_subcommand(["doc", "list", "--limit", "10"])
                continue
            if choice == "4":
                ingestion_id = _prompt("Ingestion ID: ")
                if not ingestion_id:
                    typer.echo("Ingestion ID is required.")
                    continue
                run_cli_subcommand(["ingest", "status", ingestion_id])
                continue
            if choice == "5":
                run_id = _prompt("Run ID: ")
                if not run_id:
                    typer.echo("Run ID is required.")
                    continue
                run_cli_subcommand(["run", "show", run_id])
                continue
            if choice == "6":
                run_cli_subcommand(["config", "get"])
                continue
            if choice == "7":
                raw = _prompt("CLI args (without --cli): ")
                args = parse_command_line(raw)
                if not args:
                    typer.echo("No command entered.")
                    continue
                run_cli_subcommand(args)
                continue
            typer.echo("Unknown choice. Use 0-7.")


__all__ = ["register_shell_command"]

