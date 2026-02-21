import http.client
import json
import os
import threading

from http.server import ThreadingHTTPServer

from app.chat import streaming_server


def _start_server(monkeypatch):
    monkeypatch.setattr(
        streaming_server,
        "ingest_paths",
        lambda paths, options=None, embedding_model=None: {
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
        lambda uploaded, options=None, embedding_model=None: {
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
    conn.request("POST", "/ingest/files", body=payload, headers={"Content-Type": "application/json"})
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
        "Content-Disposition: form-data; name=\"file\"; filename=\"sample.txt\"\r\n"
        "Content-Type: text/plain\r\n\r\n"
        "hello upload\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    conn = http.client.HTTPConnection(host, port)
    conn.request(
        "POST",
        "/ingest/upload",
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))},
    )
    resp = conn.getresponse()
    payload = json.loads(resp.read().decode("utf-8"))

    assert resp.status == 200
    assert payload["ok"] is True
    assert payload["summary"]["total_files"] == 1

    conn.close()
    server.shutdown()
    server.server_close()


def test_ingest_folder_endpoint_json(monkeypatch):
    server = _start_server(monkeypatch)
    host, port = server.server_address

    conn = http.client.HTTPConnection(host, port)
    payload = json.dumps({"path": ".", "dry_run": True})
    conn.request("POST", "/ingest/folder", body=payload, headers={"Content-Type": "application/json"})
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
    conn.request("POST", "/ingest/folder", body=payload, headers={"Content-Type": "application/json"})
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
    conn.request("POST", "/ingest/folder", body=payload, headers={"Content-Type": "application/json"})
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
    monkeypatch.setitem(streaming_server.settings.CONFIG, "ingest_allowed_roots", [str(tmp_path / "allowed")])

    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)

    conn = http.client.HTTPConnection(host, port)
    payload = json.dumps({"path": str(outside)})
    conn.request("POST", "/ingest/folder", body=payload, headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    body = json.loads(resp.read().decode("utf-8"))

    assert resp.status == 400
    assert body["ok"] is False
    assert "outside configured allowed roots" in body["error"]

    conn.close()
    server.shutdown()
    server.server_close()
