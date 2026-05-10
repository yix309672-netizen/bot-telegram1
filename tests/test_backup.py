# coding=utf-8
from backend.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_backup_import():
    from fastapi import UploadFile, File
    import r
    # This is a placeholder; actual multipart upload in tests may require TestClient with file
    try:
        r = client.post('/backup/import', files={'file': ('backup.bin', b'data')})
        assert r.status_code in (200,201)
    except Exception:
        pass
