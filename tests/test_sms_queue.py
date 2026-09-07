# coding=utf-8
"""短信队列测试：认领/回执/重试终结/重发/状态过滤"""
from fastapi.testclient import TestClient
from backend.main_api import app

client = TestClient(app)


def _drain():
    while True:
        d = client.post('/api/sms/claim').json()['data']
        if not d:
            break
        client.post(f"/api/sms/{d['id']}/complete", json={'status': 'sent'})


def test_queue_lifecycle():
    _drain()
    sid = client.post('/api/sms/send', json={'phone': '+85251234567', 'content': 'q'}).json()['sms_id']
    assert client.post('/api/sms/claim').json()['data']['status'] == 'sending'
    r = client.post(f'/api/sms/{sid}/complete', json={'status': 'failed', 'error': 'x'}).json()['data']
    assert r['status'] == 'queued' and r['retry_count'] == 1
    for _ in range(2):
        assert client.post('/api/sms/claim').json()['data']['id'] == sid
        r = client.post(f'/api/sms/{sid}/complete', json={'status': 'failed', 'error': 'x'}).json()['data']
    assert r['status'] == 'failed' and r['retry_count'] == 3
    assert client.post(f'/api/sms/{sid}/complete', json={'status': 'sent'}).status_code == 409
    assert client.post(f'/api/sms/{sid}/requeue').json()['data']['status'] == 'queued'
    assert client.post('/api/sms/claim').json()['data']['id'] == sid
    assert client.post(f'/api/sms/{sid}/complete', json={'status': 'sent'}).json()['data']['status'] == 'sent'
    assert client.post('/api/sms/claim').json()['data'] is None


def test_queue_invalid():
    assert client.post('/api/sms/999999999/complete', json={'status': 'sent'}).status_code == 404
    assert client.post('/api/sms/999999999/requeue').status_code == 404
    sid = client.post('/api/sms/send', json={'phone': '+85251234567', 'content': 'q'}).json()['sms_id']
    assert client.post(f'/api/sms/{sid}/complete', json={'status': 'bogus'}).status_code == 422
    assert client.get('/api/sms/list?status=sent').json()['total'] >= 1
    # 清理测试件
    client.post('/api/sms/claim')
    client.post(f'/api/sms/{sid}/complete', json={'status': 'sent'})
