"""Hybrid retrieval utilities backed by persistent vector DB (Chroma)."""

from __future__ import annotations

import json
import math
import re
import argparse
from typing import List, Dict, Any, Optional, Tuple, Iterable
from collections import defaultdict

from app.common.namespaces import coerce_namespace, merge_namespace_filters
from app.config import runtime_settings as settings
from app.embeddings.service import embed_text
from app.retrieval import heuristic_reranker as reranker
from app.retrieval.provenance import (
    assign_source_indices,
    normalize_locator,
    normalize_snippet,
    normalize_title,
)
from app.storage.chroma_vector_store import ChromaVectorStore

# --- Text tokenization (simple, used for BM25) ---
def tokenize(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


# --- Simple BM25 implementation ---
class BM25:
    def __init__(self, docs: List[str], tokenizer=tokenize, k1: float = 1.5, b: float = 0.75):
        self.tokenizer = tokenizer
        self.docs_tokens = [tokenizer(d) for d in docs]
        self.N = len(self.docs_tokens)
        self.k1 = k1
        self.b = b
        self.doc_len = [len(toks) for toks in self.docs_tokens]
        self.avgdl = sum(self.doc_len) / self.N if self.N > 0 else 0.0

        # term frequencies per doc and document frequencies
        self.tf: List[Dict[str, int]] = []
        self.df: Dict[str, int] = defaultdict(int)

        for toks in self.docs_tokens:
            freqs: Dict[str, int] = defaultdict(int)
            seen = set()
            for t in toks:
                freqs[t] += 1
                if t not in seen:
                    self.df[t] += 1
                    seen.add(t)
            self.tf.append(freqs)

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        # add-one smoothing and +1 to avoid negative idf
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1)

    def score(self, query: str) -> List[float]:
        q_terms = self.tokenizer(query)
        scores = [0.0] * self.N
        for term in q_terms:
            idf = self._idf(term)
            for i in range(self.N):
                tf = self.tf[i].get(term, 0)
                if tf == 0:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * (self.doc_len[i] / (self.avgdl or 1.0)))
                score = idf * (tf * (self.k1 + 1)) / denom
                scores[i] += score
        return scores

    def top_n(self, query: str, n: int = 10) -> List[Tuple[int, float]]:
        scores = self.score(query)
        indexed = [(i, s) for i, s in enumerate(scores) if s > 0]
        indexed.sort(key=lambda x: x[1], reverse=True)
        return indexed[:n]


def get_query_embedding(text: str, embedding_model: Optional[str] = None) -> Optional[List[float]]:
    info = embed_text(text, embedding_model=embedding_model, allow_fallback=False)
    return info.get('embedding')


# --- RRF merging ---
def rrf_merge(ranked_lists: List[List[str]], top_k: int = 10, k: int = 60, weights: Optional[List[float]] = None) -> List[Tuple[str, float]]:
    scores: Dict[str, float] = defaultdict(float)
    weights = weights or [1.0] * len(ranked_lists)
    for i, rlist in enumerate(ranked_lists):
        w = weights[i] if i < len(weights) else 1.0
        for rank, cid in enumerate(rlist):
            scores[cid] += w * (1.0 / (k + (rank + 1)))
    items = list(scores.items())
    items.sort(key=lambda x: x[1], reverse=True)
    return items[:top_k]


def hybrid_search(query: str,
                  top_k: int = 6,
                  dense_top: int = 100,
                  bm25_top: int = 100,
                  rrf_k: int = 60,
                  embedding_model: Optional[str] = None,
                  filters: Optional[Dict[str, Any]] = None,
                  namespaces: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    embedding_model = embedding_model or settings.CONFIG.get('embedding_model')

    # Allow overriding retrieval limits from config.yaml
    dense_top = settings.CONFIG.get('retrieval_dense_top', dense_top)
    bm25_top = settings.CONFIG.get('retrieval_bm25_top', bm25_top)
    rrf_k = settings.CONFIG.get('retrieval_rrf_k', rrf_k)
    top_k = settings.CONFIG.get('top_k', top_k)

    query_emb = get_query_embedding(query, embedding_model=embedding_model)
    if not query_emb:
        return []

    candidate_limit = max(int(dense_top), int(bm25_top), int(top_k))
    effective_filters = merge_namespace_filters(filters, namespaces)
    store = ChromaVectorStore()
    rows = store.query(query_emb, top_k=candidate_limit, filters=effective_filters)
    if not rows:
        return []

    chunk_rows: List[Dict[str, Any]] = []
    for row in rows:
        metadata = row.get('metadata') or {}
        vector_id = str(row.get('id') or '')
        chunk_key = metadata.get('chunk_id') or vector_id
        text = (row.get('document') or '').strip()
        distance = row.get('distance')
        dense_score = 1.0 / (1.0 + float(distance)) if distance is not None else 0.0
        chunk_rows.append(
            {
                'vector_id': vector_id,
                'chunk_id': chunk_key,
                'doc_id': metadata.get('doc_id'),
                'source': metadata.get('source'),
                'namespace': metadata.get('namespace'),
                'page_number': metadata.get('page_number'),
                'slide_number': metadata.get('slide_number'),
                'sheet_name': metadata.get('sheet_name'),
                'row_number': metadata.get('row_number'),
                'chunk_index': metadata.get('chunk_index'),
                'token_count': metadata.get('token_count'),
                'text': text,
                'dense_score': dense_score,
                'metadata': metadata,
            }
        )

    # Dedupe duplicate chunks deterministically by first-seen chunk_id.
    deduped_rows: List[Dict[str, Any]] = []
    seen_chunk_ids = set()
    for row in chunk_rows:
        chunk_id = row.get('chunk_id')
        if chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk_id)
        deduped_rows.append(row)
    chunk_rows = deduped_rows

    chunk_map = {r['chunk_id']: r for r in chunk_rows}

    dense_pairs = [(r['chunk_id'], float(r.get('dense_score', 0.0))) for r in chunk_rows]
    dense_pairs.sort(key=lambda x: x[1], reverse=True)
    dense_ids = [cid for cid, _ in dense_pairs[:dense_top]]

    docs_text = [r.get('text', '') for r in chunk_rows]
    bm25_k1 = settings.CONFIG.get('bm25_k1', 1.5)
    bm25_b = settings.CONFIG.get('bm25_b', 0.75)
    bm25 = BM25(docs_text, k1=bm25_k1, b=bm25_b)
    bm25_topn = bm25.top_n(query, n=bm25_top)
    bm25_ids = [chunk_rows[i].get('chunk_id') for i, _ in bm25_topn]

    # RRF merge (dense + bm25)
    merged = rrf_merge([dense_ids, bm25_ids], top_k=top_k, k=rrf_k)

    # Compose result objects
    dense_score_map = {cid: score for cid, score in dense_pairs}
    bm25_score_map = {chunk_rows[i].get('chunk_id'): score for i, score in bm25_topn}

    results: List[Dict[str, Any]] = []
    for cid, score in merged:
        meta = chunk_map.get(cid, {})
        doc_id = meta.get('doc_id') or 'unknown'
        citation = f"[{doc_id}:{cid}]"
        source_path = str(meta.get('source') or "")
        source_namespace = coerce_namespace(meta.get('namespace'))
        source_title = normalize_title(meta.get('doc_id') or source_path or "Untitled")
        source_locator = normalize_locator(meta.get('metadata') or {})
        source_snippet = normalize_snippet(meta.get('text') or "", max_chars=240)
        results.append({
            'id': meta.get('vector_id'),
            'chunk_id': cid,
            'citation': citation,
            'score': score,
            'dense_score': float(dense_score_map.get(cid, 0.0)),
            'bm25_score': float(bm25_score_map.get(cid, 0.0)),
            'text': (meta.get('text') or '')[:800],
            'doc_id': meta.get('doc_id'),
            'source_path': source_path,
            'source': {
                'source_id': '',
                'citation_index': 0,
                'namespace': source_namespace,
                'doc_id': str(meta.get('doc_id') or ''),
                'path': source_path,
                'title': source_title,
                'locator': source_locator,
                'snippet': source_snippet,
            },
            'namespace': meta.get('namespace'),
            'page_number': meta.get('page_number'),
            'slide_number': meta.get('slide_number'),
            'sheet_name': meta.get('sheet_name'),
            'row_number': meta.get('row_number'),
            'chunk_index': meta.get('chunk_index'),
            'token_count': meta.get('token_count') or len(re.findall(r"\w+", meta.get('text', ''))),
        })

    # Deterministic source ids based on final retrieval order.
    assigned = assign_source_indices([r.get('source') or {} for r in results])
    for i, source in enumerate(assigned):
        results[i]['source'] = source
    return results


# --- CLI ---

def scored_chunks(query: str,
                  top_k: int = 6,
                  rerank: bool = True,
                  rerank_weights: Optional[Dict[str, float]] = None,
                  embedding_model: Optional[str] = None,
                  filters: Optional[Dict[str, Any]] = None,
                  namespaces: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """Return scored chunk objects with metadata and optional reranking.

    This function returns a list of chunk dicts containing at least:
    chunk_id, score, dense_score, bm25_score, text, doc_id, source, token_count.
    If `rerank` is True, the heuristic reranker is applied before returning.
    """
    res = hybrid_search(
        query,
        top_k=top_k,
        embedding_model=embedding_model,
        filters=filters,
        namespaces=namespaces,
    )

    # Ensure token_count present and enrich metadata where possible
    for r in res:
        if 'token_count' not in r or r.get('token_count') is None:
            r['token_count'] = len(re.findall(r"\w+", r.get('text', '')))

    if rerank:
        try:
            res = reranker.rerank(res, query, weights=rerank_weights, top_k=top_k)
        except Exception:
            # On rerank failure, fall back to hybrid ordering
            pass

    return res


def main():
    parser = argparse.ArgumentParser(description='Hybrid retrieval (vector DB + BM25 rerank + RRF)')
    parser.add_argument('--query', required=True, help='Query text')
    parser.add_argument('--top-k', type=int, default=6, help='Number of results to return')
    parser.add_argument('--embedding-model', default=None)
    parser.add_argument('--filter-doc-id', default=None, help='Optional doc_id metadata filter')
    parser.add_argument('--namespaces', action='append', default=[], help='Namespace filter (repeatable or comma-separated)')
    parser.add_argument('--no-rerank', action='store_true', help='Disable reranking')
    args = parser.parse_args()

    filters = {'doc_id': args.filter_doc_id} if args.filter_doc_id else None
    res = scored_chunks(
        args.query,
        top_k=args.top_k,
        rerank=(not args.no_rerank),
        embedding_model=args.embedding_model,
        filters=filters,
        namespaces=args.namespaces,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
