# coding=utf-8
"""健康检查：统一后端（8000）各面均存活"""
from fastapi.testclient import TestClient
from backend.main_api import app as api_app

api_client = TestClient(api_app)


def test_health():
    r = api_client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_api_health():
    r = api_client.get('/api/health')
    assert r.status_code == 200


def test_display_pages():
    # 展示页（原8002）已并入统一后端
    for path in ('/phones', '/sms', '/backups'):
        r = api_client.get(path)
        assert r.status_code == 200
