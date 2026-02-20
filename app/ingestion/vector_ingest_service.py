from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional

from app.config import runtime_settings as settings
from app.indexing.embedding_service import embed_text
from app.storage.chroma_vector_store import ChromaVectorStore
from app.storage.vector_ids import chunk_id as stable_chunk_id
from app.storage.vector_ids import doc_id as stable_doc_id
from app.storage.vector_ids import vector_id as stable_vector_id


def _resolve_doc_id(source_path: Optional[str], explicit_doc_id: Optional[str] = None) -> str:
    if explicit_doc_id:
        return str(explicit_doc_id)
    if source_path:
        return os.path.basename(source_path)
    return "unknown"


def ingest_chunks(
    chunks_list: Iterable[str],
    *,
    source_path: Optional[str] = None,
    doc_id: Optional[str] = None,
    embedding_model: Optional[str] = None,
    store: Optional[ChromaVectorStore] = None,
) -> Dict[str, int]:
    """Chunk -> embed -> upsert to vector DB."""
    resolved_doc_id = _resolve_doc_id(source_path, explicit_doc_id=doc_id)
    resolved_doc_key = stable_doc_id(resolved_doc_id)
    batch_size = int(settings.CONFIG.get("vector_db_batch_size", 64))

    vector_store = store or ChromaVectorStore()

    added = 0
    skipped = 0
    failed = 0
    batch: List[Dict[str, object]] = []

    for raw_chunk in chunks_list:
        text = (raw_chunk or "").strip()
        if not text:
            skipped += 1
            continue

        emb_info = embed_text(text, embedding_model=embedding_model, allow_fallback=True)
        emb = emb_info.get("embedding")
        if emb is None:
            failed += 1
            continue

        chunk_key = stable_chunk_id(text)
        v_id = stable_vector_id(resolved_doc_key, chunk_key)

        batch.append(
            {
                "id": v_id,
                "embedding": emb,
                "text": text,
                "metadata": {
                    "doc_id": resolved_doc_id,
                    "doc_key": resolved_doc_key,
                    "chunk_id": chunk_key,
                    "source": source_path or "",
                    "token_count": len(text.split()),
                },
            }
        )

        if len(batch) >= batch_size:
            added += vector_store.upsert(batch)
            batch = []

    if batch:
        added += vector_store.upsert(batch)

    return {"added": added, "skipped": skipped, "failed": failed}


def delete_doc(doc_id: str, *, store: Optional[ChromaVectorStore] = None) -> int:
    vector_store = store or ChromaVectorStore()
    return vector_store.delete_by_doc_id(doc_id)


__all__ = ["ingest_chunks", "delete_doc"]
