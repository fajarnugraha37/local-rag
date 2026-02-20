"""
Phase 4 validation: exercise multi-pass retrieval and citation outputs
without calling external LLMs. This script demonstrates:
- retrieval.scored_chunks returns citation metadata
- context_packer.pack_context selects chunks within token budget
- multi-pass (A/B) retrieval produces wider context on second pass

Run via centralized launcher:
python .\\cmd\\app.py --cli validate-phase4 --query "your query" --top-k 8
"""

import argparse
from app.retrieval import hybrid_search as retrieval
from app.context import token_budget_packer as context_packer
from app.config import runtime_settings as settings
from app.context import token_chunking as chunking


def run_pass(query: str, top_k: int):
    print(f"Running retrieval for top_k={top_k}...\n")
    res = retrieval.scored_chunks(query, top_k=top_k)
    print(f"Retrieved {len(res)} scored chunks")

    for idx, r in enumerate(res, start=1):
        cid = r.get('chunk_id')
        cit = r.get('citation')
        bm = r.get('bm25_score', 0.0)
        ds = r.get('dense_score', 0.0)
        doc = r.get('doc_id')
        text_preview = (r.get('text', ''))[:300].replace('\n', ' ')
        print(f"{idx}. {cid} {cit} doc={doc} bm25={bm:.3f} dense={ds:.3f}")
        print(f"   preview: {text_preview}...\n")

    # Pack context by token budget using retrieved texts in rank order.
    texts_in_order = [r.get('text', '') for r in res]
    max_tokens = settings.CONFIG.get('context_token_budget', 1500)
    overlap = settings.CONFIG.get('context_overlap', 20)

    packed = context_packer.pack_context(query, texts_in_order, max_tokens=max_tokens, overlap_tokens=overlap)

    print(f"Packed into {len(packed)} pieces (max_tokens={max_tokens} overlap={overlap}):")
    for i, p in enumerate(packed, start=1):
        tc = chunking.estimate_token_count(p)
        preview = p[:200].replace('\n',' ')
        print(f"  Piece {i}: tokens={tc} preview={preview}...")
    print('\n' + ('-'*60) + '\n')

    return res, packed


def main():
    parser = argparse.ArgumentParser(description='Phase 4 validation runner')
    parser.add_argument('--query', default='common case overview')
    parser.add_argument('--top-k', type=int, default=8)
    args = parser.parse_args()

    print('Phase 4 validation start')
    print(f"Query: {args.query}\n")

    print('--- PASS A (initial retrieval + packing) ---')
    resA, packedA = run_pass(args.query, args.top_k)

    print('--- PASS B (wider retrieval + packing) ---')
    resB, packedB = run_pass(args.query, args.top_k * 2)

    print('Summary:')
    print(f"Pass A: retrieved={len(resA)} packed_pieces={len(packedA)}")
    print(f"Pass B: retrieved={len(resB)} packed_pieces={len(packedB)}")
    print('\nCitations sample (A):', [r.get('citation') for r in resA[:5]])
    print('Citations sample (B):', [r.get('citation') for r in resB[:5]])
    print('\nPhase 4 validation complete.')


