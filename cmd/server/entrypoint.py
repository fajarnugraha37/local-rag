"""Server mode dispatcher for centralized launcher."""

from __future__ import annotations

import sys
from typing import Sequence

if __package__ in {None, "", "server"}:
    from actions import run_action
else:
    from ..actions import run_action


def run_server(argv: Sequence[str]) -> int:
    return run_action("server", argv)


if __name__ == "__main__":
    raise SystemExit(run_server(sys.argv[1:]))
