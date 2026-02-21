from __future__ import annotations

import argparse
import json
from typing import Sequence

from app.common.namespaces import validate_namespace
from app.config import runtime_settings as settings
from app.ingestion.doc_registry_store import DocRegistryStore
from app.ingestion.vector_ingest_service import delete_doc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete ingested document vectors and registry records."
    )
    parser.add_argument("--doc-id", required=True, help="Document ID to delete.")
    parser.add_argument(
        "--namespace", default=None, help="Namespace to delete from (default: default)."
    )
    parser.add_argument(
        "--all-namespaces",
        action="store_true",
        help="Delete this doc_id across all namespaces.",
    )
    return parser


def _delete_registry_records(
    store: DocRegistryStore, doc_id: str, namespace: str | None, all_namespaces: bool
) -> int:
    deleted = 0
    if all_namespaces:
        page = store.list_docs(limit=100000)
        for row in page.get("records", []):
            if str(row.get("doc_id")) != str(doc_id):
                continue
            if store.delete(str(row.get("namespace")), str(doc_id)):
                deleted += 1
        return deleted
    resolved_ns = validate_namespace(namespace, default_to_default=True)
    return 1 if store.delete(resolved_ns, str(doc_id)) else 0


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    namespace = (
        None if args.all_namespaces else validate_namespace(args.namespace, default_to_default=True)
    )

    vectors_deleted = delete_doc(
        str(args.doc_id),
        namespace=namespace,
        all_namespaces=bool(args.all_namespaces),
    )
    registry_store = DocRegistryStore(
        str(settings.CONFIG.get("doc_registry_path", "data/doc_registry.json"))
    )
    registry_deleted = _delete_registry_records(
        registry_store,
        doc_id=str(args.doc_id),
        namespace=namespace,
        all_namespaces=bool(args.all_namespaces),
    )
    if registry_deleted > 0:
        registry_store.save()
    print(
        json.dumps(
            {
                "ok": True,
                "doc_id": str(args.doc_id),
                "namespace": namespace,
                "all_namespaces": bool(args.all_namespaces),
                "vectors_deleted": int(vectors_deleted),
                "registry_deleted": int(registry_deleted),
                "not_found": (vectors_deleted == 0 and registry_deleted == 0),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
