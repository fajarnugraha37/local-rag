from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.sqlite.db import connect


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IdempotencyRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def upsert_pending(
        self,
        key: str,
        method: str,
        path: str,
        signature: str,
        expires_at: str | None = None,
    ) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO idempotency(
                    key, method, path, signature, status, response_body, created_at, expires_at
                ) VALUES(?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (key, method, path, signature, _now_iso(), expires_at),
            )

    def set_response(
        self, key: str, method: str, path: str, status: int, response_body: str
    ) -> bool:
        with connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE idempotency SET status = ?, response_body = ? WHERE key = ? AND method = ? AND path = ?",
                (status, response_body, key, method, path),
            )
        return cur.rowcount > 0

    def get(self, key: str, method: str, path: str) -> dict | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM idempotency WHERE key = ? AND method = ? AND path = ?",
                (key, method, path),
            ).fetchone()
        return dict(row) if row is not None else None

    def is_expired(self, row: dict | None, now_iso: str | None = None) -> bool:
        if not row:
            return True
        expires_at = row.get("expires_at")
        if not expires_at:
            return False
        now_iso = now_iso or _now_iso()
        return str(expires_at) <= str(now_iso)

    def delete_expired(self, now_iso: str | None = None) -> int:
        now_iso = now_iso or _now_iso()
        with connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM idempotency WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now_iso,),
            )
        return cur.rowcount
