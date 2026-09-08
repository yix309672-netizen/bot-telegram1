# coding=utf-8
"""机器人三件套：查看脱敏/保存校验（写临时文件，不碰真.env）"""
import os
from fastapi.testclient import TestClient

import backend.main_api as m

client = TestClient(m.app)
TMP = r'C:\Users\39712\AppData\Local\Temp\opencode\fakebot.env'


def _fake_env(monkeypatch, content="BOT_TOKEN=111:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nAPI_ID=12345\nAPI_HASH=abcdef0123456789abcdef0123456789\n"):
    with open(TMP, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    monkeypatch.setattr(m, '_bot_env_file', lambda: TMP)


def test_env_info_masked(monkeypatch):
    _fake_env(monkeypatch)
    d = client.get('/api/bot/env').json()
    assert d['bot_token_ok'] is True and '****' in d['bot_token_masked']
    assert d['api_id'] == '12345' and '****' in d['api_hash_masked']


def test_env_save_validation(monkeypatch):
    _fake_env(monkeypatch)
    assert client.put('/api/bot/env', json={}).status_code == 422
    assert client.put('/api/bot/env', json={'bot_token': 'bad'}).status_code == 422
    assert client.put('/api/bot/env', json={'api_id': 'abc'}).status_code == 422
    assert client.put('/api/bot/env', json={'api_hash': 'zzz'}).status_code == 422


def test_env_save_roundtrip(monkeypatch):
    _fake_env(monkeypatch)
    r = client.put('/api/bot/env', json={'api_id': '99999'})
    assert r.status_code == 200 and r.json()['keys'] == ['API_ID']
    txt = open(TMP, encoding='utf-8').read()
    assert 'API_ID=99999' in txt and 'BOT_TOKEN=111:' in txt
    if os.path.isfile(TMP):
        os.remove(TMP)
    if os.path.isfile(TMP + '.bak'):
        os.remove(TMP + '.bak')
