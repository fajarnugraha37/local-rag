from fastapi.testclient import TestClient

from app.http.fastapi_app import create_app


def test_chat_sse_emits_sources_and_stats_before_done(monkeypatch):
    from app.http.routers import legacy

    def fake_scored_chunks(query, top_k=3, rerank=True, filters=None, namespaces=None):
        return [
            {
                "chunk_id": "c1",
                "doc_id": "doc-1",
                "namespace": "default",
                "text": "Alpha evidence.",
                "source": {
                    "source_id": "S1",
                    "citation_index": 1,
                    "namespace": "default",
                    "doc_id": "doc-1",
                    "path": "docs/a.txt",
                    "title": "Doc A",
                    "locator": "page 1",
                    "snippet": "Alpha evidence.",
                },
            }
        ]

    def fake_stream(*args, **kwargs):
        yield {"event": "meta", "data": {"stream": True}}
        yield {"event": "final_delta", "data": {"text": "Answer [1]."}}
        yield {"event": "done", "data": {"cancelled": False, "text": "Answer [1]."}}

    class _DummyOpenAI:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(legacy.retrieval, "scored_chunks", fake_scored_chunks)
    monkeypatch.setattr(legacy, "stream_chat_with_continuation", fake_stream)
    monkeypatch.setattr(legacy, "OpenAI", _DummyOpenAI)

    with TestClient(create_app()) as client:
        resp = client.get("/chat/stream?question=test&top_k=3")
        payload = resp.text

    assert resp.status_code == 200
    assert "event: final_delta" in payload
    assert "event: sources" in payload
    assert "event: citation_stats" in payload
    assert "event: done" in payload

    idx_final = payload.index("event: final_delta")
    idx_sources = payload.index("event: sources")
    idx_stats = payload.index("event: citation_stats")
    idx_done = payload.index("event: done")
    assert idx_final < idx_sources < idx_stats < idx_done

    assert '"sources": [{' in payload
    assert '"citation_index": 1' in payload
    assert '"stats": {' in payload
