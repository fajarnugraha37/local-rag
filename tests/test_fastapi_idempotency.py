from fastapi.testclient import TestClient

from app.config import runtime_settings as settings
from app.http.fastapi_app import create_app


def test_idempotency_replays_same_response_for_same_key_and_payload(tmp_path, monkeypatch):
    db_path = tmp_path / 'app.db'
    monkeypatch.setitem(settings.CONFIG, 'sqlite_db_path', str(db_path))
    monkeypatch.setitem(settings.CONFIG, 'idempotency_ttl_s', 3600)

    with TestClient(create_app()) as client:
        headers = {'Idempotency-Key': 'k-1'}
        body = {'namespace': 'idem-ns', 'defaults': {'top_k': 4}}

        first = client.post('/v1/namespaces', json=body, headers=headers)
        second = client.post('/v1/namespaces', json=body, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json() == second.json()


def test_idempotency_conflicts_on_same_key_different_payload(tmp_path, monkeypatch):
    db_path = tmp_path / 'app.db'
    monkeypatch.setitem(settings.CONFIG, 'sqlite_db_path', str(db_path))

    with TestClient(create_app()) as client:
        headers = {'Idempotency-Key': 'k-2'}
        first = client.post('/v1/namespaces', json={'namespace': 'idem-a'}, headers=headers)
        second = client.post('/v1/namespaces', json={'namespace': 'idem-b'}, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 409
        assert second.json()['ok'] is False
        assert second.json()['error'] == 'idempotency_key_reused_with_different_payload'
