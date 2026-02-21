from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from app.common.namespaces import validate_namespace


@dataclass
class DocRegistryRecord:
    namespace: str
    doc_id: str
    source_path: str
    source_type: str
    title: str
    content_hash: str
    chunk_count: int
    created_at: str
    updated_at: str
    last_ingested_at: str
    size_bytes: int
    tags: List[str]


class DocRegistryStore:
    def __init__(self, registry_path: str) -> None:
        self.registry_path = os.path.abspath(registry_path)
        self._records: Dict[Tuple[str, str], DocRegistryRecord] = {}
        self._loaded = False

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _to_key(namespace: str, doc_id: str) -> Tuple[str, str]:
        return validate_namespace(namespace, default_to_default=True), str(doc_id or "").strip()

    @staticmethod
    def _encode_key(namespace: str, doc_id: str) -> str:
        return f"{namespace}::{doc_id}"

    @staticmethod
    def _decode_key(encoded: str) -> Optional[Tuple[str, str]]:
        if "::" not in str(encoded):
            return None
        namespace, doc_id = str(encoded).split("::", 1)
        doc_id = doc_id.strip()
        if not doc_id:
            return None
        return validate_namespace(namespace, default_to_default=True), doc_id

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not os.path.exists(self.registry_path):
            self._records = {}
            return
        try:
            with open(self.registry_path, "r", encoding="utf-8") as handle:
                raw = json.load(handle) or {}
        except Exception:
            self._records = {}
            return

        parsed: Dict[Tuple[str, str], DocRegistryRecord] = {}
        if not isinstance(raw, dict):
            self._records = {}
            return
        for raw_key, value in raw.items():
            if not isinstance(value, dict):
                continue
            decoded = self._decode_key(str(raw_key))
            if decoded is None:
                continue
            namespace, doc_id = decoded
            try:
                parsed[(namespace, doc_id)] = DocRegistryRecord(
                    namespace=namespace,
                    doc_id=doc_id,
                    source_path=str(value.get("source_path") or ""),
                    source_type=str(value.get("source_type") or "file"),
                    title=str(value.get("title") or doc_id),
                    content_hash=str(value.get("content_hash") or ""),
                    chunk_count=int(value.get("chunk_count") or 0),
                    created_at=str(value.get("created_at") or self._now_iso()),
                    updated_at=str(value.get("updated_at") or self._now_iso()),
                    last_ingested_at=str(value.get("last_ingested_at") or self._now_iso()),
                    size_bytes=int(value.get("size_bytes") or 0),
                    tags=[str(tag) for tag in (value.get("tags") or [])],
                )
            except Exception:
                continue
        self._records = parsed

    def save(self) -> None:
        self._load()
        parent = os.path.dirname(self.registry_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        serializable = {}
        for (namespace, doc_id), record in sorted(self._records.items()):
            serializable[self._encode_key(namespace, doc_id)] = asdict(record)
        with open(self.registry_path, "w", encoding="utf-8") as handle:
            json.dump(serializable, handle, indent=2, sort_keys=True)

    def get(self, namespace: str, doc_id: str) -> Optional[DocRegistryRecord]:
        self._load()
        return self._records.get(self._to_key(namespace, doc_id))

    def upsert(
        self,
        *,
        namespace: str,
        doc_id: str,
        source_path: str = "",
        source_type: str = "file",
        title: str = "",
        content_hash: str = "",
        chunk_count: int = 0,
        size_bytes: int = 0,
        tags: Optional[List[str]] = None,
        last_ingested_at: Optional[str] = None,
    ) -> DocRegistryRecord:
        self._load()
        key = self._to_key(namespace, doc_id)
        if not key[1]:
            raise ValueError("doc_id is required.")
        now = self._now_iso()
        existing = self._records.get(key)
        created_at = existing.created_at if existing is not None else now
        record = DocRegistryRecord(
            namespace=key[0],
            doc_id=key[1],
            source_path=str(source_path or (existing.source_path if existing else "")),
            source_type=str(source_type or (existing.source_type if existing else "file")),
            title=str(title or (existing.title if existing else key[1])),
            content_hash=str(content_hash or (existing.content_hash if existing else "")),
            chunk_count=int(chunk_count if chunk_count else (existing.chunk_count if existing else 0)),
            created_at=created_at,
            updated_at=now,
            last_ingested_at=str(last_ingested_at or now),
            size_bytes=int(size_bytes if size_bytes else (existing.size_bytes if existing else 0)),
            tags=[str(tag) for tag in (tags if tags is not None else (existing.tags if existing else []))],
        )
        self._records[key] = record
        return record

    def delete(self, namespace: str, doc_id: str) -> bool:
        self._load()
        key = self._to_key(namespace, doc_id)
        return self._records.pop(key, None) is not None

    def list_docs(
        self,
        *,
        namespace: Optional[str] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Dict[str, object]:
        self._load()
        safe_limit = max(1, int(limit or 50))
        cursor_key = self._decode_key(cursor) if cursor else None
        namespace_filter = validate_namespace(namespace, default_to_default=True) if namespace is not None else None

        keys = sorted(self._records.keys())
        rows: List[DocRegistryRecord] = []
        for key in keys:
            if namespace_filter is not None and key[0] != namespace_filter:
                continue
            if cursor_key is not None and key <= cursor_key:
                continue
            rows.append(self._records[key])

        page = rows[:safe_limit]
        next_cursor = None
        if len(rows) > safe_limit and page:
            last = page[-1]
            next_cursor = self._encode_key(last.namespace, last.doc_id)
        return {
            "records": [asdict(record) for record in page],
            "next_cursor": next_cursor,
        }


__all__ = ["DocRegistryRecord", "DocRegistryStore"]
