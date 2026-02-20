from app.config import runtime_settings as settings
from app.ingestion import vector_ingest_service
from app.ingestion.file_ingest_gui import write_chunks_file
from app.ingestion.vector_ingest_service import delete_doc
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
