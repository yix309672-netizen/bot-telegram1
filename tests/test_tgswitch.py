# coding=utf-8
"""多号切换接口测试（只验名单与校验，不真切）"""
from fastapi.testclient import TestClient

import backend.main_api as m
from backend.core.cache import cache
from backend.main_api import app

import pytest

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_lock():
    # 防爆破锁被同进程其他测试触发，每个用例前清
    cache.delete('login_fail:testclient')
    yield


def test_accounts_requires_login():
    assert client.get('/api/telegram/accounts').status_code == 401


def test_accounts_list():
    login = client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'})
    ck = {'access_token': login.cookies.get('access_token')}
    c2 = TestClient(app)
    d = c2.get('/api/telegram/accounts', cookies=ck).json()['data']
    phones = {x['phone'] for x in d}
    assert '66989453470' in phones and '+66804938604' in phones
    kinds = {x['phone']: x['tdata'] for x in d}
    assert kinds['66989453470'] == 'full'


def test_switch_validation(monkeypatch):
    login = client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'})
    ck = {'access_token': login.cookies.get('access_token')}
    c2 = TestClient(app)
    assert c2.post('/api/telegram/switch', json={'phone': 'abc'}, cookies=ck).status_code == 422
    assert c2.post('/api/telegram/switch', json={'phone': '00000'}, cookies=ck).status_code == 404
    # 开鉴权后匿名应拒
    monkeypatch.setattr(m, 'ENABLE_AUTH', True)
    monkeypatch.setattr(m, 'API_KEY', 'swkey')
    assert TestClient(app).post('/api/telegram/switch', json={'phone': '66989453470'}).status_code in (401, 403)
    assert TestClient(app).get('/api/telegram/accounts').status_code == 401
