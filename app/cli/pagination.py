from __future__ import annotations

import base64
import json
from typing import Any


def encode_cursor(*, updated_at: str, doc_id: str) -> str:
    raw = json.dumps({"updated_at": updated_at, "doc_id": doc_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str | None) -> tuple[str, str] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * ((4 - len(cursor) % 4) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        data: dict[str, Any] = json.loads(payload)
        return str(data["updated_at"]), str(data["doc_id"])
    except Exception as exc:
        raise ValueError("invalid cursor") from exc


def normalize_limit(limit: int, *, min_value: int = 1, max_value: int = 500) -> int:
    value = int(limit)
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value

