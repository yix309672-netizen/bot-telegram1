# coding=utf-8
"""BOT控制台/生成验证导入/转换/系统/商城/桌面单页测试"""
from fastapi.testclient import TestClient
from backend.main_api import app
from backend.ops_pages import html_bot, html_phone_tool, html_convert, html_system, html_mall, html_desktop

client = TestClient(app)


def _ck():
    login = client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'})
    return {'access_token': login.cookies.get('access_token')}


def test_ops_pages_require_login():
    for p in ('/admin/bot', '/admin/phone-tool', '/admin/convert', '/admin/system',
              '/admin/mall', '/admin/desktop'):
        assert TestClient(app).get(p).status_code == 401, p


def test_ops_pages_content():
    ck = _ck()
    c2 = TestClient(app)
    b = c2.get('/admin/bot', cookies=ck).text
    assert 'bot-grid' in b and 'botAdd' in b and 'botStart' in b and 'botDel' in b and 'botLog' in b
    p = c2.get('/admin/phone-tool', cookies=ck).text
    assert 'toolGenerate' in p and 'toolValidate' in p and 'toolImport' in p
    assert 'convGo' in c2.get('/admin/convert', cookies=ck).text
    s = c2.get('/admin/system', cookies=ck).text
    assert 'cfgSave' in s and 'userAdd' in s and 'auditLoad' in s
    assert 'mallLoad' in c2.get('/admin/mall', cookies=ck).text
    assert 'tgSwitch' in c2.get('/admin/desktop', cookies=ck).text


def test_shell_nav_grouped():
    ck = _ck()
    shell = TestClient(app).get('/admin/', cookies=ck).text
    for nav in ('/admin/console', '/admin/bot', '/admin/phone-tool', '/admin/sms',
                '/admin/convert', '/admin/phones', '/admin/backups', '/admin/system',
                '/admin/mall', '/admin/desktop', '/docs'):
        assert f'data-src="{nav}"' in shell, nav
    for g in ('监控', '操作', '管理'):
        assert g in shell
    assert '#' not in ''.join(
        l for l in shell.split('\n') if 'data-src' in l), '侧栏不应再有锚点链接'
