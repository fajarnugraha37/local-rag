from __future__ import annotations

import argparse
import os
from typing import Dict, Sequence

from app.ingestion.folder_ingest_service import FolderIngestOptions, ingest_folder


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
    parser.set_defaults(recursive=True, respect_gitignore=True)
    return parser


def _render_progress(counts: Dict[str, int], *, scanned: int, selected: int) -> None:
    print(
        "Progress: "
        f"scanned={scanned} "
        f"selected={selected} "
        f"ingested={counts['ingested']} "
        f"skipped={counts['skipped']} "
        f"failed={counts['failed']}"
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    recursive = bool(args.recursive and not args.no_recursive)

    progress_counts = {"ingested": 0, "skipped": 0, "failed": 0}
    scan_counts = {"scanned": 0, "selected": 0}

    def _on_progress(event: str, payload: Dict[str, object]) -> None:
        if event == "scan_done":
            scan_counts["scanned"] = int(payload.get("scanned") or 0)
            scan_counts["selected"] = int(payload.get("selected") or 0)
            _render_progress(progress_counts, scanned=scan_counts["scanned"], selected=scan_counts["selected"])
            return
        if event in {"file_ingested", "file_planned"}:
            progress_counts["ingested"] += 1
        elif event == "file_skipped":
            progress_counts["skipped"] += 1
        elif event == "file_failed":
            progress_counts["failed"] += 1
        else:
            return
        file_path = str(payload.get("path") or "")
        reason = str(payload.get("reason") or "")
        print(f"[{event}] {file_path} reason={reason}")
        _render_progress(progress_counts, scanned=scan_counts["scanned"], selected=scan_counts["selected"])

    result = ingest_folder(
        FolderIngestOptions(
            path=args.path,
            recursive=recursive,
            include_patterns=list(args.include or []),
            exclude_patterns=list(args.exclude or []),
            respect_gitignore=bool(args.respect_gitignore),
            dry_run=bool(args.dry_run),
            force=bool(args.force),
            progress_callback=_on_progress,
        )
    )

    print(
        "Summary: "
        f"path={os.path.abspath(str(result.get('path') or args.path))} "
        f"dry_run={bool(result.get('dry_run'))} "
        f"force={bool(result.get('force'))} "
        f"scanned={int(result.get('scanned') or 0)} "
        f"selected={int(result.get('selected') or 0)} "
        f"ingested={int(result.get('ingested') or 0)} "
        f"skipped={int(result.get('skipped') or 0)} "
        f"failed={int(result.get('failed') or 0)}"
    )


if __name__ == "__main__":
    main()
