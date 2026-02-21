from __future__ import annotations

import json
from typing import Any


def format_event_line(event: dict[str, Any]) -> str:
    ts = str(event.get("ts") or "")
    name = str(event.get("event") or "")
    payload = event.get("payload") or {}
    payload_json = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    return f"{ts}  {name}  {payload_json}"


def render_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "(no events)"
    return "\n".join(format_event_line(item) for item in events)

