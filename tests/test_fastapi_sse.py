from fastapi.testclient import TestClient

from app.config import runtime_settings as settings
from app.http.fastapi_app import create_app


def test_fastapi_query_stream_and_replay_sse(tmp_path, monkeypatch):
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
        stream_resp = client.post(
            "/v1/query/stream", json={"query": "alpha"}, headers={"accept": "text/event-stream"}
        )
        assert stream_resp.status_code == 200
        text = stream_resp.text
        assert "event: meta" in text
        assert "event: final_delta" in text
        assert "event: sources" in text
        assert "event: citation_stats" in text
        assert "event: done" in text

        query_resp = client.post("/v1/query", json={"query": "alpha"})
        run_id = query_resp.json()["run_id"]

        replay = client.get(f"/v1/runs/{run_id}/replay")
        assert replay.status_code == 200
        replay_text = replay.text
        assert "event: meta" in replay_text
        assert "event: done" in replay_text
