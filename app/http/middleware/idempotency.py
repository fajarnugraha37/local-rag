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
        if cached and not self.repo.is_expired(cached):
            if cached.get("signature") != signature:
                return JSONResponse(
                    status_code=409,
                    content={
                        "ok": False,
                        "error": "idempotency_key_reused_with_different_payload",
                    },
                )
            if cached.get("status") is not None:
                try:
                    payload = json.loads(cached.get("response_body") or "{}")
                except json.JSONDecodeError:
                    payload = {"ok": False, "error": "Invalid cached idempotency payload"}
                return JSONResponse(status_code=int(cached["status"]), content=payload)
            return JSONResponse(
                status_code=409,
                content={"ok": False, "error": "idempotency_key_request_in_progress"},
            )

        if cached and self.repo.is_expired(cached):
            self.repo.delete_expired()

        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)).isoformat()
        self.repo.upsert_pending(
            key=key,
            method=request.method,
            path=request.url.path,
            signature=signature,
            expires_at=expires_at,
        )

        response = await call_next(request)
        if isinstance(response, Response) and not response.headers.get(
            "content-type", ""
        ).startswith("text/event-stream"):
            body_bytes = b""
            if hasattr(response, "body") and response.body is not None:
                body_bytes = response.body
            else:
                chunks = []
                async for chunk in response.body_iterator:
                    chunks.append(chunk)
                body_bytes = b"".join(chunks)
                response = Response(
                    content=body_bytes,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                    background=response.background,
                )
            body_text = body_bytes.decode("utf-8", errors="replace")
            self.repo.set_response(
                key=key,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                response_body=body_text,
            )
        response.headers["X-Idempotency-Recorded-At"] = _utc_now_iso()
        return response
