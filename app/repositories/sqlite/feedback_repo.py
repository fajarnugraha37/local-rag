from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.sqlite.db import connect


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FeedbackRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def create(
        self,
        feedback_id: str,
        run_id: str | None,
        thumb: str | None,
        note: str | None,
        citation_id: str | None,
    ) -> dict:
        created_at = _now_iso()
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO feedback(feedback_id, run_id, thumb, note, citation_id, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (feedback_id, run_id, thumb, note, citation_id, created_at),
            )
        return self.get(feedback_id) or {}

    def get(self, feedback_id: str) -> dict | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM feedback WHERE feedback_id = ?",
                (feedback_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_by_run(self, run_id: str) -> list[dict]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM feedback WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]
