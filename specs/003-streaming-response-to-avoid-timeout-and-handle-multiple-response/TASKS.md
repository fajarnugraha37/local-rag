# Tasks: Streaming Response & Multi-Call Continuation

## Progress Tracker
- Status counts: todo 2, doing 0, done 5, blocked 0.

## Task List

### T001 — Define streaming protocol + config (status: done)
- Goal: Provide shared event schema and config knobs for streaming/continuation.
- Files: `app/common/stream_protocol.py`, `config.yaml`, `app/config/runtime_settings.py`.
- Steps: add event builders, add defaults (`enable_streaming`, `enable_thinking_summary`, `per_call_max_tokens`, `max_continuations`, `flush_interval_ms`, `provider_timeout_s`, `continuation_instruction`), ensure loader reads them.
- Acceptance: protocol helpers importable; config keys available with sane defaults; existing CLIs still run.
- Validation: `python -m pytest -q`.

### T002 — Streaming + continuation wrapper (status: done)
- Goal: Create a reusable streaming client that emits protocol events and chains calls on `finish_reason="length"`.
- Files: `app/chat/streaming_llm_client.py` (new), optional helper in `app/common/stream_protocol.py`.
- Steps: implement streaming call with `stream=True`, keep-alives, continuation loop, optional thinking summary sanitizing `<think>` tags, retries, cancellation hook.
- Acceptance: function yields ordered protocol events; stops after `max_continuations`; respects `per_call_max_tokens`.
- Validation: run a local smoke script that prints streamed chunks; ensure no exceptions.

### T003 — Integrate into document chat CLI (status: done)
- Goal: Make `app/chat/document_chat_cli.py` support streaming without breaking current usage.
- Files: `app/chat/document_chat_cli.py`, root shim `localrag.py` if needed.
- Steps: add CLI flags (`--stream`, `--max-continuations`, `--per-call-max-tokens`, `--enable-thinking-summary`); route through streaming wrapper when enabled; keep non-stream path unchanged.
- Acceptance: streaming flag streams incremental output; old invocation works identically when streaming disabled.
- Validation: `python -m app.chat.document_chat_cli --model llama3 --top-k 1 --stream --max-continuations 2`.

### T004 — Apply to baseline and email CLIs (status: done)
- Goal: Extend streaming support to other chat entrypoints.
- Files: `app/chat/document_chat_baseline_cli.py`, `app/chat/email_chat_cli.py`, root shims (`localrag_no_rewrite.py`, `emailrag2.py`) if signature changes.
- Steps: wire in streaming wrapper, expose same flags, preserve defaults.
- Acceptance: both CLIs run with and without `--stream`; no regression in conversation history handling.
- Validation: run each CLI once with `--stream`; optional quick prompt “ping”.

### T005 — Optional SSE endpoint (status: done)
- Goal: Expose streaming protocol over HTTP without heavy deps.
- Files: `app/chat/streaming_server.py` (new) or minimal server module; optional runner script.
- Steps: implement `/chat/stream` SSE endpoint forwarding events from streaming wrapper; send keep-alives; handle client disconnect.
- Acceptance: `curl -N http://localhost:8000/chat/stream?...` returns SSE events until completion.
- Validation: manual curl; server exits cleanly on ctrl+c.

### T006 — Tests for continuation and streaming (status: todo)
- Goal: Cover continuation logic, ordering, and toggles.
- Files: `tests/test_streaming_continuation.py` (new), adjust fixtures if needed.
- Steps: mock provider to force `finish_reason="length"`, assert concatenated output equals expected, test cancellation and config toggles.
- Acceptance: new tests pass and existing tests unaffected.
- Validation: `python -m pytest -q`.

### T007 — Update docs (status: todo)
- Goal: Document new behavior and usage.
- Files: `README.md`, `AGENTS.md`, optionally `specs/003...` links.
- Steps: add streaming flags/examples, SSE contract summary, safety note about thinking summaries defaulting off.
- Acceptance: docs mention streaming + continuation, commands are accurate.
- Validation: manual read; check links/paths resolve.
