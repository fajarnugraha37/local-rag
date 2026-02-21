from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.repositories.sqlite.db import connect


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NamespacesRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def create(self, namespace: str, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        created_at = _now_iso()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO namespaces(namespace, created_at, deleted_at, defaults_json)
                VALUES(?, ?, NULL, ?)
                """,
                (namespace, created_at, json.dumps(defaults or {}, sort_keys=True)),
            )
        return self.get(namespace, include_deleted=True) or {}

    def get(self, namespace: str, include_deleted: bool = False) -> dict[str, Any] | None:
        query = "SELECT * FROM namespaces WHERE namespace = ?"
        params: list[Any] = [namespace]
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        with connect(self.db_path) as conn:
            row = conn.execute(query, params).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["defaults"] = json.loads(data.pop("defaults_json") or "{}")
        return data

    def list(self, include_deleted: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM namespaces"
        if not include_deleted:
            query += " WHERE deleted_at IS NULL"
        query += " ORDER BY namespace"
        with connect(self.db_path) as conn:
            rows = conn.execute(query).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["defaults"] = json.loads(data.pop("defaults_json") or "{}")
            out.append(data)
        return out

    def soft_delete(self, namespace: str) -> bool:
        deleted_at = _now_iso()
        with connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE namespaces SET deleted_at = ? WHERE namespace = ? AND deleted_at IS NULL",
                (deleted_at, namespace),
            )
        return cur.rowcount > 0

    def restore(self, namespace: str) -> bool:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE namespaces SET deleted_at = NULL WHERE namespace = ?",
                (namespace,),
            )
        return cur.rowcount > 0
