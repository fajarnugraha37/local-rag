"""
chunking.py

Token-aware chunking utilities.

Provides a small, optional-tokenizer-aware chunker that falls back to a
whitespace-based approximation when tiktoken (or another fast tokenizer)
is not available. The goal is to let downstream ingestion pack text by
an estimated token budget with a small overlap between chunks.
"""

import re
import settings
from typing import Callable, List, Optional


def _load_tokenizer(encoding_name: Optional[str] = None) -> Callable[[str], List]:
    """Return a tokenizer callable(text) -> list_of_tokens (or token ids).

    Tries to use tiktoken if available; otherwise falls back to a
    whitespace-based tokenizer that returns words.
    """
    try:
        import tiktoken  # type: ignore

        if encoding_name:
            enc = tiktoken.get_encoding(encoding_name)
        else:
            # cl100k_base is a reasonable default for many modern models
            enc = tiktoken.get_encoding("cl100k_base")

        return lambda text: enc.encode(text)
    except Exception:
        # Fallback: simple whitespace tokenizer
        return lambda text: text.split()


def estimate_token_count(text: Optional[str], tokenizer: Optional[Callable] = None) -> int:
    """Estimate token count for `text` using the provided tokenizer.

    This is intentionally conservative and fast: if a fast tokenizer is not
    available, it falls back to counting whitespace-separated words.
    """
    if not text:
        return 0
    tokenizer = tokenizer or _load_tokenizer()
    try:
        toks = tokenizer(text)
        return len(toks)
    except Exception:
        return len(str(text).split())


def chunk_by_tokens(text: str, max_tokens: int = 200, overlap: int = 20,
                    tokenizer: Optional[Callable] = None) -> List[str]:
    """Split text into chunks aiming for <= max_tokens (estimated).

    - Preserves sentence boundaries where possible (splits on sentence enders).
    - Uses an approximate overlap (in words) when starting a new chunk.
    - If an individual sentence exceeds max_tokens, that sentence is further
      split by words into sub-chunks.

    Returns a list of chunk strings.
    """
    if not text:
        return []

    tokenizer = tokenizer or _load_tokenizer()

    # Allow overriding defaults from config.yaml
    max_tokens = settings.CONFIG.get('chunk_max_tokens', max_tokens)
    overlap = settings.CONFIG.get('chunk_overlap_tokens', overlap)

    # Split by sentence-ish boundaries to keep coherence
    sentences = re.split(r'(?<=[.!?]) +', text)

    chunks: List[str] = []
    cur = ""
    cur_count = 0

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        sent_count = estimate_token_count(sent, tokenizer)

        # If a single sentence is larger than the budget, split it by words
        if sent_count > max_tokens:
            words = sent.split()
            sub = ""
            sub_count = 0
            for w in words:
                w_count = estimate_token_count(w, tokenizer)
                if sub_count + w_count <= max_tokens:
                    sub = (sub + " " + w).strip()
                    sub_count += w_count
                else:
                    # emit previous sub
                    if cur:
                        chunks.append(cur.strip())
                        cur = ""
                        cur_count = 0
                    if sub:
                        chunks.append(sub.strip())
                    sub = w
                    sub_count = w_count
            if sub:
                if cur_count + sub_count <= max_tokens:
                    cur = (cur + " " + sub).strip()
                    cur_count += sub_count
                else:
                    if cur:
                        chunks.append(cur.strip())
                    cur = sub
                    cur_count = sub_count
            continue

        # Normal case: try to append sentence to current chunk
        if cur_count + sent_count <= max_tokens:
            cur = (cur + " " + sent).strip()
            cur_count += sent_count
        else:
            # flush current chunk
            if cur:
                chunks.append(cur.strip())
            # start a new chunk with an approximate overlap (words)
            if overlap > 0 and cur:
                prev_words = cur.split()[-overlap:]
                cur = " ".join(prev_words + [sent]).strip()
                cur_count = estimate_token_count(cur, tokenizer)
            else:
                cur = sent
                cur_count = sent_count

    if cur:
        chunks.append(cur.strip())

    return chunks


__all__ = [
    'estimate_token_count',
    'chunk_by_tokens',
]
