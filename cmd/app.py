"""Single supported entrypoint for server and CLI workflows."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence


if __package__:
    from .cli.entrypoint import run_cli
    from .server.entrypoint import run_server
else:
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    REPO_ROOT = os.path.dirname(THIS_DIR)
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    from cmd.cli.entrypoint import run_cli
    from cmd.server.entrypoint import run_server


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python .\\cmd\\app.py",
        add_help=False,
        description="Centralized launcher for all server and CLI actions.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--server", action="store_true", help="Run HTTP/SSE server mode.")
    mode.add_argument("--cli", action="store_true", help="Run CLI action mode.")
    parser.add_argument("-h", "--help", action="store_true", help="Show launcher help.")
    return parser


def _print_help(parser: argparse.ArgumentParser) -> None:
    parser.print_help()
    print()
    print("Mode examples:")
    print("  python .\\cmd\\app.py --server --host 127.0.0.1 --port 8000")
    print("  python .\\cmd\\app.py --cli chat --model llama3 --top-k 6")
    print("  python .\\cmd\\app.py --cli --help")
    print("  python .\\cmd\\app.py --server --help")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    raw_args = list(argv if argv is not None else sys.argv[1:])
    args, passthrough = parser.parse_known_args(raw_args)

    if args.help and not args.server and not args.cli:
        _print_help(parser)
        return 0
    if args.server == args.cli:
        parser.error("Choose exactly one mode: --server or --cli.")
    if args.help:
        if passthrough:
            passthrough = [*passthrough, "--help"]
        else:
            passthrough = ["--help"]

    if args.server:
        return run_server(passthrough)
    return run_cli(passthrough)


if __name__ == "__main__":
    raise SystemExit(main())
