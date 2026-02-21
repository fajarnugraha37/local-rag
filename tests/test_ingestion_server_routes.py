import json

from fastapi.testclient import TestClient

from app.config import runtime_settings as settings
from app.http.fastapi_app import create_app
from app.ingestion.doc_registry_store import DocRegistryStore


def test_ingest_files_endpoint(monkeypatch):
    from app.http.routers import legacy

    monkeypatch.setattr(
        legacy,
        "ingest_paths",
        lambda paths, options=None, embedding_model=None, namespace=None: {
            "total_files": len(paths),
            "extracted": len(paths),
            "skipped": 0,
            "failed": 0,
            "total_chunks": 2,
            "files": [],
        },
    )

    with TestClient(create_app()) as client:
        resp = client.post("/ingest/files", json={"paths": ["README.md"], "recursive": False})
        body = resp.json()
        assert resp.status_code == 200
        assert body["ok"] is True
        assert body["summary"]["total_files"] == 1


def test_ingest_upload_endpoint(monkeypatch):
    from app.http.routers import legacy

    monkeypatch.setattr(
        legacy,
        "ingest_uploaded_files",
        lambda uploaded, options=None, embedding_model=None, namespace=None: {
            "total_files": len(uploaded),
            "extracted": len(uploaded),
            "skipped": 0,
            "failed": 0,
            "total_chunks": 1,
            "files": [],
        },
    )

    with TestClient(create_app()) as client:
        resp = client.post(
            "/ingest/upload",
            files=[("file", ("sample.txt", b"hello upload", "text/plain"))],
        )
        payload = resp.json()
        assert resp.status_code == 200
        assert payload["ok"] is True
        assert payload["summary"]["total_files"] == 1


def test_ingest_endpoints_namespace_accept_and_invalid(monkeypatch):
    from app.http.routers import legacy

    captured = {"chunks": None, "files": None, "upload": None, "folder": None}

    def fake_ingest_chunks(
        chunks, source_path=None, doc_id=None, namespace=None, embedding_model=None
    ):
        captured["chunks"] = namespace
        return {"added": len(chunks), "skipped": 0, "failed": 0}

    def fake_ingest_paths(paths, options=None, embedding_model=None, namespace=None):
        captured["files"] = namespace
        return {
            "total_files": len(paths),
            "extracted": len(paths),
            "skipped": 0,
            "failed": 0,
            "total_chunks": 1,
            "files": [],
        }

    def fake_ingest_uploaded(uploaded, options=None, embedding_model=None, namespace=None):
        captured["upload"] = namespace
        return {
            "total_files": len(uploaded),
            "extracted": len(uploaded),
            "skipped": 0,
            "failed": 0,
            "total_chunks": 1,
            "files": [],
        }

    def fake_ingest_folder(options):
        captured["folder"] = options.namespace
        return {
            "path": options.path,
            "dry_run": bool(options.dry_run),
            "force": bool(options.force),
            "scanned": 1,
            "selected": 1,
            "scan_skipped": 0,
            "ingested": 1,
            "skipped": 0,
            "failed": 0,
            "files": [{"path": "README.md", "status": "ok"}],
        }

    monkeypatch.setattr(legacy, "ingest_chunks", fake_ingest_chunks)
    monkeypatch.setattr(legacy, "ingest_paths", fake_ingest_paths)
    monkeypatch.setattr(legacy, "ingest_uploaded_files", fake_ingest_uploaded)
    monkeypatch.setattr(legacy, "ingest_folder", fake_ingest_folder)

    with TestClient(create_app()) as client:
        assert (
            client.post("/ingest/chunks", json={"chunks": ["a"], "namespace": "alpha"}).status_code
            == 200
        )
        assert captured["chunks"] == "alpha"

        assert (
            client.post(
                "/ingest/files", json={"paths": ["README.md"], "namespace": "beta"}
            ).status_code
            == 200
        )
        assert captured["files"] == "beta"

        assert (
            client.post("/ingest/folder", json={"path": ".", "namespace": "gamma"}).status_code
            == 200
        )
        assert captured["folder"] == "gamma"

        assert (
            client.post(
                "/ingest/upload",
                files=[("file", ("sample.txt", b"hello upload", "text/plain"))],
                data={"namespace": "delta"},
            ).status_code
            == 200
        )
        assert captured["upload"] == "delta"

        resp = client.post("/ingest/text", json={"text": "hello", "namespace": "Invalid Namespace"})
        assert resp.status_code == 400
        assert resp.json()["ok"] is False


def test_ingest_folder_endpoint_json(monkeypatch):
    from app.http.routers import legacy

    monkeypatch.setattr(
        legacy,
        "ingest_folder",
        lambda options: {
            "path": options.path,
            "dry_run": bool(options.dry_run),
            "force": bool(options.force),
            "scanned": 3,
            "selected": 2,
            "scan_skipped": 1,
            "ingested": 2,
            "skipped": 0,
            "failed": 0,
            "files": [{"path": "README.md", "status": "ok"}],
        },
    )

    with TestClient(create_app()) as client:
        resp = client.post("/ingest/folder", json={"path": ".", "dry_run": True})
        body = resp.json()
        assert resp.status_code == 200
        assert body["ok"] is True
        assert isinstance(body["request_id"], str)
        assert body["summary"]["selected"] == 2


def test_ingest_folder_endpoint_streaming(monkeypatch):
    from app.http.routers import legacy

    def fake_ingest_folder(options):
        if options.progress_callback:
            options.progress_callback("scan_started", {"path": options.path})
            options.progress_callback("file_found", {"path": "README.md"})
            options.progress_callback("file_selected", {"path": "README.md"})
            options.progress_callback("file_ingested", {"path": "README.md"})
            options.progress_callback("scan_done", {"scanned": 1, "selected": 1, "scan_skipped": 0})
        return {
            "path": options.path,
            "dry_run": bool(options.dry_run),
            "force": bool(options.force),
            "scanned": 1,
            "selected": 1,
            "scan_skipped": 0,
            "ingested": 1,
            "skipped": 0,
            "failed": 0,
            "files": [{"path": "README.md", "status": "ok"}],
        }

    monkeypatch.setattr(legacy, "ingest_folder", fake_ingest_folder)

    with TestClient(create_app()) as client:
        resp = client.post(
            "/ingest/folder", json={"path": ".", "stream": True, "request_id": "req-123"}
        )
        text = resp.text
        assert resp.status_code == 200
        assert "event: scan_started" in text
        assert "event: file_found" in text
        assert "event: file_selected" in text
        assert "event: file_ingested" in text
        assert "event: scan_done" in text
        assert '"request_id": "req-123"' in text


def test_ingest_folder_rejects_unsafe_root(monkeypatch):
    with TestClient(create_app()) as client:
        resp = client.post("/ingest/folder", json={"path": "/"})
        body = resp.json()
        assert resp.status_code == 400
        assert body["ok"] is False
        assert "not allowed" in body["error"]


def test_ingest_folder_rejects_outside_allowed_roots(monkeypatch, tmp_path):
    monkeypatch.setitem(settings.CONFIG, "ingest_allowed_roots", [str(tmp_path / "allowed")])
    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)

    with TestClient(create_app()) as client:
        resp = client.post("/ingest/folder", json={"path": str(outside)})
        body = resp.json()
        assert resp.status_code == 400
        assert body["ok"] is False
        assert "outside configured allowed roots" in body["error"]


def test_docs_list_endpoint_global_and_scoped(monkeypatch, tmp_path):
    monkeypatch.setitem(settings.CONFIG, "doc_registry_path", str(tmp_path / "doc_registry.json"))
    store = DocRegistryStore(str(tmp_path / "doc_registry.json"))
    store.upsert(namespace="alpha", doc_id="doc-a", source_path="/tmp/a.txt", chunk_count=2)
    store.upsert(namespace="beta", doc_id="doc-b", source_path="/tmp/b.txt", chunk_count=1)
    store.save()

    with TestClient(create_app()) as client:
        resp = client.get("/docs?limit=10")
        payload = resp.json()
        assert resp.status_code == 200
        assert payload["ok"] is True
        ids = {(row["namespace"], row["doc_id"]) for row in payload["records"]}
        assert ("alpha", "doc-a") in ids
        assert ("beta", "doc-b") in ids

        resp2 = client.get("/docs?namespace=alpha&limit=10")
        payload2 = resp2.json()
        assert resp2.status_code == 200
        assert payload2["ok"] is True
        assert all(row["namespace"] == "alpha" for row in payload2["records"])


def test_docs_delete_endpoint_namespace_and_all(monkeypatch, tmp_path):
    from app.http.routers import legacy

    monkeypatch.setitem(settings.CONFIG, "doc_registry_path", str(tmp_path / "doc_registry.json"))
    store = DocRegistryStore(str(tmp_path / "doc_registry.json"))
    store.upsert(namespace="alpha", doc_id="doc-x", source_path="/tmp/a.txt", chunk_count=2)
    store.upsert(namespace="default", doc_id="doc-x", source_path="/tmp/d.txt", chunk_count=1)
    store.save()

    def fake_delete(doc_id, namespace=None, all_namespaces=False):
        if doc_id != "doc-x":
            return 0
        if all_namespaces:
            return 2
        if namespace in {"alpha", "default"}:
            return 1
        return 0

    monkeypatch.setattr(legacy, "delete_doc", fake_delete)

    with TestClient(create_app()) as client:
        resp = client.delete("/docs/doc-x?namespace=alpha")
        payload = resp.json()
        assert resp.status_code == 200
        assert payload["ok"] is True
        assert payload["vectors_deleted"] == 1
        assert payload["registry_deleted"] == 1
        assert payload["all_namespaces"] is False

        reload_store = DocRegistryStore(str(tmp_path / "doc_registry.json"))
        assert reload_store.get("alpha", "doc-x") is None
        assert reload_store.get("default", "doc-x") is not None

        resp2 = client.delete("/docs/doc-x?all_namespaces=true")
        payload2 = resp2.json()
        assert resp2.status_code == 200
        assert payload2["ok"] is True
        assert payload2["all_namespaces"] is True
        assert payload2["registry_deleted"] >= 1

        reload_store2 = DocRegistryStore(str(tmp_path / "doc_registry.json"))
        assert reload_store2.get("default", "doc-x") is None

        resp3 = client.delete("/docs/missing-doc")
        payload3 = resp3.json()
        assert resp3.status_code == 200
        assert payload3["ok"] is True
        assert payload3["not_found"] is True


def test_retrieval_query_returns_answer_sources_and_citation_stats(monkeypatch):
    from app.http.routers import legacy

    def fake_scored_chunks(query_text, top_k=6, rerank=True, filters=None, namespaces=None):
        return [
            {
                "chunk_id": "c1",
                "text": "Payment is due in 14 days.",
                "source": {
                    "source_id": "S1",
                    "citation_index": 1,
                    "namespace": "default",
                    "doc_id": "doc-1",
                    "path": "docs/a.txt",
                    "title": "Invoice Terms",
                    "locator": "page 1",
                    "snippet": "Payment is due in 14 days.",
                },
            }
        ]

    monkeypatch.setattr(legacy.retrieval, "scored_chunks", fake_scored_chunks)

    with TestClient(create_app()) as client:
        resp = client.post(
            "/retrieval/query", json={"query": "payment terms", "top_k": 3, "rerank": True}
        )
        payload = resp.json()
        assert resp.status_code == 200
        assert payload["ok"] is True
        assert isinstance(payload["answer"], str)
        assert isinstance(payload["sources"], list)
        assert len(payload["sources"]) == 1
        assert payload["sources"][0]["citation_index"] == 1
        assert isinstance(payload["citation_stats"], dict)
