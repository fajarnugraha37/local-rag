from __future__ import annotations

from fastapi import APIRouter, Query

from app.common.namespaces import validate_namespace
from app.config import runtime_settings as settings
from app.http.schemas.documents import DocumentsBulkDeleteRequest
from app.services.document_service import DocumentService

router = APIRouter(prefix="/v1/documents", tags=["documents"])


def _db_path() -> str:
    return str(settings.CONFIG.get("sqlite_db_path") or "data/app.db")


@router.get("")
def list_documents(
    namespace: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> dict:
    resolved_namespace = (
        validate_namespace(namespace, default_to_default=True) if namespace is not None else None
    )
    svc = DocumentService(_db_path())
    payload = svc.list_documents(
        namespace=resolved_namespace,
        limit=limit,
        cursor=cursor,
        include_deleted=include_deleted,
    )
    return {"ok": True, **payload}


@router.get("/{namespace}/{doc_id}")
def get_document(namespace: str, doc_id: str, include_deleted: bool = Query(default=False)) -> dict:
    resolved = validate_namespace(namespace, default_to_default=False)
    svc = DocumentService(_db_path())
    row = svc.get_document(resolved, doc_id, include_deleted=include_deleted)
    if row is None:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "record": row}


@router.delete("/{namespace}/{doc_id}")
def delete_document(
    namespace: str,
    doc_id: str,
    hard_delete: bool = Query(default=False),
) -> dict:
    resolved = validate_namespace(namespace, default_to_default=False)
    svc = DocumentService(_db_path())
    deleted = svc.delete_document(resolved, doc_id, hard_delete=hard_delete)
    return {
        "ok": True,
        "namespace": resolved,
        "doc_id": doc_id,
        "deleted": bool(deleted),
        "hard_delete": bool(hard_delete),
    }


@router.post(":bulk_delete")
def bulk_delete_documents(body: DocumentsBulkDeleteRequest) -> dict:
    resolved_namespace = (
        validate_namespace(body.namespace, default_to_default=True)
        if body.namespace is not None
        else None
    )
    svc = DocumentService(_db_path())
    payload = svc.bulk_delete(
        namespace=resolved_namespace,
        doc_ids=body.doc_ids,
        hard_delete=body.hard_delete,
        limit=body.limit,
    )
    return {"ok": True, **payload}
