import http.client
import json
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
