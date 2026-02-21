from __future__ import annotations

import os
from typing import Dict, Sequence

from app.ingestion.folder_ingest_service import FolderIngestOptions, ingest_folder
from app.ingestion.pipeline import render_progress_line


def _render_progress(counts: Dict[str, int], *, scanned: int, selected: int) -> None:
    total = max(1, selected or scanned or 1)
    current = min(total, counts["ingested"] + counts["skipped"] + counts["failed"])
    prefix = (
        f"Progress scanned={scanned} selected={selected} "
        f"ingested={counts['ingested']} skipped={counts['skipped']} failed={counts['failed']}"
    )
    print(render_progress_line(prefix, current, total, width=20).replace("\r", ""))


def run_folder_ingest(args) -> None:
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
            namespace=args.namespace,
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


def main(argv: Sequence[str] | None = None) -> None:
    # Compatibility wrapper: CLI parsing now lives in app.cli.ingest_folder.
    from app.cli.ingest_folder import main as cli_main

    cli_main(argv)
