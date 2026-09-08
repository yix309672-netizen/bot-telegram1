# coding=utf-8
"""BOT控制台与生成验证单页测试"""
from fastapi.testclient import TestClient
from backend.main_api import app
from backend.ops_pages import html_bot, html_phone_tool

client = TestClient(app)


def test_ops_pages_require_login():
    assert TestClient(app).get('/admin/bot').status_code == 401
    assert TestClient(app).get('/admin/phone-tool').status_code == 401


def test_ops_pages_content():
    login = client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'})
    ck = {'access_token': login.cookies.get('access_token')}
    c2 = TestClient(app)
    b = c2.get('/admin/bot', cookies=ck).text
    assert 'botRefresh' in b and 'botStart' in b and 'botStop' in b and 'botlog' in b
    p = c2.get('/admin/phone-tool', cookies=ck).text
    assert 'toolGenerate' in p and 'toolValidate' in p and 'gen-count' in p


def test_shell_nav_has_seven():
    login = client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'})
    ck = {'access_token': login.cookies.get('access_token')}
    shell = TestClient(app).get('/admin/', cookies=ck).text
    for nav in ('/admin/console', '/admin/bot', '/admin/phone-tool', '/admin/phones',
                '/admin/sms', '/admin/backups', '/docs'):
        assert f'data-src="{nav}"' in shell
