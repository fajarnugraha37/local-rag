from __future__ import annotations

import argparse
import os
from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from app.common.content_hashing import sha256_hash
from app.common.namespaces import DEFAULT_NAMESPACE, validate_namespace
from app.config import runtime_settings as settings
from app.ingestion.doc_registry_store import DocRegistryStore
from app.storage.chroma_vector_store import ChromaVectorStore


def backfill_namespaces(*, batch_size: int = 500) -> Dict[str, int]:
    store = ChromaVectorStore()
    registry = DocRegistryStore(
        str(settings.CONFIG.get("doc_registry_path", "data/doc_registry.json"))
    )

    total = store.count()
    offset = 0
    scanned = 0
    updated_vectors = 0

    # Aggregate docs for registry rebuild from vector metadata/documents.
    docs_agg: Dict[Tuple[str, str], Dict[str, object]] = defaultdict(
        lambda: {
            "source_path": "",
            "source_type": "file",
            "title": "",
            "chunk_count": 0,
            "size_bytes": 0,
            "texts": [],
            "last_ingested_at": "",
        }
    )

    while offset < total:
        page = store.get_page(offset=offset, limit=batch_size)
        ids = page["ids"]
        metadatas = page["metadatas"]
        documents = page["documents"]
        if not ids:
            break
        scanned += len(ids)

        to_update_ids: List[str] = []
        to_update_metas: List[Dict[str, object]] = []

        for idx, vector_id in enumerate(ids):
            metadata = dict((metadatas[idx] if idx < len(metadatas) else {}) or {})
            document = str(documents[idx] if idx < len(documents) else "")

            namespace_raw = metadata.get("namespace")
            if namespace_raw is None or not str(namespace_raw).strip():
                namespace = DEFAULT_NAMESPACE
                metadata["namespace"] = namespace
                to_update_ids.append(str(vector_id))
                to_update_metas.append(metadata)
            else:
                namespace = validate_namespace(str(namespace_raw), default_to_default=True)
                metadata["namespace"] = namespace

            doc_id = str(metadata.get("doc_id") or "").strip()
            if not doc_id:
                continue
            key = (namespace, doc_id)
            agg = docs_agg[key]
            agg["chunk_count"] = int(agg["chunk_count"]) + 1
            agg["source_path"] = str(metadata.get("source") or agg["source_path"] or "")
            agg["title"] = str(
                agg["title"] or os.path.basename(str(metadata.get("source") or "")) or doc_id
            )
            agg["size_bytes"] = int(agg["size_bytes"]) + len(document.encode("utf-8"))
            agg["texts"].append(document)

        if to_update_ids:
            updated_vectors += store.update_metadatas(to_update_ids, to_update_metas)

        offset += len(ids)

    upserted_docs = 0
    for (namespace, doc_id), agg in docs_agg.items():
        texts = [str(item) for item in agg["texts"] if str(item).strip()]
        combined = "\n".join(texts)
        registry.upsert(
            namespace=namespace,
            doc_id=doc_id,
            source_path=str(agg["source_path"]),
            source_type="file",
            title=str(agg["title"] or doc_id),
            content_hash=sha256_hash(combined) if combined else "",
            chunk_count=int(agg["chunk_count"]),
            size_bytes=int(agg["size_bytes"]),
            tags=[],
            last_ingested_at=None,
        )
        upserted_docs += 1
    if upserted_docs > 0:
        registry.save()

    return {
        "scanned_vectors": scanned,
        "updated_vectors": updated_vectors,
        "upserted_docs": upserted_docs,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill namespace metadata and doc registry from existing vectors."
    )
    parser.add_argument(
        "--batch-size", type=int, default=500, help="Batch size for scanning/updating vector rows."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    summary = backfill_namespaces(batch_size=max(1, int(args.batch_size)))
    print(
        "Backfill complete: "
        f"scanned_vectors={summary['scanned_vectors']} "
        f"updated_vectors={summary['updated_vectors']} "
        f"upserted_docs={summary['upserted_docs']}"
    )


if __name__ == "__main__":
    main()
