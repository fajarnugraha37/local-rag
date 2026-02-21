from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.common.namespaces import validate_namespace
from app.config import runtime_settings as settings
from app.http.schemas.ingestions import IngestionCreateRequest
from app.services.ingestion_service import IngestionService, UploadPayload

router = APIRouter(prefix="/v1/ingestions", tags=["ingestions"])


def _db_path() -> str:
    return str(settings.CONFIG.get("sqlite_db_path") or "data/app.db")


def _service() -> IngestionService:
    return IngestionService(_db_path())


@router.post("")
def create_ingestion(body: IngestionCreateRequest) -> dict:
    ns = validate_namespace(body.namespace, default_to_default=True)
    record = _service().create_job(
        namespace=ns,
        source_type=body.source_type,
        source_spec=body.source_spec,
    )
    return {"ok": True, "ingestion_id": record["ingestion_id"], "record": record}


@router.post("/upload")
async def create_upload_ingestion(request: Request) -> dict:
    form = await request.form()
    files: list[tuple[str, bytes]] = []
    fields: dict[str, str] = {}
    for key, value in form.multi_items():
        if hasattr(value, "filename") and hasattr(value, "read"):
            if key == "file" and getattr(value, "filename", None):
                files.append((str(value.filename), await value.read()))
        else:
            fields[key] = str(value)
    if not files:
        return {"ok": False, "error": "No file uploads provided under form field 'file'"}

    ns = validate_namespace(fields.get("namespace"), default_to_default=True)
    source_spec = {"embedding_model": fields.get("embedding_model")}
    record = _service().create_job(
        namespace=ns,
        source_type="upload",
        source_spec=source_spec,
        upload_payload=UploadPayload(files=files, fields=fields),
    )
    return {"ok": True, "ingestion_id": record["ingestion_id"], "record": record}


@router.get("")
def list_ingestions(
    namespace: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=500)
) -> dict:
    ns = validate_namespace(namespace, default_to_default=True) if namespace else None
    rows = _service().list_jobs(namespace=ns, limit=limit)
    return {"ok": True, "records": rows, "count": len(rows)}


@router.get("/{ingestion_id}")
def get_ingestion(ingestion_id: str) -> dict:
    record = _service().get_job(ingestion_id)
    if record is None:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "record": record}


@router.get("/{ingestion_id}/events")
def get_ingestion_events(ingestion_id: str, limit: int = Query(default=500, ge=1, le=2000)) -> dict:
    events = _service().list_events(ingestion_id, limit=limit)
    return {"ok": True, "events": events, "count": len(events)}


@router.post("/{ingestion_id}/cancel")
def cancel_ingestion(ingestion_id: str) -> dict:
    cancel_requested = _service().cancel_job(ingestion_id)
    return {"ok": True, "ingestion_id": ingestion_id, "cancel_requested": bool(cancel_requested)}
