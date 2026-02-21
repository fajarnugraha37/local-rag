from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cmd.cli.entrypoint import run_cli


def test_doc_list_outputs_next_cursor_in_table_mode(monkeypatch, capsys):
    payload = {
        "records": [
            {
                "namespace": "default",
                "doc_id": "doc-1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "deleted_at": None,
            }
        ],
        "count": 1,
        "next_cursor": "cursor-abc",
    }
    stub_services = SimpleNamespace(
        document_service=SimpleNamespace(list_documents=lambda **kwargs: payload)
    )
    monkeypatch.setattr("app.cli.commands.documents.build_services", lambda: stub_services)

    code = run_cli(["doc", "list", "--limit", "5"])
    out = capsys.readouterr().out
    assert code == 0
    assert "doc-1" in out
    assert "next_cursor=cursor-abc" in out


def test_doc_list_json_mode_returns_cursor_and_count(monkeypatch, capsys):
    payload = {
        "records": [],
        "count": 0,
        "next_cursor": "cursor-json",
    }
    stub_services = SimpleNamespace(
        document_service=SimpleNamespace(list_documents=lambda **kwargs: payload)
    )
    monkeypatch.setattr("app.cli.commands.documents.build_services", lambda: stub_services)

    code = run_cli(["doc", "list", "--limit", "5", "--json"])
    out = capsys.readouterr().out
    body = json.loads(out)
    assert code == 0
    assert body["ok"] is True
    assert body["count"] == 0
    assert body["next_cursor"] == "cursor-json"


def test_doc_list_invalid_cursor_returns_error_code(capsys):
    code = run_cli(["doc", "list", "--cursor", "!!invalid-base64!!"])
    captured = capsys.readouterr()
    out = captured.err + captured.out
    assert code == 2
    assert "cursor" in out.lower()
