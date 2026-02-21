import hashlib
import unicodedata
import re
from typing import List, Tuple, Dict, Any


def normalize_text(text: str) -> str:
    """Normalize text for stable hashing: unicode NFKC, collapse whitespace, strip."""
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = text.strip()
    # Collapse any whitespace (spaces, newlines, tabs) to single space
    text = re.sub(r"\s+", " ", text)
    return text


def sha256_hash(text: str) -> str:
    """Return hex sha256 of normalized text."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def dedupe_chunks(chunks: List[Any], text_key: str = "text") -> Tuple[List[Any], Dict[str, int]]:
    """Deduplicate chunks by content hash.

    Args:
        chunks: list of strings or dict-like objects containing text under text_key.
    Returns:
        unique_chunks: list preserving first occurrence. If items are dicts and lack 'chunk_id', a chunk_id==hash is added.
        hash_index: mapping from hash to index in unique_chunks.
    """
    seen: Dict[str, int] = {}
    unique: List[Any] = []

    for item in chunks:
        if isinstance(item, str):
            text = item
            obj = None
        elif isinstance(item, dict):
            text = item.get(text_key, "")
            obj = dict(item)  # shallow copy to avoid mutating input
        else:
            text = str(item)
            obj = None

        h = sha256_hash(text)
        if h in seen:
            continue
        seen[h] = len(unique)
        if obj is None:
            unique.append(text)
        else:
            if "chunk_id" not in obj:
                obj["chunk_id"] = h
            unique.append(obj)

    return unique, seen


__all__ = ["normalize_text", "sha256_hash", "dedupe_chunks"]
