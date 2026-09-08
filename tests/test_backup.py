# coding=utf-8
"""备份接口测试：文件上传与JSON导入"""
from fastapi.testclient import TestClient
from backend.main_api import app

client = TestClient(app)


def test_backup_import():
    # 真实 multipart 上传，路径应为 /api/backup/import
    r = client.post('/api/backup/import', files={'file': ('backup.bin', b'data')})
    assert r.status_code == 200
    assert r.json()['status'] == 'saved'


def test_backup_import_json():
    r = client.post('/api/backup/import_json', json={'account_id': 1, 'data': {'foo': 'bar'}})
    assert r.status_code == 200
    assert r.json()['status'] == 'saved'


def test_backup_path_traversal_rejected():
    # 路径穿越文件名必须被拒绝
    r = client.post('/api/backup/import', files={'file': ('../../evil.py', b'data')})
    assert r.status_code in (400, 422)


def test_backup_download_requires_login():
    # 未登录不许下
    assert client.get('/api/backup/download/backup.bin').status_code == 401
    assert client.get('/api/backup/download/nope.bin').status_code == 401


def test_backup_download_roundtrip():
    # 上传→登录下载→内容一致→清理
    assert client.post('/api/backup/import', files={'file': ('dl_test.txt', b'abc123')}).status_code == 200
    login = client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'})
    ck = {'access_token': login.cookies.get('access_token')}
    c2 = TestClient(app)
    r = c2.get('/api/backup/download/dl_test.txt', cookies=ck)
    assert r.status_code == 200 and r.content == b'abc123'
    assert client.post('/api/backup/import', files={'file': ('t.db', b'x')}).status_code == 200
    assert c2.get('/api/backup/download/t.db', cookies=ck).status_code == 400
    assert c2.get('/api/backup/download/nope.txt', cookies=ck).status_code == 404
    # .db 受删/下双重保护，测试件直接清文件
    import os
    from backend.main_api import BACKUP_DIR
    for f in ('t.db', 'dl_test.txt'):
        p = os.path.join(BACKUP_DIR, f)
        if os.path.isfile(p):
            os.remove(p)


def test_backups_page_has_download():
    r = client.get('/backups')
    assert r.status_code == 200 and '下载' in r.text and 'delBackup' in r.text


def test_bundle_requires_login_and_valid_phone():
    assert client.get('/api/backup/bundle/66989453470').status_code == 401
    login = client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'})
    ck = {'access_token': login.cookies.get('access_token')}
    c2 = TestClient(app)
    assert c2.get('/api/backup/bundle/abc', cookies=ck).status_code == 422
    assert c2.get('/api/backup/bundle/00000', cookies=ck).status_code == 404
