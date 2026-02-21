from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.repositories.sqlite.idempotency_repo import IdempotencyRepository


def _expires_at(ttl_seconds: int) -> str:
    ttl = max(1, int(ttl_seconds))
    return (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()


def build_signature(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_idempotency_key(*, operation: str, payload: dict[str, Any]) -> str:
    signature = build_signature(payload)
    prefix = operation.strip().lower().replace(" ", "-")
    return f"{prefix}:{signature[:24]}"


def replay_response(
    repo: IdempotencyRepository,
    *,
    key: str,
    method: str,
    path: str,
    signature: str,
) -> dict[str, Any] | None:
    row = repo.get(key=key, method=method, path=path)
    if not row:
        return None
    if repo.is_expired(row):
        return None
    if str(row.get("signature") or "") != signature:
        return None
    body = row.get("response_body")
    if not body:
        return None
    try:
        return json.loads(str(body))
    except Exception:
        return None


def record_pending(
    repo: IdempotencyRepository,
    *,
    key: str,
    method: str,
    path: str,
    signature: str,
    ttl_seconds: int,
) -> None:
    repo.upsert_pending(
        key=key,
        method=method,
        path=path,
        signature=signature,
        expires_at=_expires_at(ttl_seconds),
    )


def record_response(
    repo: IdempotencyRepository,
    *,
    key: str,
    method: str,
    path: str,
    response: dict[str, Any],
    status: int = 200,
) -> None:
    repo.set_response(
        key=key,
        method=method,
        path=path,
        status=status,
        response_body=json.dumps(response, ensure_ascii=True, sort_keys=True),
    )


def execute_with_idempotency(
    *,
    repo: IdempotencyRepository,
    key: str,
    method: str,
    path: str,
    signature: str,
    ttl_seconds: int,
    fn: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    cached = replay_response(repo, key=key, method=method, path=path, signature=signature)
    if cached is not None:
        return cached, True
    record_pending(
        repo,
        key=key,
        method=method,
        path=path,
        signature=signature,
        ttl_seconds=ttl_seconds,
    )
    response = fn()
    record_response(repo, key=key, method=method, path=path, response=response, status=200)
    return response, False
