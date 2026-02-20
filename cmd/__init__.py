"""Centralized command launcher package.

This package name collides with Python's stdlib ``cmd`` module. To keep
stdlib consumers (for example ``pdb`` via ``pytest``) working, we re-export
the stdlib ``Cmd`` class from here.
"""

from __future__ import annotations

import importlib.util
import os
import sysconfig
from types import ModuleType
from typing import Optional


def _load_stdlib_cmd() -> Optional[ModuleType]:
    stdlib_dir = sysconfig.get_path("stdlib")
    if not stdlib_dir:
        return None
    module_path = os.path.join(stdlib_dir, "cmd.py")
    if not os.path.exists(module_path):
        return None

    spec = importlib.util.spec_from_file_location("_stdlib_cmd", module_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_stdlib_cmd = _load_stdlib_cmd()
if _stdlib_cmd is not None and hasattr(_stdlib_cmd, "Cmd"):
    Cmd = _stdlib_cmd.Cmd

