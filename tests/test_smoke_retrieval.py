from app.config import runtime_settings as settings
from app.retrieval import hybrid_search as retrieval
from app.storage.chroma_vector_store import ChromaVectorStore


def test_retrieval_namespace_scoping(tmp_path, monkeypatch):
    persist_dir = tmp_path / "chroma_retrieval_ns"
    collection = "test_retrieval_ns"

    settings.CONFIG["vector_db_persist_dir"] = str(persist_dir)
    settings.CONFIG["vector_db_collection"] = collection
    settings.CONFIG["embedding_dim"] = 4
    settings.CONFIG["top_k"] = 3

    store = ChromaVectorStore(
        persist_dir=str(persist_dir),
        collection=collection,
        embedding_dim=4,
    )
    store.upsert(
        [
            {
                "id": "n1",
                "embedding": [0.1, 0.2, 0.3, 0.4],
                "text": "banana alpha text",
                "metadata": {
                    "doc_id": "doc-alpha",
                    "chunk_id": "c-alpha",
                    "source": "s1",
                    "namespace": "alpha",
                    "token_count": 3,
                    "page_number": 1,
                    "chunk_index": 0,
                },
            },
            {
                "id": "n2",
                "embedding": [0.2, 0.1, 0.4, 0.3],
                "text": "banana beta text",
                "metadata": {"doc_id": "doc-beta", "chunk_id": "c-beta", "source": "s2", "namespace": "beta", "token_count": 3},
            },
        ]
    )
    monkeypatch.setattr(retrieval, "get_query_embedding", lambda query, embedding_model=None: [0.1, 0.2, 0.3, 0.4])

    all_ns = retrieval.scored_chunks("banana", top_k=3, rerank=False)
    assert len(all_ns) >= 2

    alpha_only = retrieval.scored_chunks("banana", top_k=3, rerank=False, namespaces=["alpha"])
    assert len(alpha_only) >= 1
    assert all(row.get("namespace") == "alpha" for row in alpha_only)

    none_match = retrieval.scored_chunks("banana", top_k=3, rerank=False, namespaces=["gamma"])
    assert none_match == []


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
                "metadata": {
                    "doc_id": "doc1",
                    "chunk_id": "c1",
                    "source": "s1",
                    "namespace": "alpha",
                    "token_count": 3,
                    "page_number": 2,
                    "chunk_index": 5,
                },
            },
            {
                "id": "v2",
                "embedding": [0.2, 0.1, 0.4, 0.3],
                "text": "banana orange melon",
                "metadata": {
                    "doc_id": "doc2",
                    "chunk_id": "c2",
                    "source": "s2",
                    "namespace": "beta",
                    "token_count": 3,
                    "slide_number": 4,
                    "chunk_index": 8,
                },
            },
        ]
    )

    monkeypatch.setattr(retrieval, "get_query_embedding", lambda query, embedding_model=None: [0.1, 0.2, 0.3, 0.4])

    res = retrieval.scored_chunks("banana", top_k=2, rerank=False)
    assert isinstance(res, list)
    assert len(res) >= 1
    ids = [r.get("chunk_id") for r in res]
    assert "c1" in ids or "c2" in ids
    assert all("doc_id" in r and "source" in r and "citation" in r and "namespace" in r for r in res)
    assert all(isinstance(r.get("source"), dict) for r in res)
    assert all("source_id" in r["source"] and "citation_index" in r["source"] for r in res)
    assert all("locator" in r["source"] and "snippet" in r["source"] for r in res)
    assert all(r["source"]["source_id"].startswith("S") for r in res)

    ns_alpha = retrieval.scored_chunks("banana", top_k=2, rerank=False, namespaces=["alpha"])
    assert len(ns_alpha) >= 1
    assert all(r.get("namespace") == "alpha" for r in ns_alpha)

    ns_multi = retrieval.scored_chunks("banana", top_k=2, rerank=False, namespaces=["alpha,beta"])
    assert len(ns_multi) >= 1
    assert {r.get("namespace") for r in ns_multi}.issubset({"alpha", "beta"})

    filtered = retrieval.scored_chunks("banana", top_k=2, rerank=False, filters={"doc_id": "doc1"})
    assert len(filtered) >= 1
    assert all(r.get("doc_id") == "doc1" for r in filtered)

    filtered_and_ns = retrieval.scored_chunks(
        "banana",
        top_k=2,
        rerank=False,
        filters={"doc_id": "doc1"},
        namespaces=["beta"],
    )
    assert filtered_and_ns == []

    no_match = retrieval.scored_chunks("banana", top_k=2, rerank=False, filters={"doc_id": "does-not-exist"})
    assert no_match == []
