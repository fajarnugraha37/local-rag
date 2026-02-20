import json
import os
import sys

repo = os.path.dirname(__file__)
chunks_path = os.path.join(repo, 'tmp_debug_chunks.jsonl')
data = [
    {"chunk_id": "c1", "doc_id": "doc1", "source": "s1", "text": "apple banana cherry", "token_count": 3},
    {"chunk_id": "c2", "doc_id": "doc2", "source": "s2", "text": "banana orange melon", "token_count": 3},
]
with open(chunks_path, 'w', encoding='utf-8') as fh:
    for o in data:
        fh.write(json.dumps(o, ensure_ascii=False) + "\n")

# Ensure repo is on path
sys.path.insert(0, repo)
import retrieval
res = retrieval.scored_chunks('banana', chunks_file=chunks_path, embeddings_file=os.path.join(repo, 'tmp_emb.jsonl'), top_k=2, rerank=False)
print('RESULT_LEN:', len(res))
print(json.dumps(res, ensure_ascii=False, indent=2))
