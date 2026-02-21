import http.client
import json
import os
import threading

from http.server import ThreadingHTTPServer

from app.chat import streaming_server
from app.ingestion.doc_registry_store import DocRegistryStore


def _start_server(monkeypatch):
    monkeypatch.setattr(
        streaming_server,
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
    monkeypatch.setattr(
        streaming_server,
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
    monkeypatch.setattr(
        streaming_server,
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
            "namespace": getattr(options, "namespace", None),
        },
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), streaming_server.StreamingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_ingest_files_endpoint(monkeypatch):
    server = _start_server(monkeypatch)
    host, port = server.server_address

    conn = http.client.HTTPConnection(host, port)
    payload = json.dumps({"paths": ["README.md"], "recursive": False})
    conn.request(
        "POST", "/ingest/files", body=payload, headers={"Content-Type": "application/json"}
    )
    resp = conn.getresponse()
    body = json.loads(resp.read().decode("utf-8"))

    assert resp.status == 200
    assert body["ok"] is True
    assert body["summary"]["total_files"] == 1

    conn.close()
    server.shutdown()
    server.server_close()


def test_ingest_upload_endpoint(monkeypatch):
    server = _start_server(monkeypatch)
    host, port = server.server_address

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="sample.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "hello upload\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    conn = http.client.HTTPConnection(host, port)
    conn.request(
        "POST",
        "/ingest/upload",
        body=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
    )
    resp = conn.getresponse()
    payload = json.loads(resp.read().decode("utf-8"))

    assert resp.status == 200
    assert payload["ok"] is True
    assert payload["summary"]["total_files"] == 1

    conn.close()
    server.shutdown()
    server.server_close()


def test_ingest_endpoints_namespace_accept_and_invalid(monkeypatch):
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

    monkeypatch.setattr(streaming_server, "ingest_chunks", fake_ingest_chunks)
    monkeypatch.setattr(streaming_server, "ingest_paths", fake_ingest_paths)
    monkeypatch.setattr(streaming_server, "ingest_uploaded_files", fake_ingest_uploaded)
    monkeypatch.setattr(streaming_server, "ingest_folder", fake_ingest_folder)

    server = ThreadingHTTPServer(("127.0.0.1", 0), streaming_server.StreamingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port)

    conn.request(
        "POST",
        "/ingest/chunks",
        body=json.dumps({"chunks": ["a"], "namespace": "alpha"}),
        headers={"Content-Type": "application/json"},
    )
    resp = conn.getresponse()
    assert resp.status == 200
    _ = resp.read()
    assert captured["chunks"] == "alpha"

    conn.request(
        "POST",
        "/ingest/files",
        body=json.dumps({"paths": ["README.md"], "namespace": "beta"}),
        headers={"Content-Type": "application/json"},
    )
    resp2 = conn.getresponse()
    assert resp2.status == 200
    _ = resp2.read()
    assert captured["files"] == "beta"

    conn.request(
        "POST",
        "/ingest/folder",
        body=json.dumps({"path": ".", "namespace": "gamma"}),
        headers={"Content-Type": "application/json"},
    )
    resp3 = conn.getresponse()
    assert resp3.status == 200
    _ = resp3.read()
    assert captured["folder"] == "gamma"

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="sample.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "hello upload\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="namespace"\r\n\r\n'
        "delta\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    conn.request(
        "POST",
        "/ingest/upload",
        body=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
    )
    resp4 = conn.getresponse()
    assert resp4.status == 200
    _ = resp4.read()
    assert captured["upload"] == "delta"

    conn.request(
        "POST",
        "/ingest/text",
        body=json.dumps({"text": "hello", "namespace": "Invalid Namespace"}),
        headers={"Content-Type": "application/json"},
    )
    resp5 = conn.getresponse()
    payload5 = json.loads(resp5.read().decode("utf-8"))
    assert resp5.status == 400
    assert payload5["ok"] is False

    conn.close()
    server.shutdown()
    server.server_close()


def test_ingest_folder_endpoint_json(monkeypatch):
    server = _start_server(monkeypatch)
    host, port = server.server_address

    conn = http.client.HTTPConnection(host, port)
    payload = json.dumps({"path": ".", "dry_run": True})
    conn.request(
        "POST", "/ingest/folder", body=payload, headers={"Content-Type": "application/json"}
    )
    resp = conn.getresponse()
    body = json.loads(resp.read().decode("utf-8"))

    assert resp.status == 200
    assert body["ok"] is True
    assert isinstance(body["request_id"], str)
    assert body["summary"]["selected"] == 2

    conn.close()
    server.shutdown()
    server.server_close()


def test_ingest_folder_endpoint_streaming(monkeypatch):
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

    monkeypatch.setattr(streaming_server, "ingest_folder", fake_ingest_folder)
    server = ThreadingHTTPServer(("127.0.0.1", 0), streaming_server.StreamingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port)
    payload = json.dumps({"path": ".", "stream": True, "request_id": "req-123"})
    conn.request(
        "POST", "/ingest/folder", body=payload, headers={"Content-Type": "application/json"}
    )
    resp = conn.getresponse()
    text = resp.read().decode("utf-8")

    assert resp.status == 200
    assert "event: scan_started" in text
    assert "event: file_found" in text
    assert "event: file_selected" in text
    assert "event: file_ingested" in text
    assert "event: scan_done" in text
    assert '"request_id": "req-123"' in text

    conn.close()
    server.shutdown()
    server.server_close()


def test_ingest_folder_rejects_unsafe_root(monkeypatch):
    server = _start_server(monkeypatch)
    host, port = server.server_address

    conn = http.client.HTTPConnection(host, port)
    payload = json.dumps({"path": os.path.abspath(os.sep)})
    conn.request(
        "POST", "/ingest/folder", body=payload, headers={"Content-Type": "application/json"}
    )
    resp = conn.getresponse()
    body = json.loads(resp.read().decode("utf-8"))

    assert resp.status == 400
    assert body["ok"] is False
    assert "not allowed" in body["error"]

    conn.close()
    server.shutdown()
    server.server_close()


def test_ingest_folder_rejects_outside_allowed_roots(monkeypatch, tmp_path):
    server = _start_server(monkeypatch)
    host, port = server.server_address
    monkeypatch.setitem(
        streaming_server.settings.CONFIG, "ingest_allowed_roots", [str(tmp_path / "allowed")]
    )

    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)

    conn = http.client.HTTPConnection(host, port)
    payload = json.dumps({"path": str(outside)})
    conn.request(
        "POST", "/ingest/folder", body=payload, headers={"Content-Type": "application/json"}
    )
    resp = conn.getresponse()
    body = json.loads(resp.read().decode("utf-8"))

    assert resp.status == 400
    assert body["ok"] is False
    assert "outside configured allowed roots" in body["error"]

    conn.close()
    server.shutdown()
    server.server_close()


def test_docs_list_endpoint_global_and_scoped(monkeypatch, tmp_path):
    monkeypatch.setitem(
        streaming_server.settings.CONFIG, "doc_registry_path", str(tmp_path / "doc_registry.json")
    )
    store = DocRegistryStore(str(tmp_path / "doc_registry.json"))
    store.upsert(namespace="alpha", doc_id="doc-a", source_path="/tmp/a.txt", chunk_count=2)
    store.upsert(namespace="beta", doc_id="doc-b", source_path="/tmp/b.txt", chunk_count=1)
    store.save()

    server = _start_server(monkeypatch)
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port)

    conn.request("GET", "/docs?limit=10")
    resp = conn.getresponse()
    payload = json.loads(resp.read().decode("utf-8"))
    assert resp.status == 200
    assert payload["ok"] is True
    ids = {(row["namespace"], row["doc_id"]) for row in payload["records"]}
    assert ("alpha", "doc-a") in ids
    assert ("beta", "doc-b") in ids

    conn.request("GET", "/docs?namespace=alpha&limit=10")
    resp2 = conn.getresponse()
    payload2 = json.loads(resp2.read().decode("utf-8"))
    assert resp2.status == 200
    assert payload2["ok"] is True
    assert all(row["namespace"] == "alpha" for row in payload2["records"])

    conn.close()
    server.shutdown()
    server.server_close()


def test_docs_delete_endpoint_namespace_and_all(monkeypatch, tmp_path):
    monkeypatch.setitem(
        streaming_server.settings.CONFIG, "doc_registry_path", str(tmp_path / "doc_registry.json")
    )
    store = DocRegistryStore(str(tmp_path / "doc_registry.json"))
    store.upsert(namespace="alpha", doc_id="doc-x", source_path="/tmp/a.txt", chunk_count=2)
    store.upsert(namespace="default", doc_id="doc-x", source_path="/tmp/d.txt", chunk_count=1)
    store.save()

    def fake_delete(doc_id, namespace=None, all_namespaces=False):
        if doc_id != "doc-x":
            return 0
        if all_namespaces:
            return 2
        if namespace == "alpha":
            return 1
        if namespace == "default":
            return 1
        return 0

    monkeypatch.setattr(streaming_server, "delete_doc", fake_delete)
    server = _start_server(monkeypatch)
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port)

    conn.request("DELETE", "/docs/doc-x?namespace=alpha")
    resp = conn.getresponse()
    payload = json.loads(resp.read().decode("utf-8"))
    assert resp.status == 200
    assert payload["ok"] is True
    assert payload["vectors_deleted"] == 1
    assert payload["registry_deleted"] == 1
    assert payload["all_namespaces"] is False

    reload_store = DocRegistryStore(str(tmp_path / "doc_registry.json"))
    assert reload_store.get("alpha", "doc-x") is None
    assert reload_store.get("default", "doc-x") is not None

    conn.request("DELETE", "/docs/doc-x?all_namespaces=true")
    resp2 = conn.getresponse()
    payload2 = json.loads(resp2.read().decode("utf-8"))
    assert resp2.status == 200
    assert payload2["ok"] is True
    assert payload2["all_namespaces"] is True
    assert payload2["registry_deleted"] >= 1

    reload_store2 = DocRegistryStore(str(tmp_path / "doc_registry.json"))
    assert reload_store2.get("default", "doc-x") is None

    conn.request("DELETE", "/docs/missing-doc")
    resp3 = conn.getresponse()
    payload3 = json.loads(resp3.read().decode("utf-8"))
    assert resp3.status == 200
    assert payload3["ok"] is True
    assert payload3["not_found"] is True

    conn.close()
    server.shutdown()
    server.server_close()


def test_retrieval_query_returns_answer_sources_and_citation_stats(monkeypatch):
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

    monkeypatch.setattr(streaming_server.retrieval, "scored_chunks", fake_scored_chunks)
    server = _start_server(monkeypatch)
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port)

    conn.request(
        "POST",
        "/retrieval/query",
        body=json.dumps({"query": "payment terms", "top_k": 3, "rerank": True}),
        headers={"Content-Type": "application/json"},
    )
    resp = conn.getresponse()
    payload = json.loads(resp.read().decode("utf-8"))

    assert resp.status == 200
    assert payload["ok"] is True
    assert "answer" in payload and isinstance(payload["answer"], str)
    assert "sources" in payload and isinstance(payload["sources"], list)
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["citation_index"] == 1
    assert "citation_stats" in payload and isinstance(payload["citation_stats"], dict)

    conn.close()
    server.shutdown()
    server.server_close()
