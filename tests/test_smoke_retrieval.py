from app.config import runtime_settings as settings
from app.retrieval import hybrid_search as retrieval
from app.storage.chroma_vector_store import ChromaVectorStore


def test_retrieval_vector_db(tmp_path, monkeypatch):
    persist_dir = tmp_path / "chroma_retrieval"
    collection = "test_retrieval"

    settings.CONFIG["vector_db_persist_dir"] = str(persist_dir)
    settings.CONFIG["vector_db_collection"] = collection
    settings.CONFIG["embedding_dim"] = 4
    settings.CONFIG["top_k"] = 2

    store = ChromaVectorStore(
        persist_dir=str(persist_dir),
        collection=collection,
        embedding_dim=4,
    )
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

    monkeypatch.setattr(retrieval, "get_query_embedding", lambda query, embedding_model=None: [0.1, 0.2, 0.3, 0.4])

    res = retrieval.scored_chunks("banana", top_k=2, rerank=False)
    assert isinstance(res, list)
    assert len(res) >= 1
    ids = [r.get("chunk_id") for r in res]
    assert "c1" in ids or "c2" in ids

    filtered = retrieval.scored_chunks("banana", top_k=2, rerank=False, filters={"doc_id": "doc1"})
    assert len(filtered) >= 1
    assert all(r.get("doc_id") == "doc1" for r in filtered)
