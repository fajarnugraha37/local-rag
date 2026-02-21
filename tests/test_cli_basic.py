from __future__ import annotations

import json
from types import SimpleNamespace

from app.repositories.sqlite.db import init_db
from app.repositories.sqlite.idempotency_repo import IdempotencyRepository
from cmd.cli.entrypoint import run_cli


def test_cli_help_shows_core_commands(capsys):
    code = run_cli(["--help"])
    out = capsys.readouterr().out
    assert code == 0
    assert "query" in out
    assert "ingest" in out
    assert "doc" in out
    assert "ns" in out
    assert "run" in out


def test_ingest_start_idempotency_replays_with_same_key(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "app.db"
    init_db(str(db_path))
    idempotency_repo = IdempotencyRepository(str(db_path))

    calls = {"count": 0}

    class _StubIngestionService:
        def create_job(self, namespace, source_type, source_spec, upload_payload=None):
            calls["count"] += 1
            return {
                "ingestion_id": "ing-job-1",
                "namespace": namespace,
                "source_type": source_type,
                "source_spec": source_spec,
                "status": "queued",
            }

    stub_services = SimpleNamespace(
        ingestion_service=_StubIngestionService(),
        idempotency_repo=idempotency_repo,
        config={"idempotency_ttl_s": 3600},
    )
    monkeypatch.setattr(
        "app.cli.commands.ingestions.build_services",
        lambda: stub_services,
    )

    args = [
        "ingest",
        "start",
        "--source",
        "folder",
        "--path",
        ".",
        "--idempotency-key",
        "idem-1",
        "--json",
    ]
    code1 = run_cli(args)
    out1 = capsys.readouterr().out
    payload1 = json.loads(out1)
    assert code1 == 0
    assert payload1["ok"] is True
    assert payload1["idempotency_replayed"] is False

    code2 = run_cli(args)
    out2 = capsys.readouterr().out
    payload2 = json.loads(out2)
    assert code2 == 0
    assert payload2["ok"] is True
    assert payload2["idempotency_replayed"] is True
    assert calls["count"] == 1

