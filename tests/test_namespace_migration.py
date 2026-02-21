from app.config import runtime_settings as settings
from app.ingestion.doc_registry_store import DocRegistryStore
from app.migration.backfill_namespaces import backfill_namespaces
from app.storage.chroma_vector_store import ChromaVectorStore


def test_backfill_namespaces_updates_vectors_and_registry_idempotent(tmp_path):
    settings.CONFIG["vector_db_persist_dir"] = str(tmp_path / "chroma_migration")
    settings.CONFIG["vector_db_collection"] = "test_namespace_migration"
    settings.CONFIG["embedding_dim"] = 4
    settings.CONFIG["doc_registry_path"] = str(tmp_path / "doc_registry.json")

    store = ChromaVectorStore(
        persist_dir=str(settings.CONFIG["vector_db_persist_dir"]),
        collection=str(settings.CONFIG["vector_db_collection"]),
        embedding_dim=4,
    )
    store.upsert(
        [
            {
                "id": "m1",
                "embedding": [0.1, 0.2, 0.3, 0.4],
                "text": "legacy chunk one",
                "metadata": {"doc_id": "legacy-doc", "chunk_id": "c1", "source": "/tmp/legacy.txt"},
            },
            {
                "id": "m2",
                "embedding": [0.2, 0.1, 0.4, 0.3],
                "text": "legacy chunk two",
                "metadata": {"doc_id": "legacy-doc", "chunk_id": "c2", "source": "/tmp/legacy.txt"},
            },
        ]
    )

    first = backfill_namespaces(batch_size=1)
    assert first["scanned_vectors"] == 2
    assert first["updated_vectors"] == 2
    assert first["upserted_docs"] >= 1

    rows = store.get_page(offset=0, limit=10)
    assert len(rows["ids"]) == 2
    assert all((meta or {}).get("namespace") == "default" for meta in rows["metadatas"])

    registry = DocRegistryStore(str(settings.CONFIG["doc_registry_path"]))
    rec = registry.get("default", "legacy-doc")
    assert rec is not None
    assert rec.chunk_count == 2

    second = backfill_namespaces(batch_size=2)
    assert second["scanned_vectors"] == 2
    assert second["updated_vectors"] == 0
    assert second["upserted_docs"] >= 1

    registry2 = DocRegistryStore(str(settings.CONFIG["doc_registry_path"]))
    rec2 = registry2.get("default", "legacy-doc")
    assert rec2 is not None
    assert rec2.chunk_count == 2
