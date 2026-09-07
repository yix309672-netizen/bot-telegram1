# coding=utf-8
"""统一监控台测试：页面元素 + 权限 + 聚合接口"""
from fastapi.testclient import TestClient
from backend.main_api import app

client = TestClient(app)


def test_console_public():
    r = client.get('/console')
    assert r.status_code == 200
    for needle in ('实时监控台', 'm-phones', 'logstream', 'opGenerate', 'opConvert'):
        assert needle in r.text


def test_console_admin_requires_login():
    assert client.get('/admin/console').status_code == 401


def test_metrics_overview_shape():
    d = client.get('/api/metrics/overview').json()
    for k in ('phones', 'valid_phones', 'sms', 'backups', 'audit'):
        assert k in d


def test_metrics_recent_shape():
    d = client.get('/api/metrics/recent').json()
    assert 'buckets' in d and 'entries' in d


def test_system_status_shape():
    d = client.get('/api/system/status').json()
    for k in ('backend', 'database', 'redis', 'bot', 'converter'):
        assert k in d and 'ok' in d[k] and 'label' in d[k]
