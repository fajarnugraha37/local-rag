from fastapi.testclient import TestClient

from app.config import runtime_settings as settings
from app.http.fastapi_app import create_app
from app.repositories.sqlite.db import init_db
from app.repositories.sqlite.documents_repo import DocumentsRepository


def _seed_docs(db_path: str):
    init_db(db_path)
    repo = DocumentsRepository(db_path)
    repo.upsert({"namespace": "alpha", "doc_id": "doc-a", "source_path": "a.txt", "chunk_count": 1})
    repo.upsert({"namespace": "alpha", "doc_id": "doc-b", "source_path": "b.txt", "chunk_count": 2})
    repo.upsert({"namespace": "beta", "doc_id": "doc-c", "source_path": "c.txt", "chunk_count": 3})


def test_fastapi_documents_list_detail_delete_bulk_and_pagination(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setitem(settings.CONFIG, "sqlite_db_path", str(db_path))
    _seed_docs(str(db_path))

    with TestClient(create_app()) as client:
        page1 = client.get("/v1/documents?limit=2")
        assert page1.status_code == 200
        p1 = page1.json()
        assert p1["ok"] is True
        assert len(p1["records"]) == 2
        assert p1["next_cursor"] is not None

        page2 = client.get(f"/v1/documents?limit=2&cursor={p1['next_cursor']}")
        assert page2.status_code == 200
        p2 = page2.json()
        assert p2["ok"] is True
        assert len(p2["records"]) >= 1

        detail = client.get("/v1/documents/alpha/doc-a")
        assert detail.status_code == 200
        assert detail.json()["ok"] is True
        assert detail.json()["record"]["doc_id"] == "doc-a"

        delete = client.delete("/v1/documents/alpha/doc-a")
        assert delete.status_code == 200
        assert delete.json()["ok"] is True
        assert delete.json()["deleted"] is True

        missing_after_soft_delete = client.get("/v1/documents/alpha/doc-a")
        assert missing_after_soft_delete.status_code == 200
        assert missing_after_soft_delete.json()["ok"] is False

        include_deleted_detail = client.get("/v1/documents/alpha/doc-a?include_deleted=true")
        assert include_deleted_detail.status_code == 200
        assert include_deleted_detail.json()["ok"] is True
        assert include_deleted_detail.json()["record"]["deleted_at"] is not None

        bulk = client.post(
            "/v1/documents:bulk_delete", json={"namespace": "alpha", "doc_ids": ["doc-b"]}
        )
        assert bulk.status_code == 200
        b = bulk.json()
        assert b["ok"] is True
        assert b["matched"] == 1
        assert b["deleted"] == 1
