from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.repositories.sqlite.db import connect


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestionsRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def create(
        self,
        ingestion_id: str,
        namespace: str,
        source_type: str,
        source_spec: dict[str, Any] | None = None,
        status: str = "queued",
    ) -> dict[str, Any]:
        created_at = _now_iso()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO ingestions(
                    ingestion_id, namespace, source_type, source_spec_json, status, created_at,
                    started_at, finished_at, counters_json, last_error, cancel_requested
                ) VALUES(?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL, 0)
                """,
                (
                    ingestion_id,
                    namespace,
                    source_type,
                    json.dumps(source_spec or {}, sort_keys=True),
                    status,
                    created_at,
                    json.dumps({}, sort_keys=True),
                ),
            )
        return self.get(ingestion_id) or {}

    def get(self, ingestion_id: str) -> dict[str, Any] | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM ingestions WHERE ingestion_id = ?",
                (ingestion_id,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["source_spec"] = json.loads(data.pop("source_spec_json") or "{}")
        data["counters"] = json.loads(data.pop("counters_json") or "{}")
        data["cancel_requested"] = bool(data["cancel_requested"])
        return data

    def list(self, namespace: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = "SELECT * FROM ingestions"
        params: list[Any] = []
        if namespace is not None:
            query += " WHERE namespace = ?"
            params.append(namespace)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["source_spec"] = json.loads(data.pop("source_spec_json") or "{}")
            data["counters"] = json.loads(data.pop("counters_json") or "{}")
            data["cancel_requested"] = bool(data["cancel_requested"])
            out.append(data)
        return out

    def update_status(
        self,
        ingestion_id: str,
        status: str,
        counters: dict[str, Any] | None = None,
        last_error: str | None = None,
    ) -> bool:
        now = _now_iso()
        started_at = now if status == "running" else None
        finished_at = now if status in {"done", "failed", "cancelled"} else None
        with connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE ingestions
                SET status = ?,
                    started_at = COALESCE(?, started_at),
                    finished_at = COALESCE(?, finished_at),
                    counters_json = COALESCE(?, counters_json),
                    last_error = COALESCE(?, last_error)
                WHERE ingestion_id = ?
                """,
                (
                    status,
                    started_at,
                    finished_at,
                    json.dumps(counters, sort_keys=True) if counters is not None else None,
                    last_error,
                    ingestion_id,
                ),
            )
        return cur.rowcount > 0

    def request_cancel(self, ingestion_id: str) -> bool:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE ingestions SET cancel_requested = 1 WHERE ingestion_id = ?",
                (ingestion_id,),
            )
        return cur.rowcount > 0

    def add_event(self, ingestion_id: str, event: str, payload: dict[str, Any] | None = None) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO ingestion_events(ingestion_id, ts, event, payload_json) VALUES(?, ?, ?, ?)",
                (ingestion_id, _now_iso(), event, json.dumps(payload or {}, sort_keys=True)),
            )

    def list_events(self, ingestion_id: str, limit: int = 500) -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT ingestion_id, ts, event, payload_json FROM ingestion_events WHERE ingestion_id = ? ORDER BY id ASC LIMIT ?",
                (ingestion_id, limit),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["payload"] = json.loads(data.pop("payload_json") or "{}")
            out.append(data)
        return out
