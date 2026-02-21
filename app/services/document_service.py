from __future__ import annotations

import base64
import json
from typing import Any

from app.repositories.sqlite.documents_repo import DocumentsRepository


def _encode_cursor(updated_at: str, doc_id: str) -> str:
    raw = json.dumps({"updated_at": updated_at, "doc_id": doc_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str | None) -> tuple[str, str] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * ((4 - len(cursor) % 4) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        data = json.loads(payload)
        return str(data["updated_at"]), str(data["doc_id"])
    except Exception as exc:
        raise ValueError("invalid cursor") from exc


class DocumentService:
    def __init__(self, db_path: str) -> None:
        self.repo = DocumentsRepository(db_path)

    def list_documents(
        self,
        namespace: str | None,
        limit: int,
        cursor: str | None,
        include_deleted: bool,
    ) -> dict[str, Any]:
        decoded = _decode_cursor(cursor)
        records = self.repo.list(
            namespace=namespace,
            include_deleted=include_deleted,
            limit=limit,
            cursor=decoded,
        )
        next_cursor = None
        if len(records) == limit and records:
            tail = records[-1]
            next_cursor = _encode_cursor(
                str(tail.get("updated_at") or ""), str(tail.get("doc_id") or "")
            )
        return {
            "records": records,
            "count": len(records),
            "next_cursor": next_cursor,
        }

    def get_document(
        self, namespace: str, doc_id: str, include_deleted: bool = False
    ) -> dict[str, Any] | None:
        return self.repo.get(namespace, doc_id, include_deleted=include_deleted)

    def delete_document(self, namespace: str, doc_id: str, hard_delete: bool = False) -> bool:
        if hard_delete:
            return self.repo.hard_delete(namespace, doc_id)
        return self.repo.soft_delete(namespace, doc_id)

    def bulk_delete(
        self,
        namespace: str | None = None,
        doc_ids: list[str] | None = None,
        hard_delete: bool = False,
        limit: int = 500,
    ) -> dict[str, Any]:
        rows = self.repo.list(namespace=namespace, include_deleted=False, limit=limit)
        if doc_ids:
            selected = [row for row in rows if str(row.get("doc_id")) in set(doc_ids)]
        else:
            selected = rows
        deleted = 0
        for row in selected:
            ns = str(row.get("namespace") or "default")
            doc_id = str(row.get("doc_id") or "")
            if not doc_id:
                continue
            ok = self.delete_document(ns, doc_id, hard_delete=hard_delete)
            if ok:
                deleted += 1
        return {"matched": len(selected), "deleted": deleted, "hard_delete": hard_delete}
