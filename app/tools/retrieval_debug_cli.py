import json
import os

from app.retrieval import hybrid_search as retrieval
from app.config import runtime_settings as settings
from app.storage.chroma_vector_store import ChromaVectorStore


def main():
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    persist_dir = os.path.join(repo_dir, "data", "chroma_debug")
    collection = "debug_retrieval"
    settings.CONFIG["vector_db_persist_dir"] = persist_dir
    settings.CONFIG["vector_db_collection"] = collection
    settings.CONFIG["embedding_dim"] = 4

    store = ChromaVectorStore(persist_dir=persist_dir, collection=collection, embedding_dim=4)
    store.upsert(
        [
            {
                "id": "v1",
                "embedding": [0.1, 0.2, 0.3, 0.4],
                "text": "apple banana cherry",
                "metadata": {"doc_id": "doc1", "chunk_id": "c1", "source": "s1", "token_count": 3},
            },
            {
                "id": "v2",
                "embedding": [0.2, 0.1, 0.4, 0.3],
                "text": "banana orange melon",
                "metadata": {"doc_id": "doc2", "chunk_id": "c2", "source": "s2", "token_count": 3},
            },
        ]
    )

    retrieval.get_query_embedding = lambda query, embedding_model=None: [0.1, 0.2, 0.3, 0.4]

    res = retrieval.scored_chunks(
        "banana",
        top_k=2,
        rerank=False,
    )
    print("RESULT_LEN:", len(res))
    print(json.dumps(res, ensure_ascii=False, indent=2))
