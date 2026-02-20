import re
import time
from typing import Callable, Dict, Generator, List, Optional, Tuple

from app.common import stream_protocol as protocol


def strip_think_blocks(text: str) -> str:
    if not text:
        return ""
    # Remove explicit <think>...</think> blocks and any dangling open tag section.
    cleaned = re.sub(r"(?is)<think\b[^>]*>.*?</think>", "", text)
    cleaned = re.sub(r"(?is)<think\b[^>]*>.*$", "", cleaned)
    return cleaned.strip()


def _is_cancelled(cancel_event=None, cancel_check: Optional[Callable[[], bool]] = None) -> bool:
    if cancel_event is not None:
        is_set = getattr(cancel_event, "is_set", None)
        if callable(is_set) and is_set():
            return True
    if cancel_check is not None and cancel_check():
        return True
    return False


def _dedupe_prefix(previous_text: str, new_text: str) -> str:
    if not previous_text or not new_text:
        return new_text
    max_overlap = min(len(previous_text), len(new_text))
    for size in range(max_overlap, 0, -1):
        if previous_text.endswith(new_text[:size]):
            return new_text[size:]
    return new_text


def _extract_choice_fields(chunk) -> Tuple[str, Optional[str]]:
    try:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return "", None
        first = choices[0]
        delta = getattr(first, "delta", None)
        content = getattr(delta, "content", None) if delta is not None else None
        finish_reason = getattr(first, "finish_reason", None)
        return content or "", finish_reason
    except Exception:
        return "", None


def _summarize_thinking_if_enabled(
    client,
    model: str,
    full_text: str,
    enable_thinking_summary: bool,
    timeout: Optional[float],
) -> Optional[str]:
    if not enable_thinking_summary:
        return None
    if not full_text:
        return None

    think_match = re.search(r"(?is)<think\b[^>]*>(.*?)</think>", full_text)
    if not think_match:
        return None

    thinking_text = think_match.group(1).strip()
    if not thinking_text:
        return None

    prompt = (
        "Summarize this reasoning in one short sentence without sensitive details. "
        "Do not reveal chain-of-thought, only provide a high-level summary."
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": thinking_text[:1500]},
    ]
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=60,
            temperature=0.0,
            timeout=timeout,
        )
        summary = resp.choices[0].message.content.strip()
        return summary or None
    except Exception:
        return None


def stream_chat_with_continuation(
    client,
    *,
    model: str,
    messages: List[Dict[str, str]],
    per_call_max_tokens: int,
    continuation_instruction: str,
    max_continuations: int,
    timeout: Optional[float] = None,
    flush_interval_ms: int = 250,
    enable_thinking_summary: bool = False,
    retry_limit: int = 2,
    retry_backoff_s: float = 0.3,
    cancel_event=None,
    cancel_check: Optional[Callable[[], bool]] = None,
    temperature: Optional[float] = None,
) -> Generator[Dict[str, object], None, None]:
    """
    Stream chat completion events and continue generation when finish_reason is `length`.

    Event contract uses app.common.stream_protocol helpers.
    """
    yield protocol.meta(
        model=model,
        stream=True,
        per_call_max_tokens=per_call_max_tokens,
        max_continuations=max_continuations,
    )

    base_messages = list(messages)
    assembled_text = ""
    part_index = 0
    continuation_budget = max(0, int(max_continuations))

    while True:
        if _is_cancelled(cancel_event=cancel_event, cancel_check=cancel_check):
            yield protocol.done(cancelled=True, text=assembled_text)
            return

        attempts = 0
        stream_obj = None
        while attempts <= retry_limit:
            try:
                kwargs = {
                    "model": model,
                    "messages": base_messages,
                    "max_tokens": per_call_max_tokens,
                    "stream": True,
                    "timeout": timeout,
                }
                if temperature is not None:
                    kwargs["temperature"] = temperature
                stream_obj = client.chat.completions.create(**kwargs)
                break
            except Exception as exc:
                attempts += 1
                if attempts > retry_limit:
                    yield protocol.error(
                        "stream_request_failed",
                        detail=str(exc),
                        attempt=attempts,
                    )
                    yield protocol.done(cancelled=False, text=assembled_text)
                    return
                time.sleep(retry_backoff_s * attempts)

        part_text = ""
        part_finish_reason = None
        last_flush = time.monotonic()

        try:
            for chunk in stream_obj:
                if _is_cancelled(cancel_event=cancel_event, cancel_check=cancel_check):
                    yield protocol.done(cancelled=True, text=assembled_text + part_text)
                    return

                now = time.monotonic()
                if (now - last_flush) * 1000 >= flush_interval_ms:
                    yield protocol.meta(kind="keepalive", part_index=part_index)
                    last_flush = now

                delta_text, finish_reason = _extract_choice_fields(chunk)
                if delta_text:
                    part_text += delta_text
                    yield protocol.final_delta(delta_text, part_index=part_index)
                if finish_reason:
                    part_finish_reason = finish_reason
        except Exception as exc:
            yield protocol.error("stream_iteration_failed", detail=str(exc), part_index=part_index)
            yield protocol.done(cancelled=False, text=assembled_text + part_text)
            return

        deduped_part = _dedupe_prefix(assembled_text, part_text)
        assembled_text += deduped_part
        yield protocol.part_done(
            part_index=part_index,
            finish_reason=part_finish_reason,
            part_text=deduped_part,
        )

        if part_finish_reason != "length":
            cleaned = strip_think_blocks(assembled_text)
            summary = _summarize_thinking_if_enabled(
                client=client,
                model=model,
                full_text=assembled_text,
                enable_thinking_summary=enable_thinking_summary,
                timeout=timeout,
            )
            if summary:
                yield protocol.thinking_delta(summary)
            yield protocol.done(cancelled=False, text=cleaned)
            return

        if continuation_budget <= 0:
            cleaned = strip_think_blocks(assembled_text)
            yield protocol.done(cancelled=False, text=cleaned, truncated=True)
            return

        continuation_budget -= 1
        part_index += 1
        base_messages = [
            *base_messages,
            {"role": "assistant", "content": assembled_text},
            {"role": "user", "content": continuation_instruction},
        ]
