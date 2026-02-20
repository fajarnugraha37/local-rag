"""
eval/run_eval.py

Simple evaluation runner for retrieval metrics (Recall@k, MRR, citation coverage, latency P50/P95).

Usage:
  python eval/run_eval.py --questions eval/questions.jsonl --top-k 6 --output eval/results.json

This script is intentionally lightweight and robust to slightly different retrieval result shapes.
"""

import argparse
import json
import time
import statistics
import os
from typing import List, Dict, Any

from app.config import runtime_settings as settings
from app.retrieval import hybrid_search as retrieval


def load_questions(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def normalize_expected_ids(expected_chunks: List[Dict[str, Any]]):
    ids = set()
    for e in expected_chunks:
        if not isinstance(e, dict):
            # allow string entries
            if isinstance(e, str):
                ids.add(e)
            continue
        # Prefer an explicit combined chunk_id if provided
        if 'chunk_id' in e and isinstance(e.get('chunk_id'), str) and ':' in e.get('chunk_id'):
            ids.add(e.get('chunk_id'))
            continue
        # If both doc_id and chunk_id are present, join them
        if 'doc_id' in e and 'chunk_id' in e and e.get('doc_id') and e.get('chunk_id'):
            ids.add(f"{e.get('doc_id')}:{e.get('chunk_id')}")
            continue
        # Fallbacks
        if 'chunk_id' in e and e.get('chunk_id'):
            ids.add(e.get('chunk_id'))
        elif 'doc_id' in e and e.get('doc_id'):
            ids.add(e.get('doc_id'))
    return ids


def extract_result_ids(result: Dict[str, Any]):
    ids = set()
    if not isinstance(result, dict):
        return ids
    # direct chunk_id
    if result.get('chunk_id'):
        ids.add(result.get('chunk_id'))
    # some codebases use 'id'
    if result.get('id'):
        ids.add(result.get('id'))
    # doc_id + chunk_id pair
    if result.get('doc_id') and result.get('chunk_id'):
        ids.add(f"{result.get('doc_id')}:{result.get('chunk_id')}")
    # source + chunk_id
    if result.get('source') and result.get('chunk_id'):
        ids.add(f"{result.get('source')}:{result.get('chunk_id')}")
    # as a last resort include doc_id or source alone
    if result.get('doc_id'):
        ids.add(result.get('doc_id'))
    if result.get('source'):
        ids.add(result.get('source'))
    return ids


def percentile(sorted_list: List[float], p: float) -> float:
    if not sorted_list:
        return 0.0
    k = (len(sorted_list) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_list) - 1)
    if f == c:
        return sorted_list[f]
    d = k - f
    return sorted_list[f] + d * (sorted_list[c] - sorted_list[f])


def run_eval(questions_file: str, top_k: int = 6, output_file: str = 'eval/results.json'):
    questions = load_questions(questions_file)
    if not questions:
        print(f"No questions found in {questions_file}")
        return

    per_query = []
    latencies = []
    hits = 0
    mrr_total = 0.0
    total_cited_chunks = 0
    total_returned_chunks = 0

    for q in questions:
        qid = q.get('id') or q.get('qid') or None
        query = q.get('query') or q.get('question') or q.get('text')
        expected_chunks = q.get('expected_chunks', []) or []
        expected_ids = normalize_expected_ids(expected_chunks)

        start = time.perf_counter()
        try:
            results = retrieval.scored_chunks(query, top_k=top_k)
        except Exception as e:
            print(f"Retrieval failed for query '{query}' (id={qid}): {e}")
            results = []
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies.append(elapsed_ms)

        if not isinstance(results, list):
            results = list(results or [])

        found_any = False
        reciprocal_rank = 0.0
        cited_chunks_for_query = 0

        for rank, r in enumerate(results, start=1):
            res_ids = extract_result_ids(r)
            if expected_ids and not found_any and any((eid in res_ids) for eid in expected_ids):
                found_any = True
                reciprocal_rank = 1.0 / float(rank)
            # count as cited if result has at least chunk_id or doc_id
            if r.get('chunk_id') or r.get('doc_id') or r.get('source'):
                cited_chunks_for_query += 1

        hits += 1 if found_any else 0
        mrr_total += reciprocal_rank
        total_cited_chunks += cited_chunks_for_query
        total_returned_chunks += max(0, len(results))

        per_query.append({
            'id': qid,
            'query': query,
            'expected_ids': list(expected_ids),
            'retrieved_count': len(results),
            'hit': found_any,
            'reciprocal_rank': reciprocal_rank,
            'latency_ms': elapsed_ms,
        })

    n = len(questions)
    recall_at_k = hits / n if n > 0 else 0.0
    mrr = mrr_total / n if n > 0 else 0.0
    citation_coverage = (total_cited_chunks / total_returned_chunks) if total_returned_chunks > 0 else 0.0

    lat_sorted = sorted(latencies)
    p50 = statistics.median(lat_sorted) if lat_sorted else 0.0
    p95 = percentile(lat_sorted, 95)

    summary = {
        'n_queries': n,
        'top_k': top_k,
        'recall_at_k': recall_at_k,
        'mrr': mrr,
        'citation_coverage': citation_coverage,
        'latency_ms_p50': p50,
        'latency_ms_p95': p95,
        'per_query': per_query,
    }

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as fh:
        json.dump(summary, fh, indent=2)

    print(json.dumps({
        'n_queries': n,
        'recall_at_k': recall_at_k,
        'mrr': mrr,
        'citation_coverage': citation_coverage,
        'latency_ms_p50': p50,
        'latency_ms_p95': p95,
    }, indent=2))

    return summary


def main():
    parser = argparse.ArgumentParser(description='Run simple retrieval evaluation metrics')
    parser.add_argument('--questions', default='eval/questions.jsonl', help='Path to questions JSONL file')
    parser.add_argument('--top-k', type=int, default=settings.CONFIG.get('top_k', 6), help='Top-K to evaluate')
    parser.add_argument('--output', default='eval/results.json', help='Output JSON summary file')
    args = parser.parse_args()

    run_eval(args.questions, top_k=args.top_k, output_file=args.output)


if __name__ == '__main__':
    main()
