"""SQLite persistence layer for API server state."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS namespaces (
        namespace TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        deleted_at TEXT,
        defaults_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        namespace TEXT NOT NULL,
        doc_id TEXT NOT NULL,
        source_path TEXT,
        source_type TEXT,
        title TEXT,
        content_hash TEXT,
        chunk_count INTEGER,
        size_bytes INTEGER,
        tags_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_ingested_at TEXT,
        deleted_at TEXT,
        repo TEXT,
        "commit" TEXT,
        PRIMARY KEY (namespace, doc_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_documents_updated_doc_id
    ON documents(updated_at, doc_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestions (
        ingestion_id TEXT PRIMARY KEY,
        namespace TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_spec_json TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        counters_json TEXT,
        last_error TEXT,
        cancel_requested INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ingestion_id TEXT NOT NULL,
        ts TEXT NOT NULL,
        event TEXT NOT NULL,
        payload_json TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ingestion_events_ingestion_id_ts
    ON ingestion_events(ingestion_id, ts)
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        trace_id TEXT,
        query TEXT,
        mode TEXT,
        inputs_json TEXT,
        answer TEXT,
        citations_json TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        timings_json TEXT,
        error TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS run_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        step_index INTEGER NOT NULL,
        summary TEXT,
        tool TEXT,
        scores_json TEXT,
        doc_ids_json TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_run_steps_run_step
    ON run_steps(run_id, step_index)
    """,
    """
    CREATE TABLE IF NOT EXISTS run_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        ts TEXT NOT NULL,
        event TEXT NOT NULL,
        payload_json TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_run_events_run_id_ts
    ON run_events(run_id, ts)
    """,
    """
    CREATE TABLE IF NOT EXISTS idempotency (
        key TEXT NOT NULL,
        method TEXT NOT NULL,
        path TEXT NOT NULL,
        signature TEXT NOT NULL,
        status INTEGER,
        response_body TEXT,
        created_at TEXT NOT NULL,
        expires_at TEXT,
        PRIMARY KEY (key, method, path)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_idempotency_expires_at
    ON idempotency(expires_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS feedback (
        feedback_id TEXT PRIMARY KEY,
        run_id TEXT,
        thumb TEXT,
        note TEXT,
        citation_id TEXT,
        created_at TEXT NOT NULL
    )
    """,
]


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def connect(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        for stmt in DDL_STATEMENTS:
            conn.execute(stmt)
