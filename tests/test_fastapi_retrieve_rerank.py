from fastapi.testclient import TestClient

from app.config import runtime_settings as settings
from app.http.fastapi_app import create_app


def test_fastapi_retrieve_returns_structured_candidates(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setitem(settings.CONFIG, "sqlite_db_path", str(db_path))

    from app.services import query_service as qsvc

    def fake_scored_chunks(query, top_k=6, rerank=True, filters=None, namespaces=None):
        return [
            {
                "id": "vec-1",
                "chunk_id": "ch-1",
                "doc_id": "doc-1",
                "text": "alpha beta",
                "score": 0.8,
                "dense_score": 0.7,
                "bm25_score": 0.6,
                "namespace": "default",
                "source": {"citation_index": 1, "doc_id": "doc-1", "path": "docs/a.txt"},
            }
        ]

    monkeypatch.setattr(qsvc.retrieval, "scored_chunks", fake_scored_chunks)

    with TestClient(create_app()) as client:
        resp = client.post("/v1/retrieve", json={"query": "alpha", "top_k": 5})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["count"] == 1
        cand = body["candidates"][0]
        assert cand["candidate_id"] == "vec-1"
        assert cand["scores"]["rrf"] == 0.8
        assert cand["scores"]["dense"] == 0.7
        assert cand["scores"]["bm25"] == 0.6
        assert "rerank" in cand["scores"]


def test_fastapi_rerank_returns_stable_ids_and_scores(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setitem(settings.CONFIG, "sqlite_db_path", str(db_path))

    with TestClient(create_app()) as client:
        candidates = [
            {
                "chunk_id": "a1",
                "doc_id": "doc-a",
                "text": "alpha unique term",
                "dense_score": 0.2,
                "bm25_score": 0.3,
            },
            {
                "chunk_id": "b1",
                "doc_id": "doc-b",
                "text": "beta only",
                "dense_score": 0.1,
                "bm25_score": 0.1,
            },
        ]
        resp = client.post(
            "/v1/rerank", json={"query": "alpha", "candidates": candidates, "top_k": 2}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["count"] == 2

        first = body["candidates"][0]
        second = body["candidates"][1]
        assert isinstance(first["candidate_id"], str) and first["candidate_id"]
        assert isinstance(second["candidate_id"], str) and second["candidate_id"]
        assert first["candidate_id"] != second["candidate_id"]
        assert "rerank" in first["scores"]
        assert first["rerank_rank"] == 1
