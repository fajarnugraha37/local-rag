import json

from app.config import runtime_settings as settings
from app.ingestion import vector_ingest_service
from app.ingestion.delete_doc_cli import main as delete_doc_main
from app.ingestion.list_docs_cli import main as list_docs_main
from app.ingestion.vector_ingest_service import ingest_chunks
from app.storage.chroma_vector_store import ChromaVectorStore


def _configure(tmp_path):
    settings.CONFIG["vector_db_persist_dir"] = str(tmp_path / "chroma_cli_docs")
    settings.CONFIG["vector_db_collection"] = "test_cli_doc_management"
    settings.CONFIG["embedding_dim"] = 4
    settings.CONFIG["vector_db_batch_size"] = 8
    settings.CONFIG["doc_registry_path"] = str(tmp_path / "doc_registry.json")


def _fake_embed(*args, **kwargs):
    return {"embedding": [0.1, 0.2, 0.3, 0.4], "model": "fake", "used_fallback": False}


def test_list_docs_global_and_scoped(tmp_path, monkeypatch, capsys):
    _configure(tmp_path)
    monkeypatch.setattr(vector_ingest_service, "embed_text", _fake_embed)

    ingest_chunks(["alpha text"], source_path="a.txt", doc_id="doc-a", namespace="alpha")
    ingest_chunks(["beta text"], source_path="b.txt", doc_id="doc-b", namespace="beta")

    list_docs_main(["--limit", "10"])
    payload_all = json.loads(capsys.readouterr().out)
    ids = {(row["namespace"], row["doc_id"]) for row in payload_all["records"]}
    assert ("alpha", "doc-a") in ids
    assert ("beta", "doc-b") in ids

    list_docs_main(["--namespace", "alpha", "--limit", "10"])
    payload_alpha = json.loads(capsys.readouterr().out)
    assert len(payload_alpha["records"]) >= 1
    assert all(row["namespace"] == "alpha" for row in payload_alpha["records"])


def test_delete_doc_single_namespace_and_all_namespaces(tmp_path, monkeypatch, capsys):
    _configure(tmp_path)
    monkeypatch.setattr(vector_ingest_service, "embed_text", _fake_embed)

    ingest_chunks(["alpha text"], source_path="a.txt", doc_id="doc-x", namespace="alpha")
    ingest_chunks(["default text"], source_path="d.txt", doc_id="doc-x")
    ingest_chunks(["beta text"], source_path="b.txt", doc_id="doc-y", namespace="beta")

    store = ChromaVectorStore(
        persist_dir=str(settings.CONFIG["vector_db_persist_dir"]),
        collection=str(settings.CONFIG["vector_db_collection"]),
        embedding_dim=4,
    )
    assert store.count() == 3

    delete_doc_main(["--doc-id", "doc-x", "--namespace", "alpha"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["all_namespaces"] is False
    assert payload["vectors_deleted"] == 1

    rows_doc_x = store.collection.get(where={"doc_id": "doc-x"}, include=[])
    assert len(rows_doc_x.get("ids") or []) == 1

    delete_doc_main(["--doc-id", "doc-x", "--all-namespaces"])
    payload_all = json.loads(capsys.readouterr().out)
    assert payload_all["ok"] is True
    assert payload_all["all_namespaces"] is True
    assert payload_all["vectors_deleted"] >= 1

    rows_doc_x_after = store.collection.get(where={"doc_id": "doc-x"}, include=[])
    assert len(rows_doc_x_after.get("ids") or []) == 0


def test_delete_doc_non_existent_is_success(tmp_path, monkeypatch, capsys):
    _configure(tmp_path)
    monkeypatch.setattr(vector_ingest_service, "embed_text", _fake_embed)

    delete_doc_main(["--doc-id", "missing-doc"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["not_found"] is True
