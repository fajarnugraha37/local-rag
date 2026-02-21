from fastapi.testclient import TestClient

from app.http.fastapi_app import create_app


def test_system_endpoints_health_version_capabilities():
    client = TestClient(create_app())

    h = client.get('/health')
    hz = client.get('/healthz')
    r = client.get('/readyz')
    v = client.get('/version')
    c = client.get('/v1/capabilities')

    assert h.status_code == 200
    assert h.json() == {'ok': True}
    assert hz.status_code == 200
    assert hz.json() == {'ok': True}

    ready = r.json()
    assert r.status_code == 200
    assert ready['ok'] is True
    assert set(ready['components'].keys()) == {'sqlite', 'vector_db', 'reranker'}
    assert all(isinstance(ready['components'][k]['ok'], bool) for k in ready['components'])

    assert v.status_code == 200
    assert v.json()['ok'] is True
    assert v.json()['api'] == 'fastapi'

    caps = c.json()
    assert c.status_code == 200
    assert caps['ok'] is True
    assert caps['capabilities']['streaming'] is True


def test_v1_config_get_and_patch():
    client = TestClient(create_app())

    g = client.get('/v1/config')
    assert g.status_code == 200
    cfg = g.json()['config']
    assert isinstance(cfg, dict)

    p = client.patch(
        '/v1/config',
        json={
            'updates': {
                'top_k': 9,
                'enable_streaming': True,
                'non_patchable': 'x',
            }
        },
    )
    assert p.status_code == 200
    payload = p.json()
    assert payload['ok'] is True
    assert payload['config']['top_k'] == 9
    assert payload['config']['_applied']['top_k'] == 9
    assert 'non_patchable' in payload['config']['_rejected']
