from app.config import runtime_settings as settings
from app.retrieval import hybrid_search as retrieval
from app.retrieval.provenance import normalize_locator
from app.storage.chroma_vector_store import ChromaVectorStore


def test_scored_chunks_emits_provenance_and_dedupes_chunk_ids(tmp_path, monkeypatch):
    persist_dir = tmp_path / "chroma_citation_map"
    collection = "test_citation_map"

    settings.CONFIG["vector_db_persist_dir"] = str(persist_dir)
    settings.CONFIG["vector_db_collection"] = collection
    settings.CONFIG["embedding_dim"] = 4
    settings.CONFIG["top_k"] = 5
    settings.CONFIG["retrieval_dense_top"] = 5
    settings.CONFIG["retrieval_bm25_top"] = 5

    store = ChromaVectorStore(
        persist_dir=str(persist_dir),
        collection=collection,
        embedding_dim=4,
    )
    store.upsert(
        [
            {
                "id": "dup-1",
                "embedding": [0.1, 0.2, 0.3, 0.4],
                "text": "banana duplicate text",
                "metadata": {
                    "doc_id": "doc-a",
                    "chunk_id": "shared-chunk",
                    "source": "docs/a.pdf",
                    "namespace": "alpha",
                    "page_number": 3,
                    "token_count": 3,
                },
            },
            {
                "id": "dup-2",
                "embedding": [0.1, 0.2, 0.3, 0.39],
                "text": "banana duplicate text",
                "metadata": {
                    "doc_id": "doc-a",
                    "chunk_id": "shared-chunk",
                    "source": "docs/a.pdf",
                    "namespace": "alpha",
                    "page_number": 3,
                    "token_count": 3,
                },
            },
            {
                "id": "uniq-1",
                "embedding": [0.2, 0.2, 0.3, 0.4],
                "text": "banana second source",
                "metadata": {
                    "doc_id": "doc-b",
                    "chunk_id": "unique-chunk",
                    "source": "docs/b.pdf",
                    "namespace": "beta",
                    "slide_number": 2,
                    "token_count": 3,
                },
            },
        ]
    )

    monkeypatch.setattr(
        retrieval, "get_query_embedding", lambda query, embedding_model=None: [0.1, 0.2, 0.3, 0.4]
    )

    rows = retrieval.scored_chunks("banana", top_k=5, rerank=False)
    chunk_ids = [row["chunk_id"] for row in rows]
    assert chunk_ids.count("shared-chunk") == 1

    assert all(isinstance(row.get("source"), dict) for row in rows)
    assert [row["source"]["source_id"] for row in rows] == [
        f"S{i}" for i in range(1, len(rows) + 1)
    ]
    assert [row["source"]["citation_index"] for row in rows] == list(range(1, len(rows) + 1))
    assert all(row["source"]["locator"] for row in rows)


def test_normalize_locator_supports_docling_locators() -> None:
    assert normalize_locator({"page_range": "4-6"}) == "pages 4-6"
    assert normalize_locator({"heading_path": "Intro > Scope"}) == "section Intro > Scope"
    assert normalize_locator({"sheet_name": "Data", "row_range": "10-20"}) == "sheet Data rows 10-20"
    assert normalize_locator({"xml_schema": "jats", "section_path": "body > sec-1"}) == "jats body > sec-1"
