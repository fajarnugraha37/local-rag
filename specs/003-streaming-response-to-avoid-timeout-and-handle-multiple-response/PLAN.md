# Plan: Streaming Response & Multi-Call Continuation (Feature 003)

## Preconditions
- Repo already has OpenAI/Ollama client usage in `app/chat/document_chat_cli.py`, `app/chat/document_chat_baseline_cli.py`, `app/chat/email_chat_cli.py`.
- Tests run with `python -m pytest -q`.
- Keep existing CLI flags working; root shims (`localrag.py`, etc.) must keep functioning.

## Steps
1. **Add streaming protocol primitives**
   - Create `app/common/stream_protocol.py` defining SSE-friendly event helpers (`meta`, `thinking_delta`, `final_delta`, `part_done`, `done`, `error`) and a simple `StreamEnvelope` dataclass/dict builder.
   - Add config defaults to `config.yaml` + load in `app/config/runtime_settings.py`:
     - `enable_streaming` (false), `enable_thinking_summary` (false), `per_call_max_tokens` (default `chat_max_tokens`), `max_continuations`, `flush_interval_ms`, `provider_timeout_s`, `continuation_instruction`.
   - Validation: `python -m pytest -q` (should still pass).

2. **Implement streaming + continuation client wrapper**
   - Create `app/chat/streaming_llm_client.py` (or similar) that wraps `OpenAI.chat.completions.create(stream=True, ...)`, yields protocol events, and chains follow-up calls when `finish_reason="length"` up to `max_continuations`.
   - Responsibilities:
     - Accept `messages`, `per_call_max_tokens`, `continuation_instruction`, `max_continuations`, `timeout`, `enable_thinking_summary`.
     - Sanitize `<think>` blocks; optionally emit a short thinking summary via a tiny side-call.
     - Emit keep-alive ticks every `flush_interval_ms`.
     - Stop on client cancel (check an injected `cancel_event` or callback).
   - Add lightweight retry for transient provider errors (`retry_limit`, small backoff).
   - Validation: run a dry call with a short prompt to ensure stream yields (`python - <<'PY' ...`).

3. **Integrate wrapper into document chat CLI**
   - Update `app/chat/document_chat_cli.py` to:
     - Add CLI flags `--stream/--no-stream`, `--max-continuations`, `--per-call-max-tokens`, `--enable-thinking-summary`.
     - Switch chat invocation to streaming client when enabled; otherwise fallback to existing single-call path.
     - Preserve printed UX: stream partial tokens to console; keep current return value and conversation history behavior.
   - Ensure `_call_with_timeout` is either reused for non-stream or replaced by the new timeout handling.
   - Validation: `python -m app.chat.document_chat_cli --model llama3 --top-k 1 --stream --max-continuations 2` (observe incremental output).

4. **Apply to baseline and email chat CLIs**
   - Wire the streaming client into `app/chat/document_chat_baseline_cli.py` and `app/chat/email_chat_cli.py` with the same flags; default to non-stream for backward compatibility.
   - Keep behavior identical when `--stream` is not passed.
   - Validation: run each CLI with `--stream` once; confirm no regressions without the flag.

5. **Optional SSE server surface**
   - Add minimal SSE endpoint (no heavy deps) in `app/chat/streaming_server.py` using `aiohttp`/`starlette`-lite or stdlib `http.server` with chunked responses.
   - Endpoint `/chat/stream` accepts query/body matching current CLI inputs (question, top_k, model); streams protocol events from the new client wrapper.
   - Provide simple `uvicorn` runner if using ASGI, or `python -m app.chat.streaming_server` for stdlib server.
   - Validation: `curl -N http://localhost:8000/chat/stream?...` shows event stream; stop server cleanly on CTRL+C.

6. **Tests**
   - Add `tests/test_streaming_continuation.py` covering:
     - Continuation triggered on synthetic `finish_reason="length"` (mock provider).
     - Stream ordering and aggregation.
     - Cancellation path (simulate client disconnect).
     - Config toggles (`enable_streaming`, `enable_thinking_summary`).
   - Update smoke tests if needed to account for new defaults.
   - Validation: `python -m pytest -q`.

7. **Docs and examples**
   - Update `README.md` and `AGENTS.md` with new streaming flags, SSE endpoint, config keys, and safety note about thinking summaries defaulting off.
   - Add a short usage snippet showing how to capture SSE events.
   - Validation: spell-check/format check if available; otherwise manual read.

## Rollback Guidance
- To undo a file: `git restore <path>`.
- To drop all changes for this feature: `git restore specs/003-*/ app/common app/chat config.yaml`.
- Keep commits small per step to simplify revert (`git revert <sha>` if already committed).

## Debug Checklist
- No stream output: confirm `stream=True` is passed to OpenAI client and SSE endpoint flushes with `\n\n`.
- Repeated text across continuations: ensure continuation prompt includes “continue exactly where you left off; do not repeat earlier text” and trim duplicate prefix when concatenating.
- Hanging connections: check `flush_interval_ms` keep-alives and provider timeout.
- Chain-of-thought leakage: verify thinking summary generation strips `<think>` tags; keep `enable_thinking_summary` off in prod.
