from fastapi.testclient import TestClient

from app.config import runtime_settings as settings
from app.http.fastapi_app import create_app


def test_fastapi_namespaces_create_list_delete_dry_run(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setitem(settings.CONFIG, "sqlite_db_path", str(db_path))

    with TestClient(create_app()) as client:
        c = client.post("/v1/namespaces", json={"namespace": "alpha", "defaults": {"top_k": 5}})
        assert c.status_code == 200
        assert c.json()["ok"] is True
        assert c.json()["record"]["namespace"] == "alpha"

        l = client.get("/v1/namespaces")
        assert l.status_code == 200
        assert l.json()["ok"] is True
        assert any(r["namespace"] == "alpha" for r in l.json()["records"])

        d1 = client.delete("/v1/namespaces/alpha?dry_run=true")
        payload1 = d1.json()
        assert d1.status_code == 200
        assert payload1["ok"] is True
        assert payload1["dry_run"] is True
        assert payload1["would_delete"] is True

        d2 = client.delete("/v1/namespaces/alpha")
        payload2 = d2.json()
        assert d2.status_code == 200
        assert payload2["ok"] is True
        assert payload2["deleted"] is True

        l2 = client.get("/v1/namespaces")
        assert all(r["namespace"] != "alpha" for r in l2.json()["records"])

        l3 = client.get("/v1/namespaces?include_deleted=true")
        assert any(
            r["namespace"] == "alpha" and r["deleted_at"] is not None for r in l3.json()["records"]
        )
