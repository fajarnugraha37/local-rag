from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.repositories.sqlite.db import connect


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocumentsRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def upsert(self, record: dict[str, Any]) -> dict[str, Any]:
        now = _now_iso()
        namespace = record["namespace"]
        doc_id = record["doc_id"]
        with connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT created_at FROM documents WHERE namespace = ? AND doc_id = ?",
                (namespace, doc_id),
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """
                INSERT OR REPLACE INTO documents(
                    namespace, doc_id, source_path, source_type, title, content_hash, chunk_count,
                    size_bytes, tags_json, created_at, updated_at, last_ingested_at, deleted_at, repo, "commit"
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    namespace,
                    doc_id,
                    record.get("source_path"),
                    record.get("source_type"),
                    record.get("title"),
                    record.get("content_hash"),
                    record.get("chunk_count"),
                    record.get("size_bytes"),
                    json.dumps(record.get("tags") or [], sort_keys=True),
                    created_at,
                    now,
                    record.get("last_ingested_at") or now,
                    record.get("deleted_at"),
                    record.get("repo"),
                    record.get("commit"),
                ),
            )
        return self.get(namespace, doc_id, include_deleted=True) or {}

    def get(self, namespace: str, doc_id: str, include_deleted: bool = False) -> dict[str, Any] | None:
        query = "SELECT * FROM documents WHERE namespace = ? AND doc_id = ?"
        params: list[Any] = [namespace, doc_id]
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        with connect(self.db_path) as conn:
            row = conn.execute(query, params).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["tags"] = json.loads(data.pop("tags_json") or "[]")
        return data

    def list(
        self,
        namespace: str | None = None,
        include_deleted: bool = False,
        limit: int = 50,
        cursor: tuple[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM documents WHERE 1=1"
        params: list[Any] = []
        if namespace is not None:
            query += " AND namespace = ?"
            params.append(namespace)
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        if cursor is not None:
            query += " AND (updated_at < ? OR (updated_at = ? AND doc_id > ?))"
            params.extend([cursor[0], cursor[0], cursor[1]])
        query += " ORDER BY updated_at DESC, doc_id ASC LIMIT ?"
        params.append(limit)
        with connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        out = []
        for row in rows:
            data = dict(row)
            data["tags"] = json.loads(data.pop("tags_json") or "[]")
            out.append(data)
        return out

    def soft_delete(self, namespace: str, doc_id: str) -> bool:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE documents SET deleted_at = ?, updated_at = ? WHERE namespace = ? AND doc_id = ? AND deleted_at IS NULL",
                (_now_iso(), _now_iso(), namespace, doc_id),
            )
        return cur.rowcount > 0

    def hard_delete(self, namespace: str, doc_id: str) -> bool:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM documents WHERE namespace = ? AND doc_id = ?",
                (namespace, doc_id),
            )
        return cur.rowcount > 0
