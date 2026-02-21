from __future__ import annotations

import argparse
from typing import Sequence

from app.ingestion import file_ingest_gui as ingest_service


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest files into vector storage. Use --path for non-GUI mode.",
    )
    parser.add_argument(
        "--path",
        dest="paths",
        action="append",
        default=[],
        help="File or directory path to ingest. Repeat --path for multiple inputs.",
    )
    parser.add_argument("--recursive", action="store_true", help="Recursively ingest files inside directories.")
    parser.add_argument("--include", action="append", default=[], help="Glob include filter (repeatable).")
    parser.add_argument("--exclude", action="append", default=[], help="Glob exclude filter (repeatable).")
    parser.add_argument("--max-bytes", type=int, default=None, help="Max bytes per file.")
    parser.add_argument("--max-rows", type=int, default=None, help="Max rows/records per structured file.")
    parser.add_argument("--max-pages", type=int, default=None, help="Max pages for PDF.")
    parser.add_argument("--max-slides", type=int, default=None, help="Max slides for PPT/PPTX.")
    parser.add_argument("--max-sheets", type=int, default=None, help="Max sheets for XLS/XLSX.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failed file.")
    parser.add_argument("--namespace", default=None, help="Namespace to assign to ingested chunks (default: default).")
    return parser


def main(argv: Sequence[str] | None = None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.paths:
        ingest_service.run_ingestion(
            args.paths,
            recursive=args.recursive,
            include_patterns=args.include,
            exclude_patterns=args.exclude,
            max_bytes=args.max_bytes,
            max_rows=args.max_rows,
            max_pages=args.max_pages,
            max_slides=args.max_slides,
            max_sheets=args.max_sheets,
            fail_fast=args.fail_fast,
            namespace=args.namespace,
        )
        return
    ingest_service.launch_gui()
