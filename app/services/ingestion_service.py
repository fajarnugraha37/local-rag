from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.common.namespaces import validate_namespace
from app.config import runtime_settings as settings
from app.ingestion.folder_ingest_service import FolderIngestOptions, ingest_folder
from app.ingestion.pipeline import build_options, ingest_uploaded_files
from app.repositories.sqlite.documents_repo import DocumentsRepository
from app.repositories.sqlite.ingestions_repo import IngestionsRepository
from app.repositories.sqlite.namespaces_repo import NamespacesRepository


@dataclass
class UploadPayload:
    files: list[tuple[str, bytes]]
    fields: dict[str, str]


class IngestionService:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.repo = IngestionsRepository(db_path)
        self.docs_repo = DocumentsRepository(db_path)
        self.ns_repo = NamespacesRepository(db_path)
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        namespace: str,
        source_type: str,
        source_spec: dict[str, Any],
        upload_payload: UploadPayload | None = None,
    ) -> dict[str, Any]:
        ingestion_id = str(uuid.uuid4())
        ns = validate_namespace(namespace, default_to_default=True)
        record = self.repo.create(
            ingestion_id=ingestion_id,
            namespace=ns,
            source_type=source_type,
            source_spec=source_spec,
            status="queued",
        )
        self.repo.add_event(ingestion_id, "queued", {"source_type": source_type})

        t = threading.Thread(
            target=self._run_job,
            kwargs={
                "ingestion_id": ingestion_id,
                "namespace": ns,
                "source_type": source_type,
                "source_spec": source_spec,
                "upload_payload": upload_payload,
            },
            daemon=True,
        )
        with self._lock:
            self._threads[ingestion_id] = t
        t.start()
        return record

    def list_jobs(self, namespace: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        ns = validate_namespace(namespace, default_to_default=True) if namespace else None
        return self.repo.list(namespace=ns, limit=limit)

    def get_job(self, ingestion_id: str) -> dict[str, Any] | None:
        return self.repo.get(ingestion_id)

    def list_events(self, ingestion_id: str, limit: int = 500) -> list[dict[str, Any]]:
        return self.repo.list_events(ingestion_id, limit=limit)

    def cancel_job(self, ingestion_id: str) -> bool:
        ok = self.repo.request_cancel(ingestion_id)
        if ok:
            self.repo.add_event(ingestion_id, "cancel_requested", {})
        return ok

    def _is_cancelled(self, ingestion_id: str) -> bool:
        record = self.repo.get(ingestion_id)
        return bool(record and record.get("cancel_requested"))

    def _run_job(
        self,
        ingestion_id: str,
        namespace: str,
        source_type: str,
        source_spec: dict[str, Any],
        upload_payload: UploadPayload | None,
    ) -> None:
        self.repo.update_status(ingestion_id, "running")
        self.repo.add_event(ingestion_id, "running", {})

        if self._is_cancelled(ingestion_id):
            self.repo.update_status(ingestion_id, "cancelled")
            self.repo.add_event(ingestion_id, "cancelled", {"phase": "startup"})
            return

        try:
            if source_type == "folder":
                summary = self._run_folder(ingestion_id, namespace, source_spec)
            elif source_type == "repo":
                summary = self._run_repo(ingestion_id, namespace, source_spec)
            elif source_type == "upload":
                summary = self._run_upload(ingestion_id, namespace, source_spec, upload_payload)
            else:
                raise ValueError(f"unsupported source_type: {source_type}")

            if self._is_cancelled(ingestion_id):
                self.repo.add_event(ingestion_id, "cancelled", {"phase": "finalize"})
                self.repo.update_status(ingestion_id, "cancelled")
                return

            self._persist_metadata_from_summary(
                ingestion_id=ingestion_id,
                namespace=namespace,
                source_type=source_type,
                summary=summary,
            )

            counters = {
                "ingested": int(summary.get("ingested") or summary.get("extracted") or 0),
                "skipped": int(summary.get("skipped") or 0),
                "failed": int(summary.get("failed") or 0),
            }
            self.repo.add_event(ingestion_id, "done", {"summary": summary})
            self.repo.update_status(ingestion_id, "done", counters=counters)
        except Exception as exc:
            self.repo.add_event(ingestion_id, "failed", {"error": str(exc)})
            self.repo.update_status(ingestion_id, "failed", last_error=str(exc))

    def _persist_metadata_from_summary(
        self,
        *,
        ingestion_id: str,
        namespace: str,
        source_type: str,
        summary: dict[str, Any],
    ) -> None:
        def _retry_write(fn, *, retries: int = 5, delay_s: float = 0.15) -> bool:
            last_exc: Exception | None = None
            for _ in range(max(1, retries)):
                try:
                    fn()
                    return True
                except Exception as exc:
                    last_exc = exc
                    time.sleep(delay_s)
            if last_exc is not None:
                self.repo.add_event(
                    ingestion_id,
                    "metadata_write_failed",
                    {"error": str(last_exc)},
                )
            return False

        ok_ns = _retry_write(lambda: self.ns_repo.create(namespace, defaults={}))
        if not ok_ns:
            return

        files = list(summary.get("files") or [])
        now_iso = datetime.now(timezone.utc).isoformat()
        persisted_docs = 0
        for item in files:
            status = str(item.get("status") or "")
            if status != "ok":
                continue
            path = str(item.get("path") or "").strip()
            if not path:
                continue
            doc_id = os.path.basename(path) or path
            record = {
                "namespace": namespace,
                "doc_id": doc_id,
                "source_path": path,
                "source_type": source_type,
                "title": doc_id,
                "content_hash": None,
                "chunk_count": int(item.get("chunks_count") or 0),
                "size_bytes": int(item.get("bytes_processed") or 0),
                "tags": [],
                "last_ingested_at": now_iso,
            }
            ok_doc = _retry_write(lambda r=record: self.docs_repo.upsert(r))
            if ok_doc:
                persisted_docs += 1
        self.repo.add_event(
            ingestion_id,
            "metadata_persisted",
            {"namespace": namespace, "documents_upserted": persisted_docs},
        )

    def _run_folder(
        self, ingestion_id: str, namespace: str, source_spec: dict[str, Any]
    ) -> dict[str, Any]:
        path = str(source_spec.get("path") or "").strip()
        if not path:
            raise ValueError("folder source_spec.path is required")

        def _on_progress(event_name: str, payload: dict[str, Any]):
            if self._is_cancelled(ingestion_id):
                raise RuntimeError("ingestion cancelled")
            self.repo.add_event(ingestion_id, event_name, payload)

        options = FolderIngestOptions(
            path=path,
            recursive=bool(source_spec.get("recursive", True)),
            include_patterns=list(source_spec.get("include") or []),
            exclude_patterns=list(source_spec.get("exclude") or []),
            respect_gitignore=bool(source_spec.get("respect_gitignore", True)),
            dry_run=bool(source_spec.get("dry_run", False)),
            force=bool(source_spec.get("force", False)),
            embedding_model=source_spec.get("embedding_model"),
            namespace=namespace,
            parallel_workers=int(source_spec.get("parallel_workers") or 1),
            ingest_options=build_options(
                chunk_max_tokens=source_spec.get("chunk_max_tokens"),
                chunk_overlap_tokens=source_spec.get("chunk_overlap_tokens"),
                ocr_enabled=source_spec.get("ocr_enabled"),
                max_bytes=source_spec.get("max_bytes"),
                max_rows=source_spec.get("max_rows"),
                max_pages=source_spec.get("max_pages"),
                max_slides=source_spec.get("max_slides"),
                max_sheets=source_spec.get("max_sheets"),
                ingest_timeout_s=source_spec.get("ingest_timeout_s"),
            ),
            progress_callback=_on_progress,
        )
        return ingest_folder(options)

    def _run_repo(
        self, ingestion_id: str, namespace: str, source_spec: dict[str, Any]
    ) -> dict[str, Any]:
        repo_url = str(source_spec.get("repo") or "").strip()
        if not repo_url:
            raise ValueError("repo source_spec.repo is required")
        revision = str(source_spec.get("revision") or "").strip()
        work_root = Path(
            str(settings.CONFIG.get("ingest_repo_workspace") or "data/ingestions/repos")
        )
        work_root.mkdir(parents=True, exist_ok=True)
        clone_dir = work_root / ingestion_id

        if clone_dir.exists():
            shutil.rmtree(clone_dir, ignore_errors=True)

        self.repo.add_event(ingestion_id, "repo_clone_started", {"repo": repo_url})
        subprocess.run(["git", "clone", repo_url, str(clone_dir)], check=True, capture_output=True)
        if revision:
            subprocess.run(
                ["git", "-C", str(clone_dir), "checkout", revision],
                check=True,
                capture_output=True,
            )

        source_spec_folder = {
            "path": str(clone_dir),
            "recursive": True,
            "respect_gitignore": True,
            "dry_run": bool(source_spec.get("dry_run", False)),
            "force": bool(source_spec.get("force", False)),
            "embedding_model": source_spec.get("embedding_model"),
            "include": list(source_spec.get("include") or []),
            "exclude": list(source_spec.get("exclude") or []),
        }
        return self._run_folder(ingestion_id, namespace, source_spec_folder)

    def _run_upload(
        self,
        ingestion_id: str,
        namespace: str,
        source_spec: dict[str, Any],
        upload_payload: UploadPayload | None,
    ) -> dict[str, Any]:
        if upload_payload is None or not upload_payload.files:
            raise ValueError("upload payload is required")

        temp_dir = Path(tempfile.mkdtemp(prefix=f"ingestion-{ingestion_id}-"))
        try:
            uploaded: list[tuple[str, bytes]] = []
            for name, blob in upload_payload.files:
                file_name = os.path.basename(name) or "upload.bin"
                uploaded.append((file_name, blob))
                self.repo.add_event(
                    ingestion_id, "upload_file_received", {"name": file_name, "size": len(blob)}
                )

            options = build_options(
                max_bytes=upload_payload.fields.get(
                    "max_bytes", settings.CONFIG.get("ingest_max_bytes", 8 * 1024 * 1024)
                ),
                max_rows=upload_payload.fields.get(
                    "max_rows", settings.CONFIG.get("ingest_max_rows", 2000)
                ),
                max_pages=upload_payload.fields.get(
                    "max_pages", settings.CONFIG.get("ingest_max_pages", 200)
                ),
                max_slides=upload_payload.fields.get(
                    "max_slides", settings.CONFIG.get("ingest_max_slides", 300)
                ),
                max_sheets=upload_payload.fields.get(
                    "max_sheets", settings.CONFIG.get("ingest_max_sheets", 50)
                ),
                chunk_max_tokens=upload_payload.fields.get("chunk_max_tokens"),
                chunk_overlap_tokens=upload_payload.fields.get("chunk_overlap_tokens"),
                ocr_enabled=upload_payload.fields.get("ocr_enabled"),
                ingest_timeout_s=upload_payload.fields.get("ingest_timeout_s"),
            )
            def _on_upload_progress(stage: str, current: int, total: int, stats: dict[str, Any]):
                payload = {
                    "stage": stage,
                    "current": int(current),
                    "total": int(total),
                    "stats": dict(stats or {}),
                }
                self.repo.add_event(ingestion_id, stage, payload)
                if stage in {"file_ingested", "file_skipped", "file_failed"}:
                    record = self.repo.get(ingestion_id) or {}
                    counters = dict(record.get("counters") or {})
                    if stage == "file_ingested":
                        counters["ingested"] = int(counters.get("ingested") or 0) + 1
                    elif stage == "file_skipped":
                        counters["skipped"] = int(counters.get("skipped") or 0) + 1
                    elif stage == "file_failed":
                        counters["failed"] = int(counters.get("failed") or 0) + 1
                    self.repo.update_status(ingestion_id, str(record.get("status") or "running"), counters=counters)
            try:
                return ingest_uploaded_files(
                    uploaded,
                    options=options,
                    embedding_model=source_spec.get("embedding_model")
                    or upload_payload.fields.get("embedding_model"),
                    namespace=namespace,
                    progress_callback=_on_upload_progress,
                )
            except TypeError:
                # Compatibility for tests or monkeypatched callables that do not accept progress_callback.
                return ingest_uploaded_files(
                    uploaded,
                    options=options,
                    embedding_model=source_spec.get("embedding_model")
                    or upload_payload.fields.get("embedding_model"),
                    namespace=namespace,
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
