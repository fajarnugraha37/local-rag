import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from openai import OpenAI

from app.chat.streaming_llm_client import stream_chat_with_continuation
from app.config import runtime_settings as settings
from app.context import token_budget_packer as context_packer
from app.retrieval import hybrid_search as retrieval


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


class StreamingHandler(BaseHTTPRequestHandler):
    server_version = "LocalRAGSSE/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        if parsed.path != "/chat/stream":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        query = parse_qs(parsed.query)
        question = (query.get("question") or [""])[0].strip()
        if not question:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing required query parameter: question")
            return

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
    print("Endpoint: /chat/stream?question=...&top_k=...&model=...")
    print("Health: /health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
