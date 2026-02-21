"""CLI mode dispatcher for centralized launcher."""

from __future__ import annotations

import sys
from typing import List, Sequence

if __package__ in {None, "", "cli"}:
    from actions import format_actions_table, run_action
else:
    from ..actions import format_actions_table, run_action


def _print_cli_help() -> None:
    print("Usage:")
    print("  python .\\cmd\\app.py --cli <action> [action args]")
    print()
    print(format_actions_table())
    print()
    print("Examples:")
    print("  python .\\cmd\\app.py --cli chat --top-k 6 --stream")
    print('  python .\\cmd\\app.py --cli query --query "payment terms" --top-k 6')
    print(
        '  python .\\cmd\\app.py --cli ingest-email --keyword "invoice" --startdate 01.01.2025 --enddate 31.01.2025'
    )


def run_cli(argv: Sequence[str]) -> int:
    args = list(argv)
    if not args or args[0] in {"-h", "--help"}:
        _print_cli_help()
        return 0

    action = args[0]
    action_args: List[str] = args[1:]
    return run_action(action, action_args)


if __name__ == "__main__":
    raise SystemExit(run_cli(sys.argv[1:]))
