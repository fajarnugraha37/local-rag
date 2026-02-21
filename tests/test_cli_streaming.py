from __future__ import annotations

import json
from types import SimpleNamespace

from cmd.cli.entrypoint import run_cli


def test_query_stream_prints_expected_event_sequence(monkeypatch, capsys):
    stub_result = {
        "run_id": "run-1",
        "trace_id": "trace-1",
        "answer": "final answer",
        "sources": [{"citation_index": 1, "title": "Doc A"}],
        "citation_stats": {"is_valid": True, "valid_ids": [1], "used_valid_ids": [1]},
    }
    stub_services = SimpleNamespace(
        query_service=SimpleNamespace(run_query=lambda **kwargs: dict(stub_result))
    )
    monkeypatch.setattr("app.cli.commands.query.build_services", lambda: stub_services)

    code = run_cli(["query-stream", "hello"])
    out = capsys.readouterr().out
    assert code == 0
    assert "meta" in out
    assert "final_delta" in out
    assert "sources" in out
    assert "done" in out
    assert "run-1" in out


def test_query_stream_json_mode_returns_events(monkeypatch, capsys):
    stub_result = {
        "run_id": "run-j",
        "trace_id": "trace-j",
        "answer": "answer-j",
        "sources": [],
        "citation_stats": {"is_valid": True},
    }
    stub_services = SimpleNamespace(
        query_service=SimpleNamespace(run_query=lambda **kwargs: dict(stub_result))
    )
    monkeypatch.setattr("app.cli.commands.query.build_services", lambda: stub_services)

    code = run_cli(["query-stream", "hello", "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["count"] == 5
    names = [row["event"] for row in payload["events"]]
    assert names == ["meta", "final_delta", "sources", "citation_stats", "done"]

