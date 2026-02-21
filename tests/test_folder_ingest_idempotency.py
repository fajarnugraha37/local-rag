from __future__ import annotations

import json
from pathlib import Path

from app.ingestion.folder_ingest_service import FolderIngestOptions, ingest_folder


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_folder_ingest_skips_unchanged_files(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write(root / "doc1.txt", "alpha")
    _write(root / "doc2.md", "beta")
    state_path = tmp_path / "state.json"

    calls = {"count": 0}

    def fake_ingest_single_path(path, **kwargs):
        calls["count"] += 1
        return {"path": path, "status": "ok", "chunks_count": 1}

    monkeypatch.setattr(
        "app.ingestion.folder_ingest_service.ingest_single_path", fake_ingest_single_path
    )

    first = ingest_folder(FolderIngestOptions(path=str(root), state_path=str(state_path)))
    assert first["ingested"] == 2
    assert first["skipped"] == 0
    assert calls["count"] == 2
    assert state_path.exists()

    second = ingest_folder(FolderIngestOptions(path=str(root), state_path=str(state_path)))
    assert second["ingested"] == 0
    assert second["skipped"] == 2
    assert calls["count"] == 2
    assert all(item["reason"] == "unchanged_stat" for item in second["files"])

    forced = ingest_folder(
        FolderIngestOptions(path=str(root), state_path=str(state_path), force=True)
    )
    assert forced["ingested"] == 2
    assert forced["skipped"] == 0
    assert calls["count"] == 4


def test_folder_ingest_dry_run_has_no_writes(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write(root / "doc1.txt", "alpha")
    state_path = tmp_path / "state.json"

    calls = {"count": 0}

    def fake_ingest_single_path(path, **kwargs):
        calls["count"] += 1
        return {"path": path, "status": "ok", "chunks_count": 1}

    monkeypatch.setattr(
        "app.ingestion.folder_ingest_service.ingest_single_path", fake_ingest_single_path
    )

    result = ingest_folder(
        FolderIngestOptions(path=str(root), state_path=str(state_path), dry_run=True)
    )
    assert result["dry_run"] is True
    assert result["ingested"] == 1
    assert result["skipped"] == 0
    assert calls["count"] == 0
    assert result["files"][0]["status"] == "planned"
    assert not state_path.exists()

    # Ensure a real run writes state with expected keys.
    real = ingest_folder(FolderIngestOptions(path=str(root), state_path=str(state_path)))
    assert real["ingested"] == 1
    assert state_path.exists()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert len(payload) == 1
    record = next(iter(payload.values()))
    assert "size_bytes" in record
    assert "mtime_ns" in record
    assert "content_hash" in record
    assert "last_ingested_at" in record


def test_folder_ingest_skips_too_large_file(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write(root / "large.txt", "x" * 16)
    state_path = tmp_path / "state.json"

    calls = {"count": 0}

    def fake_ingest_single_path(path, **kwargs):
        calls["count"] += 1
        return {"path": path, "status": "ok", "chunks_count": 1}

    monkeypatch.setattr(
        "app.ingestion.folder_ingest_service.ingest_single_path", fake_ingest_single_path
    )

    result = ingest_folder(
        FolderIngestOptions(
            path=str(root),
            state_path=str(state_path),
            ingest_options=type("Opt", (), {"max_bytes": 4})(),
        )
    )
    assert result["ingested"] == 0
    assert result["skipped"] == 1
    assert calls["count"] == 0
    assert "file_too_large" in result["files"][0]["reason"]


def test_folder_ingest_skips_unreadable_file(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _write(root / "doc.txt", "alpha")
    state_path = tmp_path / "state.json"

    calls = {"count": 0}

    def fake_ingest_single_path(path, **kwargs):
        calls["count"] += 1
        return {"path": path, "status": "ok", "chunks_count": 1}

    monkeypatch.setattr(
        "app.ingestion.folder_ingest_service.ingest_single_path", fake_ingest_single_path
    )
    monkeypatch.setattr("app.ingestion.folder_ingest_service._is_file_readable", lambda path: False)

    result = ingest_folder(FolderIngestOptions(path=str(root), state_path=str(state_path)))
    assert result["ingested"] == 0
    assert result["skipped"] == 1
    assert calls["count"] == 0
    assert result["files"][0]["reason"] == "unreadable_file"
