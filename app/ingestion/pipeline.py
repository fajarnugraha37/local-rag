from __future__ import annotations

import fnmatch
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.common.content_hashing import sha256_hash
from app.config import runtime_settings as settings
from app.ingestion import chunking
from app.ingestion.extractors import ExtractorContext, ExtractorRegistry, build_default_registry
from app.ingestion.extractors.base import MissingDependencyError, UnsupportedFormatError
from app.ingestion.vector_ingest_service import ingest_chunks


def render_progress_line(prefix: str, current: int, total: int, *, width: int = 30) -> str:
    safe_total = max(1, total)
    safe_current = min(max(current, 0), safe_total)
    ratio = safe_current / safe_total
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    percent = int(ratio * 100)
    return f"\r{prefix}: [{bar}] {percent:3d}% ({safe_current}/{safe_total})"


@dataclass
class IngestOptions:
    recursive: bool
    include_patterns: List[str]
    exclude_patterns: List[str]
    max_bytes: int
    max_rows: int
    max_objects: int
    max_pages: int
    max_slides: int
    max_sheets: int
    max_zip_entries: int
    max_zip_uncompressed_bytes: int
    ingest_timeout_s: int
    chunk_max_tokens: int
    chunk_overlap_tokens: int
    enable_parquet: bool
    enable_legacy_office: bool


def _to_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _to_int(value, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and not value.strip():
        return default
    try:
        return int(value)
    except Exception:
        return default


def build_options(**overrides) -> IngestOptions:
    cfg = settings.CONFIG
    data = {
        "recursive": _to_bool(overrides.get("recursive"), False),
        "include_patterns": list(overrides.get("include_patterns") or []),
        "exclude_patterns": list(overrides.get("exclude_patterns") or []),
        "max_bytes": _to_int(
            overrides.get("max_bytes"), cfg.get("ingest_max_bytes", 8 * 1024 * 1024)
        ),
        "max_rows": _to_int(overrides.get("max_rows"), cfg.get("ingest_max_rows", 2000)),
        "max_objects": _to_int(overrides.get("max_objects"), cfg.get("ingest_max_objects", 2000)),
        "max_pages": _to_int(overrides.get("max_pages"), cfg.get("ingest_max_pages", 200)),
        "max_slides": _to_int(overrides.get("max_slides"), cfg.get("ingest_max_slides", 300)),
        "max_sheets": _to_int(overrides.get("max_sheets"), cfg.get("ingest_max_sheets", 50)),
        "max_zip_entries": _to_int(
            overrides.get("max_zip_entries"), cfg.get("ingest_zip_max_entries", 10000)
        ),
        "max_zip_uncompressed_bytes": _to_int(
            overrides.get("max_zip_uncompressed_bytes"),
            cfg.get("ingest_zip_max_uncompressed_bytes", 128 * 1024 * 1024),
        ),
        "ingest_timeout_s": _to_int(
            overrides.get("ingest_timeout_s"), cfg.get("ingest_timeout_s", 30)
        ),
        "chunk_max_tokens": _to_int(
            overrides.get("chunk_max_tokens"), cfg.get("chunk_max_tokens", 200)
        ),
        "chunk_overlap_tokens": _to_int(
            overrides.get("chunk_overlap_tokens"),
            cfg.get("chunk_overlap_tokens", 20),
        ),
        "enable_parquet": _to_bool(
            overrides.get("enable_parquet"), cfg.get("ingest_enable_parquet", True)
        ),
        "enable_legacy_office": _to_bool(
            overrides.get("enable_legacy_office"), cfg.get("ingest_enable_legacy_office", True)
        ),
    }
    return IngestOptions(**data)


def _context(options: IngestOptions) -> ExtractorContext:
    return ExtractorContext(
        max_bytes=options.max_bytes,
        max_rows=options.max_rows,
        max_objects=options.max_objects,
        max_pages=options.max_pages,
        max_slides=options.max_slides,
        max_sheets=options.max_sheets,
        max_zip_entries=options.max_zip_entries,
        max_zip_uncompressed_bytes=options.max_zip_uncompressed_bytes,
        ingest_timeout_s=options.ingest_timeout_s,
        enable_parquet=options.enable_parquet,
        enable_legacy_office=options.enable_legacy_office,
        extracted_at=datetime.now(timezone.utc).isoformat(),
    )


def _path_allowed(
    path: str, include_patterns: Sequence[str], exclude_patterns: Sequence[str]
) -> bool:
    normalized = path.replace("\\", "/")
    if include_patterns and not any(fnmatch.fnmatch(normalized, pat) for pat in include_patterns):
        return False
    if exclude_patterns and any(fnmatch.fnmatch(normalized, pat) for pat in exclude_patterns):
        return False
    return True


def _collect_paths(
    paths: Sequence[str],
    *,
    recursive: bool,
    include_patterns: Sequence[str],
    exclude_patterns: Sequence[str],
) -> List[str]:
    resolved: List[str] = []
    for raw in paths:
        if not raw:
            continue
        path = os.path.abspath(raw)
        if os.path.isfile(path):
            if _path_allowed(path, include_patterns, exclude_patterns):
                resolved.append(path)
            continue
        if os.path.isdir(path):
            if recursive:
                for root, _, files in os.walk(path):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        if _path_allowed(file_path, include_patterns, exclude_patterns):
                            resolved.append(file_path)
            else:
                for file_name in os.listdir(path):
                    file_path = os.path.join(path, file_name)
                    if os.path.isfile(file_path) and _path_allowed(
                        file_path, include_patterns, exclude_patterns
                    ):
                        resolved.append(file_path)
            continue
        resolved.append(path)
    return sorted(dict.fromkeys(resolved))


def _chunks_for_document(
    path: str, doc, options: IngestOptions, ctx: ExtractorContext
) -> List[Dict[str, object]]:
    source_name = os.path.basename(path)
    ext_info = chunking.normalize_extension(source_name)

    chunks: List[Dict[str, object]] = []
    chunk_index = 0

    for unit in doc.units:
        unit_text = (unit.text or "").strip()
        if not unit_text:
            continue
        split_chunks = chunking.chunk_unit(
            unit_text,
            doc.doc_type,
            max_tokens=options.chunk_max_tokens,
            overlap_tokens=options.chunk_overlap_tokens,
        )
        for text_chunk in split_chunks:
            chunk_index += 1
            metadata = {
                "source_path": path,
                "source_name": source_name,
                "source_kind": "file",
                "extension": ext_info["extension"],
                "special_name": ext_info["special_name"],
                "doc_type": doc.doc_type,
                "content_hash": sha256_hash(text_chunk),
                "extracted_at": ctx.extracted_at,
                "chunk_index": chunk_index,
            }
            if doc.metadata:
                metadata.update(chunking.normalize_locator_metadata(doc.metadata))
            if unit.metadata:
                metadata.update(chunking.normalize_locator_metadata(unit.metadata))
            chunks.append({"text": text_chunk, "metadata": metadata})
    return chunks


def ingest_single_path(
    path: str,
    *,
    registry: Optional[ExtractorRegistry] = None,
    options: Optional[IngestOptions] = None,
    embedding_model: Optional[str] = None,
    doc_id: Optional[str] = None,
    namespace: Optional[str] = None,
    progress_callback=None,
) -> Dict[str, object]:
    started = time.monotonic()
    registry = registry or build_default_registry()
    options = options or build_options()
    ctx = _context(options)

    if not os.path.exists(path):
        return {
            "path": path,
            "status": "skipped",
            "reason": "path_not_found",
            "warnings": [],
            "chunks_count": 0,
            "bytes_processed": 0,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    if os.path.isdir(path):
        return {
            "path": path,
            "status": "skipped",
            "reason": "path_is_directory_use_ingest_paths",
            "warnings": [],
            "chunks_count": 0,
            "bytes_processed": 0,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    bytes_processed = os.path.getsize(path)
    try:
        document = registry.extract_from_path(path, ctx)
    except UnsupportedFormatError as exc:
        return {
            "path": path,
            "status": "skipped",
            "reason": str(exc),
            "warnings": [],
            "chunks_count": 0,
            "bytes_processed": bytes_processed,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except MissingDependencyError as exc:
        return {
            "path": path,
            "status": "skipped",
            "reason": str(exc),
            "warnings": ["missing_dependency"],
            "chunks_count": 0,
            "bytes_processed": bytes_processed,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as exc:
        return {
            "path": path,
            "status": "failed",
            "reason": str(exc),
            "warnings": [],
            "chunks_count": 0,
            "bytes_processed": bytes_processed,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    chunks = _chunks_for_document(path, document, options, ctx)
    if not chunks:
        return {
            "path": path,
            "status": "skipped",
            "reason": "no_extractable_content",
            "warnings": list(document.warnings),
            "chunks_count": 0,
            "bytes_processed": bytes_processed,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    ingest_progress = None
    if progress_callback:

        def _progress_with_file(stage, current, total, stats):
            merged = dict(stats or {})
            merged["file_path"] = path
            progress_callback(stage, current, total, merged)

        ingest_progress = _progress_with_file

    upsert_result = ingest_chunks(
        chunks,
        source_path=path,
        doc_id=doc_id,
        namespace=namespace,
        embedding_model=embedding_model,
        progress_callback=ingest_progress,
    )
    return {
        "path": path,
        "status": "ok",
        "reason": "",
        "warnings": list(document.warnings),
        "chunks_count": len(chunks),
        "bytes_processed": bytes_processed,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "upsert": upsert_result,
    }


def ingest_uploaded_files(
    uploaded: Sequence[Tuple[str, bytes]],
    *,
    registry: Optional[ExtractorRegistry] = None,
    options: Optional[IngestOptions] = None,
    embedding_model: Optional[str] = None,
    namespace: Optional[str] = None,
    progress_callback=None,
) -> Dict[str, object]:
    registry = registry or build_default_registry()
    options = options or build_options()
    ctx = _context(options)

    results: List[Dict[str, object]] = []
    total_chunks = 0
    extracted = 0
    skipped = 0

    for file_name, raw_bytes in uploaded:
        started = time.monotonic()
        try:
            document = registry.extract_from_bytes(file_name, raw_bytes, ctx)
            fake_path = file_name
            chunks = _chunks_for_document(fake_path, document, options, ctx)
            if not chunks:
                skipped += 1
                results.append(
                    {
                        "path": file_name,
                        "status": "skipped",
                        "reason": "no_extractable_content",
                        "warnings": list(document.warnings),
                        "chunks_count": 0,
                        "bytes_processed": len(raw_bytes),
                        "duration_ms": int((time.monotonic() - started) * 1000),
                    }
                )
                continue
            upsert = ingest_chunks(
                chunks,
                source_path=file_name,
                doc_id=file_name,
                namespace=namespace,
                embedding_model=embedding_model,
                progress_callback=progress_callback,
            )
            extracted += 1
            total_chunks += len(chunks)
            results.append(
                {
                    "path": file_name,
                    "status": "ok",
                    "reason": "",
                    "warnings": list(document.warnings),
                    "chunks_count": len(chunks),
                    "bytes_processed": len(raw_bytes),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "upsert": upsert,
                }
            )
        except UnsupportedFormatError as exc:
            skipped += 1
            results.append(
                {
                    "path": file_name,
                    "status": "skipped",
                    "reason": str(exc),
                    "warnings": [],
                    "chunks_count": 0,
                    "bytes_processed": len(raw_bytes),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
            )
        except MissingDependencyError as exc:
            skipped += 1
            results.append(
                {
                    "path": file_name,
                    "status": "skipped",
                    "reason": str(exc),
                    "warnings": ["missing_dependency"],
                    "chunks_count": 0,
                    "bytes_processed": len(raw_bytes),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "path": file_name,
                    "status": "failed",
                    "reason": str(exc),
                    "warnings": [],
                    "chunks_count": 0,
                    "bytes_processed": len(raw_bytes),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
            )

    return {
        "total_files": len(uploaded),
        "extracted": extracted,
        "skipped": skipped,
        "failed": len([r for r in results if r.get("status") == "failed"]),
        "total_chunks": total_chunks,
        "files": results,
    }


def ingest_paths(
    paths: Sequence[str],
    *,
    registry: Optional[ExtractorRegistry] = None,
    options: Optional[IngestOptions] = None,
    embedding_model: Optional[str] = None,
    namespace: Optional[str] = None,
    progress_callback=None,
) -> Dict[str, object]:
    registry = registry or build_default_registry()
    options = options or build_options()

    candidates = _collect_paths(
        paths,
        recursive=options.recursive,
        include_patterns=options.include_patterns,
        exclude_patterns=options.exclude_patterns,
    )

    results: List[Dict[str, object]] = []
    total_chunks = 0
    extracted = 0
    skipped = 0

    for candidate in candidates:
        item = ingest_single_path(
            candidate,
            registry=registry,
            options=options,
            embedding_model=embedding_model,
            namespace=namespace,
            progress_callback=progress_callback,
        )
        results.append(item)
        status = item.get("status")
        if status == "ok":
            extracted += 1
            total_chunks += int(item.get("chunks_count", 0))
        elif status == "skipped":
            skipped += 1

    return {
        "total_files": len(candidates),
        "extracted": extracted,
        "skipped": skipped,
        "failed": len([r for r in results if r.get("status") == "failed"]),
        "total_chunks": total_chunks,
        "files": results,
    }
