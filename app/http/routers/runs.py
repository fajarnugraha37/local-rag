from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.config import runtime_settings as settings
from app.http.sse import to_sse
from app.services.run_service import RunService

router = APIRouter(prefix="/v1/runs", tags=["runs"])


def _db_path() -> str:
    return str(settings.CONFIG.get("sqlite_db_path") or "data/app.db")


def _svc() -> RunService:
    return RunService(_db_path())


@router.get("/{run_id}")
def get_run(run_id: str) -> dict:
    record = _svc().get_run(run_id)
    if record is None:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "record": record}


@router.get("/{run_id}/steps")
def get_run_steps(run_id: str) -> dict:
    return {"ok": True, "steps": _svc().get_steps(run_id)}


@router.get("/{run_id}/events")
def get_run_events(run_id: str, limit: int = Query(default=1000, ge=1, le=5000)) -> dict:
    events = _svc().get_events(run_id, limit=limit)
    return {"ok": True, "events": events, "count": len(events)}


@router.get("/{run_id}/replay")
def replay_run_events(run_id: str, limit: int = Query(default=1000, ge=1, le=5000)) -> StreamingResponse:
    events = _svc().get_events(run_id, limit=limit)

    def event_iter():
        for row in events:
            yield to_sse(str(row.get("event") or "message"), row.get("payload") or {})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "close",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_iter(), media_type="text/event-stream; charset=utf-8", headers=headers)
