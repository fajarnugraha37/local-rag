from __future__ import annotations

from app.cli.idempotency import (
    build_idempotency_key,
    build_signature,
    execute_with_idempotency,
)
from app.repositories.sqlite.db import init_db
from app.repositories.sqlite.idempotency_repo import IdempotencyRepository


def test_build_idempotency_key_is_deterministic() -> None:
    payload = {"namespace": "default", "source": "folder", "path": "."}
    key1 = build_idempotency_key(operation="ingest-folder", payload=payload)
    key2 = build_idempotency_key(operation="ingest-folder", payload=dict(payload))
    assert key1 == key2
    assert key1.startswith("ingest-folder:")


def test_execute_with_idempotency_replays_previous_response(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(str(db_path))
    repo = IdempotencyRepository(str(db_path))

    payload = {"namespace": "default", "source": "folder", "path": "."}
    signature = build_signature(payload)
    key = build_idempotency_key(operation="ingest-folder", payload=payload)

    calls = {"count": 0}

    def _execute():
        calls["count"] += 1
        return {"ok": True, "ingestion_id": "job-123"}

    first, first_replayed = execute_with_idempotency(
        repo=repo,
        key=key,
        method="POST",
        path="/v1/ingestions",
        signature=signature,
        ttl_seconds=3600,
        fn=_execute,
    )
    second, second_replayed = execute_with_idempotency(
        repo=repo,
        key=key,
        method="POST",
        path="/v1/ingestions",
        signature=signature,
        ttl_seconds=3600,
        fn=_execute,
    )

    assert calls["count"] == 1
    assert first_replayed is False
    assert second_replayed is True
    assert first == second

