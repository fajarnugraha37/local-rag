from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, List, Optional

from app.config import runtime_settings as settings
from app.embeddings.service import embed_text
from app.storage.chroma_vector_store import ChromaVectorStore
from app.storage.vector_ids import chunk_id as stable_chunk_id
from app.storage.vector_ids import doc_id as stable_doc_id
from app.storage.vector_ids import vector_id as stable_vector_id


def _load_chunks(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
    return out


def _load_embeddings_map(
    path: Optional[str], embedding_model: Optional[str]
) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = {}
    if not path or not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            if (
                embedding_model
                and obj.get("embedding_model")
                and obj.get("embedding_model") != embedding_model
            ):
                continue
            cid = obj.get("chunk_id")
            emb = obj.get("embedding")
            if isinstance(cid, str) and isinstance(emb, list) and emb:
                out[cid] = emb
    return out


def _upsert_with_retries(
    store: ChromaVectorStore,
    items: List[Dict[str, Any]],
    retries: int,
    retry_delay_s: float,
) -> bool:
    attempts = max(1, retries + 1)
    for attempt in range(1, attempts + 1):
        try:
            store.upsert(items)
            return True
        except Exception as e:
            if attempt >= attempts:
                print(f"[backfill] batch upsert failed after {attempt} attempts: {e}")
                return False
            print(f"[backfill] batch upsert failed (attempt {attempt}/{attempts}), retrying: {e}")
            time.sleep(retry_delay_s)
    return False


def backfill(
    chunks_file: Optional[str],
    embeddings_file: Optional[str],
    batch_size: int,
    embedding_model: Optional[str],
    retries: int,
    retry_delay_s: float,
) -> Dict[str, int]:
    if not chunks_file:
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        chunks_file = os.path.join(repo_dir, "data", "chunks.jsonl")
    store = ChromaVectorStore()
    chunks = _load_chunks(chunks_file)
    precomputed = _load_embeddings_map(embeddings_file, embedding_model)

    print(
        f"[backfill] starting: chunks={len(chunks)} "
        f"precomputed_embeddings={len(precomputed)} "
        f"batch_size={batch_size}"
    )

    seen_vector_ids = set()
    batch: List[Dict[str, Any]] = []
    migrated = 0
    skipped = 0
    errors = 0

    for idx, obj in enumerate(chunks, start=1):
        text = str(obj.get("text", "")).strip()
        if not text:
            skipped += 1
            continue

        raw_doc_id = str(
            obj.get("doc_id")
            or (os.path.basename(str(obj.get("source"))) if obj.get("source") else "unknown")
        )
        chunk_key = str(obj.get("chunk_id") or stable_chunk_id(text))
        doc_key = stable_doc_id(raw_doc_id)
        vec_id = stable_vector_id(doc_key, chunk_key)
        if vec_id in seen_vector_ids:
            skipped += 1
            continue
        seen_vector_ids.add(vec_id)

        emb = precomputed.get(chunk_key)
        if emb is None:
            emb_info = embed_text(text, embedding_model=embedding_model, allow_fallback=True)
            emb = emb_info.get("embedding")
        if emb is None:
            errors += 1
            continue
        if len(emb) != store.embedding_dim:
            errors += 1
            continue

        batch.append(
            {
                "id": vec_id,
                "embedding": emb,
                "text": text,
                "metadata": {
                    "doc_id": raw_doc_id,
                    "doc_key": doc_key,
                    "chunk_id": chunk_key,
                    "source": str(obj.get("source", "")),
                    "token_count": int(obj.get("token_count") or len(text.split())),
                },
            }
        )

        if len(batch) >= batch_size:
            ok = _upsert_with_retries(store, batch, retries=retries, retry_delay_s=retry_delay_s)
            if ok:
                migrated += len(batch)
            else:
                errors += len(batch)
            print(
                f"[backfill] progress: processed={idx}/{len(chunks)} "
                f"migrated={migrated} skipped={skipped} errors={errors}"
            )
            batch = []

    if batch:
        ok = _upsert_with_retries(store, batch, retries=retries, retry_delay_s=retry_delay_s)
        if ok:
            migrated += len(batch)
        else:
            errors += len(batch)

    summary = {
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "vector_count": store.count(),
    }
    print(f"[backfill] done: {summary}")
    return summary


def main() -> None:
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    default_chunks = os.path.join(repo_dir, "data", "chunks.jsonl")
    default_embeddings = os.path.join(repo_dir, "data", "embeddings.jsonl")

    parser = argparse.ArgumentParser(description="Backfill legacy JSONL chunks into vector DB")
    parser.add_argument("--chunks-file", default=default_chunks, help="Path to legacy chunks.jsonl")
    parser.add_argument(
        "--embeddings-file",
        default=default_embeddings,
        help="Optional path to legacy embeddings.jsonl (if missing, embeddings are generated)",
    )
    parser.add_argument("--batch-size", type=int, default=64, help="Upsert batch size")
    parser.add_argument(
        "--embedding-model",
        default=settings.CONFIG.get("embedding_model", "mxbai-embed-large"),
        help="Embedding model name for generated embeddings",
    )
    parser.add_argument("--retries", type=int, default=2, help="Retries per batch on failure")
    parser.add_argument("--retry-delay-s", type=float, default=0.5, help="Delay between retries")
    args = parser.parse_args()

    backfill(
        chunks_file=args.chunks_file,
        embeddings_file=args.embeddings_file,
        batch_size=max(1, int(args.batch_size)),
        embedding_model=args.embedding_model,
        retries=max(0, int(args.retries)),
        retry_delay_s=max(0.0, float(args.retry_delay_s)),
    )
