from __future__ import annotations

import argparse
from typing import Sequence

from app.ingestion import folder_ingest_cli as ingest_folder_cli


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest an entire folder recursively with incremental skip support.")
    parser.add_argument("--path", required=True, help="Root folder path to scan and ingest.")
    parser.add_argument("--recursive", action="store_true", help="Enable recursive traversal (default: true).")
    parser.add_argument("--no-recursive", action="store_true", help="Disable recursive traversal.")
    parser.add_argument("--include", action="append", default=[], help="Glob include pattern (repeatable).")
    parser.add_argument("--exclude", action="append", default=[], help="Glob exclude pattern (repeatable).")
    parser.add_argument("--respect-gitignore", dest="respect_gitignore", action="store_true", help="Respect .gitignore rules (default).")
    parser.add_argument("--no-respect-gitignore", dest="respect_gitignore", action="store_false", help="Ignore .gitignore files.")
    parser.add_argument("--dry-run", action="store_true", help="Plan ingest/skip decisions without writing vectors/state.")
    parser.add_argument("--force", action="store_true", help="Force reingestion even when files are unchanged.")
    parser.add_argument("--namespace", default=None, help="Namespace to assign to ingested chunks (default: default).")
    parser.set_defaults(recursive=True, respect_gitignore=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    ingest_folder_cli.run_folder_ingest(args)
