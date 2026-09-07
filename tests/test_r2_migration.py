# coding=utf-8
"""R2迁移测试：配置/上传/审计/机器人/账号RBAC/商城/备份"""
from fastapi.testclient import TestClient

import backend.main_api as m
from backend.core.database import SessionLocal, AdminUser

client = TestClient(m.app)


def _admin_cookies():
    r = client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'})
    return {'access_token': r.cookies.get('access_token')}


def test_config_roundtrip():
    assert client.put('/api/system/config', json={'key': 'ut_key', 'value': 'v1'}).status_code == 200
    assert any(i['key'] == 'ut_key' for i in client.get('/api/system/config').json()['data'])
    assert client.put('/api/system/config', json={'key': '', 'value': 'x'}).status_code == 422


def test_upload_and_list():
    r = client.post('/api/upload', files={'file': ('ut.txt', b'hello')})
    assert r.status_code == 200
    assert client.get('/api/upload/list').json()['total'] >= 1


def test_audit_and_botlog_require_login():
    assert client.get('/api/audit/logs').status_code == 401
    ck = _admin_cookies()
    assert client.get('/api/audit/logs', cookies=ck).json()['total'] >= 1
    assert client.get('/api/bot/log', cookies=ck).json().get('log')


def test_phone_update():
    g = client.post('/api/phone/generate', json={'count': 1}).json()['data'][0]
    assert client.put(f"/api/phone/{g['id']}", json={'status': 'valid'}).status_code == 200
    assert client.put(f"/api/phone/{g['id']}", json={'status': 'nope'}).status_code == 422
    assert client.put('/api/phone/999999999', json={'status': 'valid'}).status_code == 404


def test_backup_delete():
    assert client.post('/api/backup/import', files={'file': ('ut_del.txt', b'x')}).status_code == 200
    assert client.delete('/api/backup/ut_del.txt').json()['message'] == '删除成功'
    assert client.delete('/api/backup/ut_del.txt').status_code == 404


def test_users_rbac(monkeypatch):
    # 建账号（幂等）
    r = client.post('/api/users', json={'username': 'ut_op', 'password': 'op123456', 'role': 'operator'})
    assert r.status_code in (200, 409)
    db = SessionLocal()
    uid = db.query(AdminUser).filter(AdminUser.username == 'ut_op').first().id
    db.close()
    # 开鉴权验矩阵
    monkeypatch.setattr(m, 'ENABLE_AUTH', True)
    monkeypatch.setattr(m, 'API_KEY', 'utkey')
    op = TestClient(m.app)
    tok = op.post('/admin/login', data={'username': 'ut_op', 'password': 'op123456'}).cookies.get('access_token')
    assert tok
    c_op = TestClient(m.app)
    g = client.post('/api/phone/generate', json={'count': 1},
                    headers={'X-API-Key': 'utkey'}).json()['data'][0]
    assert c_op.delete(f"/api/phone/{g['id']}", cookies={'access_token': tok}).status_code == 403
    assert c_op.get('/api/phone/list', cookies={'access_token': tok}).status_code == 200
    assert TestClient(m.app).get('/api/phone/list').status_code == 401
    adm = TestClient(m.app).post('/admin/login', data={'username': 'admin', 'password': 'admin123'})
    assert TestClient(m.app).delete(
        f"/api/phone/{g['id']}", cookies={'access_token': adm.cookies.get('access_token')}).status_code == 200


def test_mall_crud():
    c = client.post('/api/mall/cate', json={'title': 'ut分类'})
    assert c.status_code in (200, 409)
    assert client.post('/api/mall/cate', json={'title': ''}).status_code == 422
    g = client.post('/api/mall/goods', json={'title': 'ut商品', 'price': 1.5, 'stock': 2})
    assert g.status_code == 200
    assert len(client.get('/api/mall/goods').json()['data']) >= 1
    assert client.delete(f"/api/mall/goods/{g.json()['id']}").status_code == 200
