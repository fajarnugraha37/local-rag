from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.repositories.sqlite.idempotency_repo import IdempotencyRepository


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Cache responses for duplicate mutating requests with same idempotency key."""

    def __init__(self, app, repo: IdempotencyRepository, ttl_seconds: int = 24 * 3600) -> None:
        super().__init__(app)
        self.repo = repo
        self.ttl_seconds = ttl_seconds

    async def dispatch(self, request: Request, call_next):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)

        body_bytes = await request.body()
        signature = hashlib.sha256(body_bytes).hexdigest()

        cached = self.repo.get(key=key, method=request.method, path=request.url.path)
        if cached and cached.get("signature") == signature and cached.get("status") is not None:
            try:
                payload = json.loads(cached.get("response_body") or "{}")
            except json.JSONDecodeError:
                payload = {"ok": False, "error": "Invalid cached idempotency payload"}
            return JSONResponse(status_code=int(cached["status"]), content=payload)

        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)).isoformat()
        self.repo.upsert_pending(
            key=key,
            method=request.method,
            path=request.url.path,
            signature=signature,
            expires_at=expires_at,
        )

        response = await call_next(request)
        if isinstance(response, Response) and not response.headers.get("content-type", "").startswith(
            "text/event-stream"
        ):
            if hasattr(response, "body") and response.body is not None:
                body_text = response.body.decode("utf-8", errors="replace")
                self.repo.set_response(
                    key=key,
                    method=request.method,
                    path=request.url.path,
                    status=response.status_code,
                    response_body=body_text,
                )
        response.headers["X-Idempotency-Recorded-At"] = _utc_now_iso()
        return response
