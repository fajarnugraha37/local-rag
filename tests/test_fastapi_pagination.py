from fastapi.testclient import TestClient

from app.config import runtime_settings as settings
from app.http.fastapi_app import create_app
from app.repositories.sqlite.db import init_db
from app.repositories.sqlite.documents_repo import DocumentsRepository
from app.repositories.sqlite.namespaces_repo import NamespacesRepository


def _seed(db_path: str):
    init_db(db_path)
    docs = DocumentsRepository(db_path)
    ns = NamespacesRepository(db_path)

    ns.create("alpha")
    ns.create("beta")
    docs.upsert({"namespace": "alpha", "doc_id": "a1", "source_path": "a1.txt"})
    docs.upsert({"namespace": "alpha", "doc_id": "a2", "source_path": "a2.txt"})
    docs.upsert({"namespace": "beta", "doc_id": "b1", "source_path": "b1.txt"})


def test_documents_cursor_pagination_and_soft_delete_filter(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setitem(settings.CONFIG, "sqlite_db_path", str(db_path))
    _seed(str(db_path))

    with TestClient(create_app()) as client:
        p1 = client.get("/v1/documents?limit=2")
        assert p1.status_code == 200
        j1 = p1.json()
        assert j1["ok"] is True
        assert len(j1["records"]) == 2
        assert j1["next_cursor"] is not None

        p2 = client.get(f"/v1/documents?limit=2&cursor={j1['next_cursor']}")
        assert p2.status_code == 200
        j2 = p2.json()
        assert j2["ok"] is True
        assert len(j2["records"]) >= 1

        d = client.delete("/v1/documents/alpha/a1")
        assert d.status_code == 200
        assert d.json()["deleted"] is True

        listed = client.get("/v1/documents?namespace=alpha")
        ids = {r["doc_id"] for r in listed.json()["records"]}
        assert "a1" not in ids
        assert "a2" in ids

        listed_deleted = client.get("/v1/documents?namespace=alpha&include_deleted=true")
        ids2 = {r["doc_id"] for r in listed_deleted.json()["records"]}
        assert "a1" in ids2


def test_namespaces_soft_delete_excluded_by_default(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setitem(settings.CONFIG, "sqlite_db_path", str(db_path))
    _seed(str(db_path))

    with TestClient(create_app()) as client:
        resp = client.delete("/v1/namespaces/beta")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        lst = client.get("/v1/namespaces")
        names = {r["namespace"] for r in lst.json()["records"]}
        assert "beta" not in names

        lst2 = client.get("/v1/namespaces?include_deleted=true")
        rows = [r for r in lst2.json()["records"] if r["namespace"] == "beta"]
        assert rows and rows[0]["deleted_at"] is not None
