"""
retrieval.py

Hybrid retrieval utilities: dense (cosine) + BM25 + Reciprocal Rank Fusion (RRF).

This module is intentionally self-contained with minimal dependencies: it will use
numpy and ollama if available, and fall back to pure-Python implementations when not.

Functions:
- hybrid_search(query, ...): return ranked chunk objects combining dense+BM25 via RRF
- BM25 class: simple in-file BM25 implementation
- dense_search utilities: load embeddings and score by cosine similarity

CLI: run as a script to query the local index files in data/.
"""

from __future__ import annotations

import os
import json
import math
import re
import argparse
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

import settings

# Optional dependencies (best-effort)
try:
    import numpy as np
    _HAS_NUMPY = True
except Exception:
    _HAS_NUMPY = False

try:
    import ollama
    _HAS_OLLAMA = True
except Exception:
    _HAS_OLLAMA = False


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


# --- Embedding helpers ---

def extract_embedding(resp: Any) -> Optional[List[float]]:
    try:
        if resp is None:
            return None
        if isinstance(resp, dict):
            if 'embedding' in resp:
                return resp['embedding']
            data = resp.get('data')
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, dict) and 'embedding' in first:
                    return first['embedding']
        if hasattr(resp, 'embedding'):
            try:
                return resp.embedding
            except Exception:
                pass
        if hasattr(resp, 'data'):
            data = getattr(resp, 'data')
            if isinstance(data, (list, tuple)) and len(data) > 0:
                first = data[0]
                if hasattr(first, 'embedding'):
                    return getattr(first, 'embedding')
                if isinstance(first, dict) and 'embedding' in first:
                    return first['embedding']
        if isinstance(resp, list):
            return resp
    except Exception:
        return None
    return None


def get_query_embedding(text: str, embedding_model: Optional[str] = None) -> Optional[List[float]]:
    model = embedding_model or settings.CONFIG.get('embedding_model')
    if not _HAS_OLLAMA:
        return None
    try:
        resp = ollama.embeddings(model=model, prompt=text)
        emb = extract_embedding(resp)
        return emb
    except Exception:
        return None


def load_embeddings(emb_file: str, embedding_model: Optional[str] = None) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = {}
    if not os.path.exists(emb_file):
        return out
    with open(emb_file, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if embedding_model and obj.get('embedding_model') != embedding_model:
                    continue
                cid = obj.get('chunk_id')
                emb = obj.get('embedding')
                if cid and emb:
                    out[cid] = emb
            except Exception:
                continue
    return out


def _cosine_scores(query_vec: List[float], docs: List[List[float]]) -> List[float]:
    if query_vec is None:
        return [0.0] * len(docs)
    if _HAS_NUMPY:
        q = np.array(query_vec, dtype=float)
        D = np.array(docs, dtype=float)
        # guard shapes
        try:
            dots = D.dot(q)
            q_norm = np.linalg.norm(q)
            d_norm = np.linalg.norm(D, axis=1)
            denom = d_norm * (q_norm or 1.0)
            # avoid divide-by-zero
            with np.errstate(divide='ignore', invalid='ignore'):
                sim = np.where(denom == 0, 0.0, dots / denom)
            return sim.tolist()
        except Exception:
            # fallback to python
            pass

    # pure python fallback
    q_norm = math.sqrt(sum(x * x for x in query_vec)) or 1.0
    sims = []
    for d in docs:
        dot = sum(a * b for a, b in zip(query_vec, d))
        d_norm = math.sqrt(sum(x * x for x in d)) or 1.0
        sims.append(dot / (d_norm * q_norm))
    return sims


def dense_search(query_embedding: List[float], embeddings_map: Dict[str, List[float]], top_k: int = 10) -> List[Tuple[str, float]]:
    if not query_embedding or not embeddings_map:
        return []
    ids = list(embeddings_map.keys())
    docs = [embeddings_map[i] for i in ids]
    scores = _cosine_scores(query_embedding, docs)
    pairs = list(zip(ids, scores))
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs[:top_k]


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


# --- Hybrid search orchestration ---
def load_chunks(chunks_file: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.exists(chunks_file):
        return out
    with open(chunks_file, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                out.append(obj)
            except Exception:
                continue
    return out


def hybrid_search(query: str,
                  chunks_file: Optional[str] = None,
                  embeddings_file: Optional[str] = None,
                  top_k: int = 6,
                  dense_top: int = 100,
                  bm25_top: int = 100,
                  rrf_k: int = 60,
                  embedding_model: Optional[str] = None) -> List[Dict[str, Any]]:
    repo_dir = os.path.dirname(__file__)
    chunks_file = chunks_file or os.path.join(repo_dir, 'data', 'chunks.jsonl')
    embeddings_file = embeddings_file or os.path.join(repo_dir, 'data', 'embeddings.jsonl')
    embedding_model = embedding_model or settings.CONFIG.get('embedding_model')

    # Load chunks
    chunks = load_chunks(chunks_file)
    chunk_map = {c.get('chunk_id'): c for c in chunks if c.get('chunk_id')}
    docs_text = [c.get('text', '') for c in chunks]

    # BM25 ranking
    bm25 = BM25(docs_text)
    bm25_topn = bm25.top_n(query, n=bm25_top)
    bm25_ids = [chunks[i].get('chunk_id') for i, _ in bm25_topn]

    # Dense ranking
    embeddings_map = load_embeddings(embeddings_file, embedding_model=embedding_model)
    query_emb = get_query_embedding(query, embedding_model=embedding_model)
    dense_pairs = dense_search(query_emb, embeddings_map, top_k=dense_top)
    dense_ids = [cid for cid, _ in dense_pairs]

    # RRF merge (dense + bm25)
    merged = rrf_merge([dense_ids, bm25_ids], top_k=top_k, k=rrf_k)
    merged_ids = [cid for cid, _ in merged]

    # Compose result objects
    dense_score_map = {cid: score for cid, score in dense_pairs}
    bm25_score_map = {chunks[i].get('chunk_id'): score for i, score in bm25_topn}

    results: List[Dict[str, Any]] = []
    for cid, score in merged:
        meta = chunk_map.get(cid, {})
        results.append({
            'chunk_id': cid,
            'score': score,
            'dense_score': float(dense_score_map.get(cid, 0.0)),
            'bm25_score': float(bm25_score_map.get(cid, 0.0)),
            'text': meta.get('text', '')[:800],
            'doc_id': meta.get('doc_id'),
            'source': meta.get('source')
        })
    return results


# --- CLI ---

def scored_chunks(query: str,
                  chunks_file: Optional[str] = None,
                  embeddings_file: Optional[str] = None,
                  top_k: int = 6,
                  rerank: bool = True,
                  rerank_weights: Optional[Dict[str, float]] = None,
                  embedding_model: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return scored chunk objects with metadata and optional reranking.

    This function returns a list of chunk dicts containing at least:
    chunk_id, score, dense_score, bm25_score, text, doc_id, source, token_count.
    If `rerank` is True, the heuristic reranker is applied before returning.
    """
    res = hybrid_search(query, chunks_file=chunks_file, embeddings_file=embeddings_file, top_k=top_k, embedding_model=embedding_model)

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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Hybrid retrieval (dense + BM25 + RRF)')
    parser.add_argument('--query', required=True, help='Query text')
    parser.add_argument('--top-k', type=int, default=6, help='Number of results to return')
    parser.add_argument('--chunks-file', default=None)
    parser.add_argument('--embeddings-file', default=None)
    parser.add_argument('--embedding-model', default=None)
    parser.add_argument('--no-rerank', action='store_true', help='Disable reranking')
    args = parser.parse_args()

    res = scored_chunks(args.query, chunks_file=args.chunks_file, embeddings_file=args.embeddings_file,
                        top_k=args.top_k, rerank=(not args.no_rerank), embedding_model=args.embedding_model)
    print(json.dumps(res, ensure_ascii=False, indent=2))
