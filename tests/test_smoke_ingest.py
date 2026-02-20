from app.config import runtime_settings as settings
from app.ingestion import vector_ingest_service
from app.ingestion.vector_ingest_service import ingest_chunks
from app.ingestion.file_ingest_gui import write_chunks_file
from app.ingestion.vector_ingest_service import delete_doc
from app.retrieval import hybrid_search as retrieval
from app.storage.chroma_vector_store import ChromaVectorStore


def test_write_chunks_file_vector_ingest(tmp_path, monkeypatch):
    persist_dir = tmp_path / "chroma_ingest"
    collection = "test_smoke_ingest"

    settings.CONFIG["vector_db_persist_dir"] = str(persist_dir)
    settings.CONFIG["vector_db_collection"] = collection
    settings.CONFIG["embedding_dim"] = 4
    settings.CONFIG["vector_db_batch_size"] = 2

    def fake_embed_text(text, embedding_model=None, allow_fallback=True, fallback_length=None):
        return {"embedding": [0.1, 0.2, 0.3, 0.4], "model": "fake", "used_fallback": False}

    monkeypatch.setattr(vector_ingest_service, "embed_text", fake_embed_text)

    source = "test_source.txt"
    chunks = ["Hello world. This is test chunk 1.", "Another chunk text."]

    write_chunks_file(chunks, source, chunks_file=str(tmp_path / "legacy_unused.jsonl"))
    store = ChromaVectorStore(persist_dir=str(persist_dir), collection=collection, embedding_dim=4)
    assert store.count() == 2

    # Idempotent upsert: same chunks should not create duplicates.
    write_chunks_file(chunks, source, chunks_file=str(tmp_path / "legacy_unused.jsonl"))
    assert store.count() == 2

    deleted = delete_doc(source, store=store)
    assert deleted == 2
    assert store.count() == 0


def test_ingest_retrieve_delete_integration(tmp_path, monkeypatch):
    persist_dir = tmp_path / "chroma_integration"
    collection = "test_ingest_retrieve_delete"
    doc = "integration_doc.txt"

    settings.CONFIG["vector_db_persist_dir"] = str(persist_dir)
    settings.CONFIG["vector_db_collection"] = collection
    settings.CONFIG["embedding_dim"] = 4
    settings.CONFIG["vector_db_batch_size"] = 2
    settings.CONFIG["top_k"] = 3

    def fake_embed_text(text, embedding_model=None, allow_fallback=True, fallback_length=None):
        return {"embedding": [0.1, 0.2, 0.3, 0.4], "model": "fake", "used_fallback": False}

    monkeypatch.setattr(vector_ingest_service, "embed_text", fake_embed_text)
    monkeypatch.setattr(retrieval, "get_query_embedding", lambda query, embedding_model=None: [0.1, 0.2, 0.3, 0.4])

    chunks = ["contract payment terms net 30", "termination requires written notice"]
    summary = ingest_chunks(chunks, source_path=doc, doc_id=doc)
    assert summary["added"] == 2
    assert summary["failed"] == 0

    retrieved = retrieval.scored_chunks("payment terms", top_k=3, rerank=False, filters={"doc_id": doc})
    assert len(retrieved) >= 1
    assert all(r.get("doc_id") == doc for r in retrieved)

    deleted = delete_doc(doc)
    assert deleted == 2

    after_delete = retrieval.scored_chunks("payment terms", top_k=3, rerank=False, filters={"doc_id": doc})
    assert after_delete == []


def test_ingest_progress_callback(tmp_path, monkeypatch):
    persist_dir = tmp_path / "chroma_progress"
    collection = "test_ingest_progress"

    settings.CONFIG["vector_db_persist_dir"] = str(persist_dir)
    settings.CONFIG["vector_db_collection"] = collection
    settings.CONFIG["embedding_dim"] = 4
    settings.CONFIG["vector_db_batch_size"] = 2

    def fake_embed_text(text, embedding_model=None, allow_fallback=True, fallback_length=None):
        return {"embedding": [0.1, 0.2, 0.3, 0.4], "model": "fake", "used_fallback": False}

    monkeypatch.setattr(vector_ingest_service, "embed_text", fake_embed_text)

    events = []

    def on_progress(stage, current, total, stats):
        events.append((stage, current, total, dict(stats)))

    result = ingest_chunks(
        ["first chunk", "second chunk"],
        source_path="progress.txt",
        progress_callback=on_progress,
    )
    assert result["added"] == 2
    stages = [evt[0] for evt in events]
    assert "start" in stages
    assert "chunk" in stages
    assert stages[-1] == "done"


def test_ingest_duplicate_chunk_texts_do_not_fail(tmp_path, monkeypatch):
    persist_dir = tmp_path / "chroma_duplicates"
    collection = "test_ingest_duplicates"

    settings.CONFIG["vector_db_persist_dir"] = str(persist_dir)
    settings.CONFIG["vector_db_collection"] = collection
    settings.CONFIG["embedding_dim"] = 4
    settings.CONFIG["vector_db_batch_size"] = 64

    def fake_embed_text(text, embedding_model=None, allow_fallback=True, fallback_length=None):
        return {"embedding": [0.1, 0.2, 0.3, 0.4], "model": "fake", "used_fallback": False}

    monkeypatch.setattr(vector_ingest_service, "embed_text", fake_embed_text)

    repeated = ["same chunk text"] * 5
    summary = ingest_chunks(repeated, source_path="dup.txt", doc_id="dup.txt")
    assert summary["added"] == 5
    assert summary["failed"] == 0
