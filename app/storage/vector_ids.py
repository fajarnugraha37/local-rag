import hashlib

from app.common.content_hashing import sha256_hash


def doc_id(source: str) -> str:
    """Return a deterministic document ID from source identity."""
    return sha256_hash(source or '')


def chunk_id(text: str) -> str:
    """Return a deterministic chunk ID from chunk text."""
    return sha256_hash(text or '')


def vector_id(doc_id_value: str, chunk_id_value: str) -> str:
    """Return deterministic vector ID as sha256(doc_id + ':' + chunk_id)."""
    raw = f"{doc_id_value}:{chunk_id_value}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


__all__ = ['doc_id', 'chunk_id', 'vector_id']
