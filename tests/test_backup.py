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
