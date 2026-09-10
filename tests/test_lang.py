# coding=utf-8
"""语言管理测试：接口+机器人语言包"""
import sys
sys.path.insert(0, r'C:\Users\39712\Desktop\bot-telegram1-main')
from fastapi.testclient import TestClient
from backend.main_api import app

client = TestClient(app)


def test_lang_list_shape():
    d = client.get('/api/lang/list').json()
    assert set(d['langs']) >= {'zh', 'en'} and d['default'] in d['langs']
    assert 'welcome' in d['builtin_keys'] and 'success' in d['builtin_keys']


def test_lang_override_roundtrip():
    assert client.put('/api/lang/override',
                      json={'lang': 'en', 'key': 'welcome', 'value': 'UT-WELCOME'}).status_code == 200
    assert client.put('/api/lang/override', json={'lang': 'xx', 'key': 'welcome', 'value': 'x'}).status_code == 422
    assert client.put('/api/lang/override', json={'lang': 'en', 'key': 'nope', 'value': 'x'}).status_code == 422
    ov = client.get('/api/lang/overrides').json()
    assert ov['en']['welcome'] == 'UT-WELCOME'
    rows = client.get('/api/lang/list').json()['data']
    oid = next(r['id'] for r in rows if r['lang'] == 'en' and r['key'] == 'welcome')
    assert client.delete(f'/api/lang/override/{oid}').status_code == 200
    assert client.delete('/api/lang/override/999999999').status_code == 404
    assert 'welcome' not in client.get('/api/lang/overrides').json().get('en', {})


def test_lang_default():
    assert client.get('/api/lang/default').json()['default'] in ('zh', 'en')
    assert client.put('/api/lang/default', json={'lang': 'en'}).status_code == 200
    assert client.get('/api/lang/default').json()['default'] == 'en'
    assert client.put('/api/lang/default', json={'lang': 'xx'}).status_code == 422
    assert client.put('/api/lang/default', json={'lang': 'zh'}).status_code == 200


def test_bot_lang_pack():
    sys.path.insert(0, r'C:\Users\39712\Desktop\bot-telegram1-main\bot')
    import lang as L
    assert set(L.STRINGS['zh']) == set(L.STRINGS['en'])
    assert L.t('en', 'welcome').startswith('Welcome')
    assert L.t('xx', 'welcome') == L.STRINGS['zh']['welcome']
    L.apply_overrides({'en': {'welcome': 'OVERRIDDEN'}})
    assert L.t('en', 'welcome') == 'OVERRIDDEN'
    L.OVERRIDES.clear()
    assert L.normalize_lang('English') == 'en' and L.normalize_lang('中文') == 'zh'
    assert L.normalize_lang('en-US') == 'en' and L.normalize_lang('qq') == 'zh'
