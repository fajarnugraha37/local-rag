import json
import retrieval


def test_retrieval_bm25(tmp_path):
    chunks_file = tmp_path / "chunks.jsonl"
    data = [
        {"chunk_id": "c1", "doc_id": "doc1", "source": "s1", "text": "apple banana cherry", "token_count": 3},
        {"chunk_id": "c2", "doc_id": "doc2", "source": "s2", "text": "banana orange melon", "token_count": 3},
    ]
    with open(chunks_file, 'w', encoding='utf-8') as fh:
        for obj in data:
            fh.write(json.dumps(obj, ensure_ascii=False) + '\\n')

    res = retrieval.scored_chunks("banana", chunks_file=str(chunks_file), embeddings_file=str(tmp_path / "emb.jsonl"), top_k=2, rerank=False)
    assert isinstance(res, list)
    assert len(res) >= 1
    ids = [r.get('chunk_id') for r in res]
    assert "c1" in ids or "c2" in ids
