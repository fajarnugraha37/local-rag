from __future__ import annotations

from fastapi import APIRouter, Query

from app.common.namespaces import validate_namespace
from app.config import runtime_settings as settings
from app.http.request_parsing import parse_bool
from app.http.schemas.namespaces import NamespaceCreateRequest
from app.services.namespace_service import NamespaceService

router = APIRouter(prefix="/v1/namespaces", tags=["namespaces"])


def _db_path() -> str:
    return str(settings.CONFIG.get("sqlite_db_path") or "data/app.db")


@router.get("")
def list_namespaces(include_deleted: bool = Query(default=False)) -> dict:
    svc = NamespaceService(_db_path())
    rows = svc.list_namespaces(include_deleted=include_deleted)
    return {"ok": True, "records": rows, "count": len(rows)}


@router.post("")
def create_namespace(body: NamespaceCreateRequest) -> dict:
    namespace = validate_namespace(body.namespace, default_to_default=False)
    svc = NamespaceService(_db_path())
    created = svc.create_namespace(namespace, defaults=body.defaults)
    return {"ok": True, "record": created}


@router.delete("/{namespace}")
def delete_namespace(namespace: str, dry_run: str | bool = Query(default=False)) -> dict:
    resolved = validate_namespace(namespace, default_to_default=False)
    run_dry = parse_bool(dry_run, default=False)
    svc = NamespaceService(_db_path())
    payload = svc.delete_namespace(resolved, dry_run=run_dry)
    return {"ok": True, **payload}
