"""Shared chat orchestration utilities for CLI and server chat paths."""

from __future__ import annotations

import time

from app.chat.citation_formatter import render_citation_output
from app.chat.citation_prompting import build_citation_prompt, format_source_blocks_text
from app.chat.streaming_llm_client import stream_chat_with_continuation


def get_relevant_context(query: str, retrieval_module, top_k: int, on_error=None):
    try:
        return retrieval_module.scored_chunks(query, top_k=top_k)
    except Exception as exc:
        if on_error is not None:
            on_error(exc)
        return []


def build_context_prompt(user_input: str, retrieved_chunks, top_k: int, settings):
    return build_citation_prompt(
        user_input,
        retrieved_chunks,
        max_sources=top_k,
        max_snippet_chars=int(settings.CONFIG.get("citation_max_snippet_chars", 500)),
    )


def citation_render_config(settings, top_k: int):
    citations_mode = settings.CONFIG.get("citations_mode", "inline")
    citations_enabled = bool(settings.CONFIG.get("citations", True))
    effective_mode = citations_mode if citations_enabled else "none"
    max_sources = int(settings.CONFIG.get("citation_max_sources", top_k))
    max_snippet_chars = int(settings.CONFIG.get("citation_max_snippet_chars", 240))
    return {
        "mode": effective_mode,
        "max_sources": max_sources,
        "max_snippet_chars": max_snippet_chars,
    }


def render_answer_with_citations(answer: str, source_blocks, settings, top_k: int):
    opts = citation_render_config(settings, top_k=top_k)
    rendered = render_citation_output(
        answer,
        source_blocks,
        mode=opts["mode"],
        max_sources=opts["max_sources"],
        max_snippet_chars=opts["max_snippet_chars"],
    )
    if rendered["sources_text"]:
        print(rendered["sources_text"])
    return rendered["answer"]


def stream_chat_answer(
    *,
    client,
    ollama_model: str,
    messages,
    source_blocks,
    settings,
    top_k: int,
    max_continuations,
    per_call_max_tokens,
    enable_thinking_summary: bool,
    formatting,
    error_message: str,
):
    provider_timeout = settings.CONFIG.get(
        "provider_timeout_s", settings.CONFIG.get("model_timeout", 120)
    )
    flush_interval_ms = settings.CONFIG.get("flush_interval_ms", 250)
    effective_per_call_tokens = per_call_max_tokens or settings.CONFIG.get(
        "per_call_max_tokens",
        settings.CONFIG.get("chat_max_tokens", 4000),
    )
    effective_max_continuations = (
        settings.CONFIG.get("max_continuations", 2)
        if max_continuations is None
        else max_continuations
    )
    continuation_instruction = settings.CONFIG.get(
        "continuation_instruction",
        "Continue exactly where you left off. Do not repeat prior text.",
    )

    done_text = ""
    saw_delta = False
    stream_failed = False
    last_token_at = time.monotonic()
    last_keepalive_notice_at = 0.0

    for event in stream_chat_with_continuation(
        client,
        model=ollama_model,
        messages=messages,
        per_call_max_tokens=effective_per_call_tokens,
        continuation_instruction=continuation_instruction,
        max_continuations=effective_max_continuations,
        timeout=provider_timeout,
        flush_interval_ms=flush_interval_ms,
        enable_thinking_summary=enable_thinking_summary,
    ):
        event_name = event.get("event")
        data = event.get("data", {})

        if event_name == "final_delta":
            text = data.get("text", "")
            if text:
                formatting.print_stream_delta(text)
                saw_delta = True
                last_token_at = time.monotonic()
        elif event_name == "meta" and data.get("kind") == "keepalive":
            now = time.monotonic()
            if now - last_token_at >= 3.0 and now - last_keepalive_notice_at >= 3.0:
                formatting.print_stream_keepalive()
                last_keepalive_notice_at = now
        elif event_name == "thinking_delta":
            summary = data.get("text", "").strip()
            if summary:
                formatting.print_thinking_summary(summary)
        elif event_name == "error":
            stream_failed = True
            detail = data.get("detail") or data.get("message") or "unknown streaming error"
            formatting.print_stream_error(detail)
        elif event_name == "done":
            done_text = data.get("text", "")
            if saw_delta:
                print()

    if stream_failed and not done_text:
        return error_message
    if not done_text:
        done_text = error_message

    return render_answer_with_citations(done_text, source_blocks, settings=settings, top_k=top_k)


def build_messages(system_message: str, conversation_history):
    return [{"role": "system", "content": system_message}, *conversation_history]


def context_blocks_to_text(source_blocks):
    return format_source_blocks_text(source_blocks)
