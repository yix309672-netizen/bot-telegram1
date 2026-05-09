# coding=utf-8
import requests

BASE = 'https://your-domain.com'
def test_health():
    r = requests.get(f"{BASE}/health", timeout=5, verify=False)
    assert r.status_code == 200 or r.status_code == 403 or r.status_code == 401

def test_backup_upload():
    # 仅示意：实际上传需提供一个小文件
    url = f"{BASE}/backup/import"
    files = {'file': ('backup.dat', b'data')}
    r = requests.post(url, files=files, timeout=10, verify=False)
    assert r.status_code in (200, 201, 202)
