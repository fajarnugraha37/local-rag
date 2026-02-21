from app.ingestion.doc_registry_store import DocRegistryStore


def test_doc_registry_upsert_get_delete(tmp_path):
    store = DocRegistryStore(str(tmp_path / "doc_registry.json"))
    record = store.upsert(
        namespace="alpha",
        doc_id="doc-1",
        source_path="/tmp/doc-1.txt",
        source_type="file",
        title="Doc 1",
        content_hash="h1",
        chunk_count=3,
        size_bytes=123,
        tags=["a", "b"],
    )
    store.save()

    assert record.namespace == "alpha"
    assert record.doc_id == "doc-1"
    loaded = DocRegistryStore(str(tmp_path / "doc_registry.json"))
    loaded_record = loaded.get("alpha", "doc-1")
    assert loaded_record is not None
    assert loaded_record.source_path == "/tmp/doc-1.txt"
    assert loaded_record.chunk_count == 3

    assert loaded.delete("alpha", "doc-1") is True
    assert loaded.delete("alpha", "doc-1") is False


def test_doc_registry_pagination_and_stable_order(tmp_path):
    store = DocRegistryStore(str(tmp_path / "doc_registry.json"))
    entries = [
        ("beta", "doc-2"),
        ("alpha", "doc-3"),
        ("alpha", "doc-1"),
        ("beta", "doc-1"),
    ]
    for namespace, doc_id in entries:
        store.upsert(
            namespace=namespace, doc_id=doc_id, source_path=f"/x/{doc_id}.txt", chunk_count=1
        )
    store.save()

    page1 = store.list_docs(limit=2)
    assert [r["doc_id"] for r in page1["records"]] == ["doc-1", "doc-3"]
    assert [r["namespace"] for r in page1["records"]] == ["alpha", "alpha"]
    assert page1["next_cursor"] == "alpha::doc-3"

    page2 = store.list_docs(limit=2, cursor=page1["next_cursor"])
    assert [r["namespace"] for r in page2["records"]] == ["beta", "beta"]
    assert [r["doc_id"] for r in page2["records"]] == ["doc-1", "doc-2"]
    assert page2["next_cursor"] is None

    scoped = store.list_docs(namespace="beta", limit=10)
    assert [r["doc_id"] for r in scoped["records"]] == ["doc-1", "doc-2"]
