from __future__ import annotations

from http import HTTPStatus
from urllib.parse import parse_qs

from app.http.sse import to_sse


def _get_relevant_context(retrieval, query: str, top_k: int):
    try:
        return retrieval.scored_chunks(query, top_k=top_k)
    except Exception as exc:
        # Retrieval failures should not break chat streaming; emit empty context.
        try:
            retrieval_logger = getattr(retrieval, "logger", None)
            if retrieval_logger:
                retrieval_logger.exception("chat_context_retrieval_failed error=%s", exc)
        except Exception:
            pass
        return []


def _build_messages(deps, question: str, top_k: int):
    settings = deps["settings"]
    retrieved_chunks = _get_relevant_context(deps["retrieval"], question, top_k=top_k)
    user_text, source_blocks = deps["build_citation_prompt"](
        question,
        retrieved_chunks,
        max_sources=top_k,
        max_snippet_chars=int(settings.CONFIG.get("citation_max_snippet_chars", 500)),
    )
    system_message = settings.CONFIG.get(
        "system_message",
        "You are a helpful assistant that is an expert at extracting the most useful information from a given text.",
    )
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_text},
    ], source_blocks


def handle_chat_stream_get(handler, deps, parsed) -> bool:
    if parsed.path != "/chat/stream":
        return False

    settings = deps["settings"]
    query = parse_qs(parsed.query)
    question = (query.get("question") or [""])[0].strip()
    if not question:
        handler.send_error(HTTPStatus.BAD_REQUEST, "Missing required query parameter: question")
        return True

    try:
        model = (query.get("model") or [settings.CONFIG.get("ollama_model", "llama3")])[0]
        top_k = int((query.get("top_k") or [settings.CONFIG.get("top_k", 3)])[0])
        max_continuations = int(
            (query.get("max_continuations") or [settings.CONFIG.get("max_continuations", 2)])[0]
        )
        per_call_max_tokens = int(
            (
                query.get("per_call_max_tokens")
                or [
                    settings.CONFIG.get(
                        "per_call_max_tokens", settings.CONFIG.get("chat_max_tokens", 4000)
                    )
                ]
            )[0]
        )
    except ValueError:
        handler.send_error(HTTPStatus.BAD_REQUEST, "Invalid numeric query parameter")
        return True

    enable_thinking_summary_raw = (
        (query.get("enable_thinking_summary") or ["false"])[0].strip().lower()
    )
    enable_thinking_summary = enable_thinking_summary_raw in {"1", "true", "yes", "on"}

    timeout = settings.CONFIG.get("provider_timeout_s", settings.CONFIG.get("model_timeout", 120))
    flush_interval_ms = settings.CONFIG.get("flush_interval_ms", 250)
    continuation_instruction = settings.CONFIG.get(
        "continuation_instruction",
        "Continue exactly where you left off. Do not repeat prior text.",
    )

    client = deps["OpenAI"](
        base_url=settings.CONFIG.get("ollama_api", {}).get("base_url", "http://localhost:11434/v1"),
        api_key=settings.CONFIG.get("ollama_api", {}).get("api_key"),
    )
    messages, source_blocks = _build_messages(deps, question=question, top_k=top_k)

    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "close")
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()

    try:
        for event in deps["stream_chat_with_continuation"](
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
            if name == "done":
                handler.wfile.write(to_sse("sources", {"sources": source_blocks}))
                if source_blocks:
                    stats_payload = deps["render_citation_output"](
                        payload.get("text", ""),
                        source_blocks,
                        mode="inline",
                        max_sources=int(settings.CONFIG.get("citation_max_sources", top_k)),
                        max_snippet_chars=int(
                            settings.CONFIG.get("citation_max_snippet_chars", 240)
                        ),
                    ).get("stats", {})
                    handler.wfile.write(to_sse("citation_stats", {"stats": stats_payload}))
            handler.wfile.write(to_sse(name, payload))
            handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        return True
    except Exception as exc:
        handler.log_exception("chat_stream_failed", exc)
        try:
            handler.wfile.write(
                to_sse("error", {"message": "server_stream_error", "detail": str(exc)})
            )
            handler.wfile.write(to_sse("done", {"cancelled": True}))
            handler.wfile.flush()
        except Exception:
            pass
    return True
