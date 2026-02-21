from fastapi.testclient import TestClient

from app.config import runtime_settings as settings
from app.http.fastapi_app import create_app


def test_fastapi_query_creates_run_and_persists_events(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setitem(settings.CONFIG, "sqlite_db_path", str(db_path))

    from app.services import query_service as qsvc

    def fake_scored_chunks(query, top_k=6, rerank=True, filters=None, namespaces=None):
        return [
            {
                "doc_id": "doc-1",
                "text": "alpha",
                "source": {
                    "source_id": "S1",
                    "citation_index": 1,
                    "namespace": "default",
                    "doc_id": "doc-1",
                    "path": "docs/a.txt",
                    "title": "Doc A",
                    "locator": "p1",
                    "snippet": "alpha",
                },
            }
        ]

    monkeypatch.setattr(qsvc.retrieval, "scored_chunks", fake_scored_chunks)

    with TestClient(create_app()) as client:
        resp = client.post("/v1/query", json={"query": "alpha", "top_k": 3})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert isinstance(body["run_id"], str)
        assert isinstance(body["trace_id"], str)
        assert isinstance(body["sources"], list)

        run = client.get(f"/v1/runs/{body['run_id']}")
        assert run.status_code == 200
        assert run.json()["ok"] is True
        assert run.json()["record"]["status"] == "done"

        events = client.get(f"/v1/runs/{body['run_id']}/events")
        assert events.status_code == 200
        names = [e["event"] for e in events.json()["events"]]
        assert "meta" in names
        assert "final_delta" in names
        assert "done" in names

        steps = client.get(f"/v1/runs/{body['run_id']}/steps")
        assert steps.status_code == 200
        assert steps.json()["ok"] is True
        assert len(steps.json()["steps"]) >= 1
