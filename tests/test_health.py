# coding=utf-8
"""健康检查：验证主接口与转换服务均存活"""
from fastapi.testclient import TestClient
from backend.main_api import app as api_app
from backend.main_web import app as web_app

api_client = TestClient(api_app)
web_client = TestClient(web_app)


def test_health():
    r = api_client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_api_health():
    r = api_client.get('/api/health')
    assert r.status_code == 200


def test_converter_health():
    r = web_client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'
