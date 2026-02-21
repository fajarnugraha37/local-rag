from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _launcher_path() -> Path:
    return _repo_root() / "cmd" / "app.py"


def parse_command_line(raw: str) -> list[str]:
    text = raw.strip()
    if not text:
        return []
    return shlex.split(text)


def run_cli_subcommand(args: Sequence[str]) -> int:
    launcher = _launcher_path()
    cmd = [sys.executable, str(launcher), "--cli", *list(args)]
    completed = subprocess.run(cmd, cwd=str(_repo_root()), check=False)
    return int(completed.returncode)

