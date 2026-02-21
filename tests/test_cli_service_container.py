from __future__ import annotations

import sqlite3

from app.cli.adapters.service_container import build_services


def test_build_services_initializes_sqlite_schema(tmp_path):
    db_path = tmp_path / "fresh.db"
    services = build_services(config={"sqlite_db_path": str(db_path)})
    assert services.db_path == str(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ingestions'"
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
