import json
import os

from app.retrieval import hybrid_search as retrieval


def main():
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    chunks_path = os.path.join(repo_dir, "tmp_debug_chunks.jsonl")
    embeddings_path = os.path.join(repo_dir, "tmp_emb.jsonl")

    data = [
        {"chunk_id": "c1", "doc_id": "doc1", "source": "s1", "text": "apple banana cherry", "token_count": 3},
        {"chunk_id": "c2", "doc_id": "doc2", "source": "s2", "text": "banana orange melon", "token_count": 3},
    ]
    with open(chunks_path, "w", encoding="utf-8") as fh:
        for obj in data:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")

    res = retrieval.scored_chunks(
        "banana",
        chunks_file=chunks_path,
        embeddings_file=embeddings_path,
        top_k=2,
        rerank=False,
    )
    print("RESULT_LEN:", len(res))
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
