import time

from fastapi.testclient import TestClient

from app.config import runtime_settings as settings
from app.http.fastapi_app import create_app


def _wait_status(client: TestClient, ingestion_id: str, timeout_s: float = 5.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/v1/ingestions/{ingestion_id}")
        payload = resp.json()
        if payload.get("ok") and payload["record"]["status"] in {"done", "failed", "cancelled"}:
            return payload["record"]
        time.sleep(0.05)
    raise AssertionError("ingestion job did not finish in time")


def test_fastapi_ingestions_folder_job_and_events(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setitem(settings.CONFIG, "sqlite_db_path", str(db_path))

    root = tmp_path / "docs"
    root.mkdir()
    (root / "a.txt").write_text("hello", encoding="utf-8")

    with TestClient(create_app()) as client:
        create = client.post(
            "/v1/ingestions",
            json={
                "namespace": "default",
                "source_type": "folder",
                "source_spec": {"path": str(root), "dry_run": True},
            },
        )
        assert create.status_code == 200
        body = create.json()
        assert body["ok"] is True
        ingestion_id = body["ingestion_id"]

        record = _wait_status(client, ingestion_id)
        assert record["status"] == "done"

        events = client.get(f"/v1/ingestions/{ingestion_id}/events").json()
        assert events["ok"] is True
        names = [e["event"] for e in events["events"]]
        assert "queued" in names
        assert "running" in names
        assert "done" in names


def test_fastapi_ingestions_upload_and_cancel(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setitem(settings.CONFIG, "sqlite_db_path", str(db_path))

    from app.services import ingestion_service as svc_mod

    def fake_upload(uploaded, options=None, embedding_model=None, namespace=None):
        return {
            "total_files": len(uploaded),
            "extracted": len(uploaded),
            "skipped": 0,
            "failed": 0,
            "total_chunks": 1,
        }

    def slow_folder(options):
        time.sleep(0.5)
        return {
            "path": options.path,
            "ingested": 1,
            "skipped": 0,
            "failed": 0,
        }

    monkeypatch.setattr(svc_mod, "ingest_uploaded_files", fake_upload)
    monkeypatch.setattr(svc_mod, "ingest_folder", slow_folder)

    root = tmp_path / "docs2"
    root.mkdir()
    (root / "b.txt").write_text("world", encoding="utf-8")

    with TestClient(create_app()) as client:
        upload = client.post(
            "/v1/ingestions/upload",
            files=[("file", ("u.txt", b"hello upload", "text/plain"))],
            data={"namespace": "default"},
        )
        assert upload.status_code == 200
        up_body = upload.json()
        assert up_body["ok"] is True
        up_id = up_body["ingestion_id"]
        up_record = _wait_status(client, up_id)
        assert up_record["status"] == "done"

        create = client.post(
            "/v1/ingestions",
            json={
                "namespace": "default",
                "source_type": "folder",
                "source_spec": {"path": str(root), "dry_run": True},
            },
        )
        ing_id = create.json()["ingestion_id"]

        cancel = client.post(f"/v1/ingestions/{ing_id}/cancel")
        assert cancel.status_code == 200
        assert cancel.json()["ok"] is True
        assert cancel.json()["cancel_requested"] is True

        rec = _wait_status(client, ing_id)
        assert rec["status"] == "cancelled"


def test_fastapi_ingestions_folder_tuning_knobs_forwarded(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setitem(settings.CONFIG, "sqlite_db_path", str(db_path))

    from app.services import ingestion_service as svc_mod

    seen = {}

    def capture_folder(options):
        seen["parallel_workers"] = options.parallel_workers
        seen["chunk_max_tokens"] = options.ingest_options.chunk_max_tokens
        seen["chunk_overlap_tokens"] = options.ingest_options.chunk_overlap_tokens
        seen["ocr_enabled"] = options.ingest_options.ocr_enabled
        return {"path": options.path, "ingested": 0, "skipped": 0, "failed": 0, "files": []}

    monkeypatch.setattr(svc_mod, "ingest_folder", capture_folder)

    root = tmp_path / "docs3"
    root.mkdir()
    (root / "a.txt").write_text("hello", encoding="utf-8")

    with TestClient(create_app()) as client:
        create = client.post(
            "/v1/ingestions",
            json={
                "namespace": "default",
                "source_type": "folder",
                "source_spec": {
                    "path": str(root),
                    "dry_run": True,
                    "parallel_workers": 3,
                    "chunk_max_tokens": 720,
                    "chunk_overlap_tokens": 72,
                    "ocr_enabled": True,
                },
            },
        )
        assert create.status_code == 200
        ing_id = create.json()["ingestion_id"]
        rec = _wait_status(client, ing_id)
        assert rec["status"] == "done"

    assert seen["parallel_workers"] == 3
    assert seen["chunk_max_tokens"] == 720
    assert seen["chunk_overlap_tokens"] == 72
    assert seen["ocr_enabled"] is True
