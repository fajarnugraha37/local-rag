from __future__ import annotations

from typing import Any

from app.repositories.sqlite.namespaces_repo import NamespacesRepository


class NamespaceService:
    def __init__(self, db_path: str) -> None:
        self.repo = NamespacesRepository(db_path)

    def list_namespaces(self, include_deleted: bool = False) -> list[dict[str, Any]]:
        return self.repo.list(include_deleted=include_deleted)

    def create_namespace(self, namespace: str, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.repo.create(namespace, defaults=defaults)

    def delete_namespace(self, namespace: str, dry_run: bool = False) -> dict[str, Any]:
        existing = self.repo.get(namespace, include_deleted=True)
        if existing is None:
            return {"namespace": namespace, "deleted": False, "not_found": True, "dry_run": dry_run}
        if dry_run:
            return {
                "namespace": namespace,
                "deleted": False,
                "not_found": False,
                "dry_run": True,
                "would_delete": existing.get("deleted_at") is None,
            }
        deleted = self.repo.soft_delete(namespace)
        return {"namespace": namespace, "deleted": bool(deleted), "not_found": False, "dry_run": False}
