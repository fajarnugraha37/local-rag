"""
context_packer.py

Token-budget context packer utilities.

Selects and (optionally) truncates retrieved chunks so the total estimated
token count stays within a provided budget. Assumes candidate chunks are
ordered by relevance (most relevant first).
"""

from typing import List, Optional
from app.config import runtime_settings as settings
from app.context.token_chunking import estimate_token_count, chunk_by_tokens


def pack_context(query: str, chunks: List[str], tokenizer=None, max_tokens: Optional[int] = None, overlap_tokens: int = 20) -> List[str]:
    """Pack `chunks` (list of strings) into a list whose total estimated token
    count does not exceed `max_tokens`.

    - If `max_tokens` is None, falls back to settings.CONFIG['context_token_budget'] or 1500.
    - If the first candidate chunk is larger than the budget, returns a truncated
      sub-chunk produced by chunk_by_tokens() so at least some context is provided.
    """
    if not chunks:
        return []

    if max_tokens is None:
        max_tokens = settings.CONFIG.get('context_token_budget', 1500)

    selected: List[str] = []
    total_tokens = 0

    for chunk in chunks:
        tok = estimate_token_count(chunk, tokenizer)
        # if it fits, take it
        if total_tokens + tok <= max_tokens:
            selected.append(chunk)
            total_tokens += tok
            continue

        # doesn't fit
        if not selected:
            # try to split the large chunk and take the first piece
            subchunks = chunk_by_tokens(chunk, max_tokens=max_tokens, overlap=overlap_tokens, tokenizer=tokenizer)
            if subchunks:
                chosen = subchunks[0]
                selected.append(chosen)
                total_tokens += estimate_token_count(chosen, tokenizer)
        break

    return selected


__all__ = ["pack_context"]
