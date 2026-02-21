from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from app.http.handlers.actions import handle_actions_get, handle_actions_post
from app.http.handlers.chat import handle_chat_stream_get
from app.http.handlers.docs import handle_docs_delete, handle_docs_get
from app.http.handlers.ingestion import handle_ingestion_post


def create_streaming_handler(deps_provider):
    class StreamingHandler(BaseHTTPRequestHandler):
        server_version = "LocalRAGSSE/1.1"

        def send_json(self, status: int, payload: dict) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

        def do_GET(self):
            deps = deps_provider()
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self.send_json(HTTPStatus.OK, {"ok": True})
                return
            if handle_actions_get(self, deps, parsed):
                return
            if handle_docs_get(self, deps, parsed):
                return
            if handle_chat_stream_get(self, deps, parsed):
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self):
            deps = deps_provider()
            parsed = urlparse(self.path)
            if handle_ingestion_post(self, deps, parsed):
                return
            if handle_actions_post(self, deps, parsed):
                return
            self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

        def do_DELETE(self):
            deps = deps_provider()
            parsed = urlparse(self.path)
            if handle_docs_delete(self, deps, parsed):
                return
            self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

        def log_message(self, format, *args):
            return

    return StreamingHandler


def run_server(host: str, port: int, handler_cls) -> None:
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"SSE server listening on http://{host}:{port}")
    print("GET  /health")
    print("GET  /actions")
    print("GET  /docs")
    print("GET  /chat/stream?question=...&top_k=...&model=...")
    print("POST /ingest/chunks")
    print("POST /ingest/text")
    print("POST /ingest/files")
    print("POST /ingest/folder")
    print("POST /ingest/upload (multipart form-data)")
    print("POST /vectors/delete-doc")
    print("POST /retrieval/query")
    print("POST /actions/run")
    print("DELETE /docs/{doc_id}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(handler_cls) -> None:
    parser = argparse.ArgumentParser(description="Streaming SSE server for local RAG chat.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    args = parser.parse_args()
    run_server(args.host, args.port, handler_cls)
