# Streaming Response & Multi-Call Continuation (Feature 003)

## Current Behavior (grounded)
- Chat entrypoints are CLI scripts (`app/chat/document_chat_cli.py`, `app/chat/document_chat_baseline_cli.py`, `app/chat/email_chat_cli.py`; root shims like `localrag.py` delegate to them).
- Each issues a single blocking `client.chat.completions.create(...)` call (OpenAI SDK pointed at Ollama) with `max_tokens` from `config.yaml` (`chat_max_tokens: 4000`, `model_timeout: 120`). No `stream=True`.
- Responses are returned only after the model finishes; nothing is flushed early. `finish_reason` is ignored, so `length` truncations silently drop tail content. `_call_with_timeout` wraps calls but simply returns `None` on timeout (no retry).
- Transport is STDOUT; there is no HTTP/SSE/WebSocket surface and no keep-alives. Long generations risk client-side wait and HTTP proxy timeout if served through a thin server in front.

## Problem / Root Cause
- Fixed `chat_max_tokens` caps answers; when the model hits the limit it stops with `finish_reason="length"` and the tail is lost.
- Single-call, non-streaming responses mean callers wait for full output; long generations can exceed `model_timeout` or proxy idle timeouts.
- No continuation logic, no retry, and no explicit separation between “thinking” hints and final text; risk of either losing reasoning or leaking chain-of-thought if we ever stream raw tokens.

## Chosen Direction (why)
- **Multi-call continuation + streaming**: keep the connection alive, surface partial tokens quickly, and automatically chain follow-up completions when `finish_reason=length`.
- Alternatives considered:
  - Increase `max_tokens`: higher latency/cost; still hard-cap; small 1B/8k models cannot expand much.
  - Aggressive summarization/rewrite: reduces fidelity and still fails on very long answers.
  - Smaller retrieval packs: already token-budgeted via `app/context/token_budget_packer.py` but does not prevent answer truncation.
- Therefore we add streaming + continuation as first-class behavior, keeping existing CLI commands compatible.

## Streaming Protocol Proposal
- Transport: **SSE** over HTTP (lightweight, no heavy deps) plus compatible console streamer.
- Event types:
  - `meta`: `{request_id, model, started_at}`
  - `thinking_delta`: text chunk of high-level approach (optional, sanitized)
  - `final_delta`: text chunk of the user-facing answer
  - `part_done`: `{part_index, finish_reason, usage}`
  - `done`: `{total_parts, duration_ms, usage}`
  - `error`: `{code, message}`
- Example SSE frame: `event: final_delta\ndata: {"chunk":"..."}\n\n`
- Keep-alive: send empty comment `:\n\n` every `flush_interval_ms`.

## Continuation Algorithm (pseudo-flow)
1. Build base prompt (system + history + packed context).
2. Call provider with `stream=True`, `max_tokens=per_call_max_tokens`.
3. Stream deltas to client; accumulate text per part.
4. On `finish_reason="length"` and while `part_index < max_continuations`:
   - Append instruction: “Continue exactly where you left off; do not repeat earlier text; keep formatting.”
   - Reissue completion with updated history and continuation hint.
   - Stream follow-up deltas as the same logical response (increment `part_index`).
5. Stop when finish_reason != length or limit reached; emit `done` or `error` accordingly.
6. If thinking summary enabled, prepend a short bulletized plan generated in a tiny side-call; never forward raw reasoning tokens.

## Config Knobs
- `enable_streaming` (default false), `enable_thinking_summary` (default false)
- `per_call_max_tokens` (defaults to existing `chat_max_tokens`)
- `max_continuations` (e.g., 4)
- `flush_interval_ms`, `provider_timeout_s`, `retry_limit`
- `continuation_instruction` template (string)

## Risks & Mitigations
- Repetition or drift across parts → include strict continuation instruction; dedupe by comparing trailing text before streaming.
- Cost explosion → enforce `max_continuations` and per-call token cap; log usage per part.
- Proxy buffering / idle timeout → use SSE with periodic flush/keep-alive.
- Chain-of-thought leakage → default `enable_thinking_summary` off; summaries are short, user-safe; strip `<think>` blocks before streaming.
- Client disconnects → observe request cancellation and stop downstream calls.

## Acceptance Criteria
- Long answers continue over multiple calls until completion within configured limits.
- Clients receive progressive streamed text (visible in console and via SSE).
- Thinking vs final content is clearly tagged; no raw chain-of-thought leaks.
- Tests cover length-truncation continuation, stream ordering, and disconnect/cancel handling (where feasible).
