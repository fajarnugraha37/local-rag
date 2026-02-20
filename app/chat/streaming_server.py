import argparse
import contextlib
import io
import json
import re
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from openai import OpenAI

from cmd.actions import ACTION_SPECS, run_action
from app.chat.streaming_llm_client import stream_chat_with_continuation
from app.config import runtime_settings as settings
from app.context import token_budget_packer as context_packer
from app.ingestion.vector_ingest_service import delete_doc, ingest_chunks
from app.retrieval import hybrid_search as retrieval


HTTP_ACTION_EXCLUDE = {"chat", "chat-baseline", "chat-email", "ingest-files", "server"}
HTTP_ACTIONS = sorted(name for name in ACTION_SPECS if name not in HTTP_ACTION_EXCLUDE)


def _parse_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _get_relevant_context(query: str, top_k: int):
    try:
        results = retrieval.scored_chunks(query, top_k=top_k)
        return [item.get("text", "").strip() for item in results if item.get("text")]
    except Exception:
        return []


def _build_messages(question: str, system_message: str, top_k: int):
    relevant_context = _get_relevant_context(question, top_k=top_k)
    if relevant_context:
        max_tokens = settings.CONFIG.get("context_token_budget", 1500)
        overlap_tokens = settings.CONFIG.get("context_overlap", 20)
        packed = context_packer.pack_context(
            question,
            relevant_context,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )
        context_str = "\n\n".join(packed)
        user_text = f"{question}\n\nRelevant Context:\n{context_str}"
    else:
        user_text = question
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_text},
    ]


def _to_sse(event_name: str, payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_name}\ndata: {body}\n\n".encode("utf-8")


def _chunk_text_for_ingest(text: str, max_chars: int) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?]) +", normalized)
    chunks = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip()
            continue
        if current:
            chunks.append(current)
        current = sentence
    if current:
        chunks.append(current)
    return chunks


def _run_action_capture(action: str, action_args: list[str]) -> dict:
    started = time.monotonic()
    out_buffer = io.StringIO()
    err_buffer = io.StringIO()
    with contextlib.redirect_stdout(out_buffer), contextlib.redirect_stderr(err_buffer):
        exit_code = run_action(action, action_args)
    return {
        "action": action,
        "args": action_args,
        "exit_code": exit_code,
        "stdout": out_buffer.getvalue(),
        "stderr": err_buffer.getvalue(),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


class StreamingHandler(BaseHTTPRequestHandler):
    server_version = "LocalRAGSSE/1.1"

    def _send_json(self, status: int, payload: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _read_json(self) -> dict:
        raw_len = self.headers.get("Content-Length", "0")
        try:
            content_len = int(raw_len)
        except ValueError:
            raise ValueError("invalid Content-Length")
        if content_len <= 0:
            raise ValueError("empty request body")
        raw_body = self.rfile.read(content_len)
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"invalid JSON body: {exc}") from exc
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object")
        return body

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return

        if parsed.path in {"/actions", "/action"}:
            actions = []
            for name in sorted(ACTION_SPECS):
                spec = ACTION_SPECS[name]
                actions.append(
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "http_supported": spec.name in HTTP_ACTIONS,
                    }
                )
            self._send_json(
                HTTPStatus.OK,
                {
                    "actions": actions,
                    "http_supported_actions": HTTP_ACTIONS,
                    "notes": {
                        "run_endpoint": "POST /actions/run",
                        "interactive_actions_blocked": sorted(HTTP_ACTION_EXCLUDE),
                    },
                },
            )
            return

        if parsed.path != "/chat/stream":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        query = parse_qs(parsed.query)
        question = (query.get("question") or [""])[0].strip()
        if not question:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing required query parameter: question")
            return

        try:
            model = (query.get("model") or [settings.CONFIG.get("ollama_model", "llama3")])[0]
            top_k = int((query.get("top_k") or [settings.CONFIG.get("top_k", 3)])[0])
            max_continuations = int(
                (query.get("max_continuations") or [settings.CONFIG.get("max_continuations", 2)])[0]
            )
            per_call_max_tokens = int(
                (
                    query.get("per_call_max_tokens")
                    or [settings.CONFIG.get("per_call_max_tokens", settings.CONFIG.get("chat_max_tokens", 4000))]
                )[0]
            )
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid numeric query parameter")
            return

        enable_thinking_summary_raw = (query.get("enable_thinking_summary") or ["false"])[0].strip().lower()
        enable_thinking_summary = enable_thinking_summary_raw in {"1", "true", "yes", "on"}

        system_message = settings.CONFIG.get(
            "system_message",
            "You are a helpful assistant that is an expert at extracting the most useful information from a given text.",
        )
        timeout = settings.CONFIG.get("provider_timeout_s", settings.CONFIG.get("model_timeout", 120))
        flush_interval_ms = settings.CONFIG.get("flush_interval_ms", 250)
        continuation_instruction = settings.CONFIG.get(
            "continuation_instruction",
            "Continue exactly where you left off. Do not repeat prior text.",
        )

        client = OpenAI(
            base_url=settings.CONFIG.get("ollama_api", {}).get("base_url", "http://localhost:11434/v1"),
            api_key=settings.CONFIG.get("ollama_api", {}).get("api_key"),
        )
        messages = _build_messages(question, system_message=system_message, top_k=top_k)

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        try:
            for event in stream_chat_with_continuation(
                client,
                model=model,
                messages=messages,
                per_call_max_tokens=per_call_max_tokens,
                continuation_instruction=continuation_instruction,
                max_continuations=max_continuations,
                timeout=timeout,
                flush_interval_ms=flush_interval_ms,
                enable_thinking_summary=enable_thinking_summary,
            ):
                name = event.get("event", "message")
                payload = event.get("data", {})
                self.wfile.write(_to_sse(name, payload))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            try:
                self.wfile.write(_to_sse("error", {"message": "server_stream_error", "detail": str(exc)}))
                self.wfile.write(_to_sse("done", {"cancelled": True}))
                self.wfile.flush()
            except Exception:
                return

    def do_POST(self):
        parsed = urlparse(self.path)

        try:
            body = self._read_json()
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return

        if parsed.path == "/ingest/chunks":
            chunks = body.get("chunks")
            if not isinstance(chunks, list) or not chunks:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'chunks' must be a non-empty array"})
                return
            source_path = body.get("source_path")
            doc_id = body.get("doc_id")
            embedding_model = body.get("embedding_model")
            try:
                result = ingest_chunks(chunks, source_path=source_path, doc_id=doc_id, embedding_model=embedding_model)
                self._send_json(HTTPStatus.OK, {"ok": True, "result": result})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path == "/ingest/text":
            text = (body.get("text") or "").strip()
            if not text:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'text' is required"})
                return
            try:
                max_chars = int(body.get("max_chars") or settings.CONFIG.get("chunk_max_chars", 1000))
            except (TypeError, ValueError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'max_chars' must be an integer"})
                return
            chunks = _chunk_text_for_ingest(text, max_chars=max(1, max_chars))
            source_path = body.get("source_path")
            doc_id = body.get("doc_id")
            embedding_model = body.get("embedding_model")
            try:
                result = ingest_chunks(chunks, source_path=source_path, doc_id=doc_id, embedding_model=embedding_model)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "chunk_count": len(chunks),
                        "result": result,
                    },
                )
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path == "/vectors/delete-doc":
            doc_id = (body.get("doc_id") or "").strip()
            if not doc_id:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'doc_id' is required"})
                return
            try:
                deleted = delete_doc(doc_id)
                self._send_json(HTTPStatus.OK, {"ok": True, "doc_id": doc_id, "deleted": deleted})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path == "/retrieval/query":
            query_text = (body.get("query") or "").strip()
            if not query_text:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'query' is required"})
                return
            try:
                top_k = int(body.get("top_k") or settings.CONFIG.get("top_k", 6))
            except (TypeError, ValueError):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'top_k' must be an integer"})
                return
            rerank = _parse_bool(body.get("rerank"), default=True)
            filters = body.get("filters")
            if filters is not None and not isinstance(filters, dict):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'filters' must be an object"})
                return
            try:
                results = retrieval.scored_chunks(query_text, top_k=top_k, rerank=rerank, filters=filters)
                self._send_json(HTTPStatus.OK, {"ok": True, "count": len(results), "results": results})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        if parsed.path in {"/actions/run", "/action/run"}:
            action = (body.get("action") or "").strip()
            action_args = body.get("args") or []
            if action not in HTTP_ACTIONS:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "ok": False,
                        "error": "unsupported action for HTTP execution",
                        "allowed_actions": HTTP_ACTIONS,
                    },
                )
                return
            if not isinstance(action_args, list) or any(not isinstance(v, str) for v in action_args):
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "'args' must be an array of strings"})
                return
            try:
                result = _run_action_capture(action, action_args)
                self._send_json(HTTPStatus.OK, {"ok": result["exit_code"] == 0, "result": result})
                return
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
                return

        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def log_message(self, format, *args):
        # Keep server output concise.
        return


def main():
    parser = argparse.ArgumentParser(description="Streaming SSE server for local RAG chat.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), StreamingHandler)
    print(f"SSE server listening on http://{args.host}:{args.port}")
    print("GET  /health")
    print("GET  /actions")
    print("GET  /chat/stream?question=...&top_k=...&model=...")
    print("POST /ingest/chunks")
    print("POST /ingest/text")
    print("POST /vectors/delete-doc")
    print("POST /retrieval/query")
    print("POST /actions/run")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
