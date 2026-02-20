import pytest

from app.storage.chroma_vector_store import ChromaVectorStore


def test_vector_store_upsert_query_delete(tmp_path):
    store = ChromaVectorStore(
        persist_dir=str(tmp_path / "chroma_store"),
        collection="test_vector_store",
        embedding_dim=4,
    )

    inserted = store.upsert(
        [
            {
                "id": "v1",
                "embedding": [0.1, 0.2, 0.3, 0.4],
                "text": "alpha",
                "metadata": {"doc_id": "doc-1", "chunk_id": "c1"},
            },
            {
                "id": "v2",
                "embedding": [0.2, 0.1, 0.4, 0.3],
                "text": "beta",
                "metadata": {"doc_id": "doc-2", "chunk_id": "c2"},
            },
        ]
    )
    assert inserted == 2
    assert store.count() == 2

    rows = store.query([0.1, 0.2, 0.3, 0.4], top_k=2)
    assert len(rows) == 2
    assert all("id" in r and "metadata" in r for r in rows)

    deleted = store.delete_by_doc_id("doc-1")
    assert deleted == 1
    assert store.count() == 1


def test_vector_store_dimension_mismatch(tmp_path):
    store = ChromaVectorStore(
        persist_dir=str(tmp_path / "chroma_dim"),
        collection="test_vector_dim",
        embedding_dim=4,
    )
    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        store.upsert(
            [
                {
                    "id": "bad",
                    "embedding": [0.1, 0.2],
                    "text": "bad",
                    "metadata": {"doc_id": "doc-x"},
                }
            ]
        )
