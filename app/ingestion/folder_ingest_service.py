from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from app.config import runtime_settings as settings
from app.ingestion.file_state_store import FileStateStore
from app.ingestion.folder_scanner import ScanOptions, scan_folder
from app.ingestion.pipeline import IngestOptions, ingest_single_path


ProgressCallback = Callable[[str, Dict[str, object]], None]


@dataclass
class FolderIngestOptions:
    path: str
    recursive: bool = True
    include_patterns: List[str] | None = None
    exclude_patterns: List[str] | None = None
    respect_gitignore: bool = True
    respect_ragignore: bool = True
    extra_ignore_file: Optional[str] = None
    dry_run: bool = False
    force: bool = False
    embedding_model: Optional[str] = None
    state_path: Optional[str] = None
    ingest_options: Optional[IngestOptions] = None
    progress_callback: Optional[ProgressCallback] = None


def _hash_file(path: str, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            part = handle.read(chunk_size)
            if not part:
                break
            digest.update(part)
    return digest.hexdigest()


def _is_file_readable(path: str) -> bool:
    try:
        with open(path, "rb") as handle:
            handle.read(1)
        return True
    except Exception:
        return False


def _decide_action(path: str, store: FileStateStore, *, force: bool) -> tuple[str, Optional[str]]:
    if force:
        return "ingest", "forced"

    previous = store.get(path)
    if previous is None:
        return "ingest", "new_file"

    try:
        stat = os.stat(path)
    except Exception:
        return "skip", "stat_error"

    if previous.size_bytes == int(stat.st_size) and previous.mtime_ns == int(stat.st_mtime_ns):
        return "skip", "unchanged_stat"

    current_hash = _hash_file(path)
    if previous.content_hash and previous.content_hash == current_hash:
        return "skip", "unchanged_hash"
    return "ingest", "changed"


def ingest_folder(options: FolderIngestOptions) -> Dict[str, object]:
    state_path = options.state_path or str(settings.CONFIG.get("ingest_state_path", "data/ingest_state.json"))
    store = FileStateStore(state_path=state_path)
    scan_options = ScanOptions(
        recursive=options.recursive,
        include_patterns=list(options.include_patterns or []),
        exclude_patterns=list(options.exclude_patterns or []),
        respect_gitignore=options.respect_gitignore,
        respect_ragignore=options.respect_ragignore,
        extra_ignore_file=options.extra_ignore_file,
    )

    if options.progress_callback:
        options.progress_callback("scan_started", {"path": os.path.abspath(options.path)})
    candidates, scan_summary = scan_folder(options.path, options=scan_options)
    if options.progress_callback:
        options.progress_callback(
            "scan_done",
            {
                "scanned": scan_summary.scanned,
                "selected": scan_summary.selected,
                "scan_skipped": scan_summary.skipped,
            },
        )
    results: List[Dict[str, object]] = []
    ingested = 0
    skipped = 0
    failed = 0
    state_changed = False
    max_bytes = int(
        (options.ingest_options.max_bytes if options.ingest_options is not None else settings.CONFIG.get("ingest_max_bytes", 8 * 1024 * 1024))
        or 8 * 1024 * 1024
    )

    for candidate in candidates:
        if options.progress_callback:
            options.progress_callback("file_found", {"path": candidate.path})
            options.progress_callback("file_selected", {"path": candidate.path})
        if candidate.size_bytes > max_bytes:
            skipped += 1
            reason = f"file_too_large:{candidate.size_bytes}>{max_bytes}"
            results.append({"path": candidate.path, "status": "skipped", "reason": reason})
            if options.progress_callback:
                options.progress_callback("file_skipped", {"path": candidate.path, "reason": reason})
            continue
        if not _is_file_readable(candidate.path):
            skipped += 1
            reason = "unreadable_file"
            results.append({"path": candidate.path, "status": "skipped", "reason": reason})
            if options.progress_callback:
                options.progress_callback("file_skipped", {"path": candidate.path, "reason": reason})
            continue
        decision, reason = _decide_action(candidate.path, store, force=options.force)
        if decision == "skip":
            skipped += 1
            results.append({"path": candidate.path, "status": "skipped", "reason": reason})
            if options.progress_callback:
                options.progress_callback("file_skipped", {"path": candidate.path, "reason": reason})
            continue

        if options.dry_run:
            ingested += 1
            results.append({"path": candidate.path, "status": "planned", "reason": reason})
            if options.progress_callback:
                options.progress_callback("file_planned", {"path": candidate.path, "reason": reason})
            continue

        ingest_result = ingest_single_path(
            candidate.path,
            options=options.ingest_options,
            embedding_model=options.embedding_model,
            doc_id=os.path.basename(candidate.path),
        )
        status = str(ingest_result.get("status") or "")
        if status == "ok":
            stat = os.stat(candidate.path)
            store.set(
                candidate.path,
                size_bytes=int(stat.st_size),
                mtime_ns=int(stat.st_mtime_ns),
                content_hash=_hash_file(candidate.path),
            )
            state_changed = True
            ingested += 1
            if options.progress_callback:
                options.progress_callback("file_ingested", {"path": candidate.path, "reason": reason})
        elif status == "skipped":
            skipped += 1
            if options.progress_callback:
                options.progress_callback("file_skipped", {"path": candidate.path, "reason": reason})
        else:
            failed += 1
            if options.progress_callback:
                options.progress_callback("file_failed", {"path": candidate.path, "reason": reason})
        entry = {"path": candidate.path, "status": status, "reason": reason}
        entry.update(ingest_result)
        results.append(entry)

    if state_changed and not options.dry_run:
        store.save()

    return {
        "path": os.path.abspath(options.path),
        "dry_run": options.dry_run,
        "force": options.force,
        "state_path": os.path.abspath(state_path),
        "scanned": scan_summary.scanned,
        "selected": scan_summary.selected,
        "scan_skipped": scan_summary.skipped,
        "ingested": ingested,
        "skipped": skipped,
        "failed": failed,
        "files": results,
    }


__all__ = ["FolderIngestOptions", "ingest_folder"]
