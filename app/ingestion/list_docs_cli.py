from __future__ import annotations

import argparse
import json
from typing import Sequence

from app.common.namespaces import validate_namespace
from app.config import runtime_settings as settings
from app.ingestion.doc_registry_store import DocRegistryStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List ingested documents from the registry.")
    parser.add_argument("--namespace", default=None, help="Optional namespace filter.")
    parser.add_argument("--limit", type=int, default=50, help="Max documents to return.")
    parser.add_argument("--cursor", default=None, help="Pagination cursor from prior response.")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    namespace = validate_namespace(args.namespace, default_to_default=True) if args.namespace is not None else None
    store = DocRegistryStore(str(settings.CONFIG.get("doc_registry_path", "data/doc_registry.json")))
    payload = store.list_docs(namespace=namespace, limit=int(args.limit), cursor=args.cursor)
    print(json.dumps({"ok": True, **payload}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
