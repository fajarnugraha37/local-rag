"""CLI mode dispatcher for centralized launcher."""

from __future__ import annotations

import sys
from typing import Sequence

if __package__ in {None, "", "cli"}:
    from app.cli.main import run
else:
    from app.cli.main import run


def run_cli(argv: Sequence[str]) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(run_cli(sys.argv[1:]))
