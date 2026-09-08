# coding=utf-8
"""号段定向生成测试"""
from fastapi.testclient import TestClient
from backend.main_api import app

client = TestClient(app)


def test_prefix_list_seeded():
    d = client.get('/api/phone/prefixes').json()['data']
    assert len(d) >= 43
    assert any(x['prefix'] == '95575' for x in d)


def test_prefix_generate():
    r = client.post('/api/phone/generate', json={'count': 4, 'prefixes': ['95575']}).json()
    assert r['count'] == 4
    assert all(n.startswith('+85295575') and len(n) == 12 for n in [x['number'] for x in r['data']])


def test_prefix_validation_and_crud():
    assert client.post('/api/phone/generate', json={'count': 1, 'prefixes': ['21']}).status_code == 422
    a = client.post('/api/phone/prefixes', json={'prefix': '58888'})
    assert a.status_code == 200
    assert client.post('/api/phone/prefixes', json={'prefix': '58888'}).status_code == 409
    assert client.delete(f"/api/phone/prefixes/{a.json()['id']}").status_code == 200
    assert client.delete('/api/phone/prefixes/999999999').status_code == 404
