import http.client
import threading

from http.server import ThreadingHTTPServer

from app.chat import streaming_server


def test_chat_sse_emits_sources_and_stats_before_done(monkeypatch):
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

    monkeypatch.setattr(streaming_server.retrieval, "scored_chunks", fake_scored_chunks)
    monkeypatch.setattr(streaming_server, "stream_chat_with_continuation", fake_stream)
    monkeypatch.setattr(streaming_server, "OpenAI", _DummyOpenAI)

    server = ThreadingHTTPServer(("127.0.0.1", 0), streaming_server.StreamingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    conn = http.client.HTTPConnection(host, port)
    conn.request("GET", "/chat/stream?question=test&top_k=3")
    resp = conn.getresponse()
    payload = resp.read().decode("utf-8")

    assert resp.status == 200
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

    conn.close()
    server.shutdown()
    server.server_close()
