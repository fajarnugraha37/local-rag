from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.repositories.sqlite.db import connect


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunsRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def create(
        self,
        run_id: str,
        status: str,
        trace_id: str | None = None,
        query: str | None = None,
        mode: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _now_iso()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs(
                    run_id, trace_id, query, mode, inputs_json, answer, citations_json,
                    status, created_at, updated_at, timings_json, error
                ) VALUES(?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    run_id,
                    trace_id,
                    query,
                    mode,
                    json.dumps(inputs or {}, sort_keys=True),
                    json.dumps([], sort_keys=True),
                    status,
                    now,
                    now,
                    json.dumps({}, sort_keys=True),
                ),
            )
        return self.get(run_id) or {}

    def get(self, run_id: str) -> dict[str, Any] | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["inputs"] = json.loads(data.pop("inputs_json") or "{}")
        data["citations"] = json.loads(data.pop("citations_json") or "[]")
        data["timings"] = json.loads(data.pop("timings_json") or "{}")
        return data

    def update_result(
        self,
        run_id: str,
        status: str,
        answer: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        timings: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> bool:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE runs
                SET status = ?, answer = COALESCE(?, answer), citations_json = COALESCE(?, citations_json),
                    timings_json = COALESCE(?, timings_json), error = COALESCE(?, error), updated_at = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    answer,
                    json.dumps(citations, sort_keys=True) if citations is not None else None,
                    json.dumps(timings, sort_keys=True) if timings is not None else None,
                    error,
                    _now_iso(),
                    run_id,
                ),
            )
        return cur.rowcount > 0

    def add_step(
        self,
        run_id: str,
        step_index: int,
        summary: str,
        tool: str | None = None,
        scores: dict[str, Any] | None = None,
        doc_ids: list[str] | None = None,
    ) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO run_steps(run_id, step_index, summary, tool, scores_json, doc_ids_json, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    step_index,
                    summary,
                    tool,
                    json.dumps(scores or {}, sort_keys=True),
                    json.dumps(doc_ids or [], sort_keys=True),
                    _now_iso(),
                ),
            )

    def list_steps(self, run_id: str) -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT run_id, step_index, summary, tool, scores_json, doc_ids_json, created_at FROM run_steps WHERE run_id = ? ORDER BY step_index ASC",
                (run_id,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["scores"] = json.loads(data.pop("scores_json") or "{}")
            data["doc_ids"] = json.loads(data.pop("doc_ids_json") or "[]")
            out.append(data)
        return out

    def add_event(self, run_id: str, event: str, payload: dict[str, Any] | None = None) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO run_events(run_id, ts, event, payload_json) VALUES(?, ?, ?, ?)",
                (run_id, _now_iso(), event, json.dumps(payload or {}, sort_keys=True)),
            )

    def list_events(self, run_id: str, limit: int = 1000) -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT run_id, ts, event, payload_json FROM run_events WHERE run_id = ? ORDER BY id ASC LIMIT ?",
                (run_id, limit),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["payload"] = json.loads(data.pop("payload_json") or "{}")
            out.append(data)
        return out
