"""
reranker.py

Cheap heuristic reranker for retrieval results.

This module provides a small, fast reranker that re-scores retrieval outputs
by combining normalized dense and BM25 scores with a token-overlap heuristic
and a lightweight length-based bonus. It's intentionally simple and
configurable via weights passed to `rerank()`.
"""

import math
import re
from typing import List, Dict, Any, Optional


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


def term_overlap_score(query: str, text: str) -> float:
    """Return fraction of unique query tokens that appear in text (0..1)."""
    q = _tokenize(query)
    if not q:
        return 0.0
    qset = set(q)
    tset = set(_tokenize(text))
    return len(qset & tset) / max(1.0, len(qset))


def _normalize_list(values: List[float]) -> List[float]:
    if not values:
        return []
    try:
        mn = min(values)
        mx = max(values)
    except Exception:
        return [0.0 for _ in values]
    if mx == mn:
        return [0.0 for _ in values]
    return [(v - mn) / (mx - mn) for v in values]


def rerank(results: List[Dict[str, Any]], query: str,
           weights: Optional[Dict[str, float]] = None,
           top_k: Optional[int] = None) -> List[Dict[str, Any]]:
    """Rerank `results` (list of dicts) given `query`.

    Expected keys in each result dict: 'dense_score', 'bm25_score', 'text',
    optionally 'token_count'. The function attaches 'rerank_score' and
    'rerank_rank' to each returned item and returns them sorted.

    weights: dict with optional keys 'dense', 'bm25', 'overlap', 'length'.
    Defaults chosen to give sensible emphasis to dense+bm25 and overlap.
    """
    if not results:
        return []
    weights = weights or {'dense': 1.0, 'bm25': 1.0, 'overlap': 0.8, 'length': 0.1}

    dense_vals = [float(r.get('dense_score') or 0.0) for r in results]
    bm25_vals = [float(r.get('bm25_score') or 0.0) for r in results]
    norm_dense = _normalize_list(dense_vals)
    norm_bm25 = _normalize_list(bm25_vals)

    overlaps = [term_overlap_score(query, r.get('text', '')) for r in results]

    token_counts: List[int] = []
    for r in results:
        tc = r.get('token_count')
        if tc is None:
            tc = len(_tokenize(r.get('text', '')))
        try:
            tc = max(1, int(tc))
        except Exception:
            tc = max(1, len(_tokenize(r.get('text', ''))))
        token_counts.append(tc)

    # shorter chunks get slightly higher length score (1/(1+log(tokens)))
    length_vals = [1.0 / (1.0 + math.log(1 + tc)) for tc in token_counts]
    norm_length = _normalize_list(length_vals)

    scores: List[float] = []
    for i, _ in enumerate(results):
        s = (
            weights.get('dense', 0.0) * (norm_dense[i] if i < len(norm_dense) else 0.0) +
            weights.get('bm25', 0.0) * (norm_bm25[i] if i < len(norm_bm25) else 0.0) +
            weights.get('overlap', 0.0) * (overlaps[i] if i < len(overlaps) else 0.0) +
            weights.get('length', 0.0) * (norm_length[i] if i < len(norm_length) else 0.0)
        )
        scores.append(s)

    norm_scores = _normalize_list(scores)

    for i, r in enumerate(results):
        # prefer the normalized final score for human-meaningful range
        r['rerank_score'] = float(norm_scores[i]) if norm_scores else float(scores[i])

    results_sorted = sorted(results, key=lambda x: x.get('rerank_score', 0.0), reverse=True)

    if top_k is not None:
        results_sorted = results_sorted[:top_k]

    for idx, item in enumerate(results_sorted, start=1):
        item['rerank_rank'] = idx

    return results_sorted


__all__ = ['rerank']
