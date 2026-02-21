from __future__ import annotations

import json


def to_sse(event_name: str, payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_name}\ndata: {body}\n\n".encode("utf-8")
