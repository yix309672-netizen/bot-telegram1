# coding=utf-8
"""限流 / 审计 / argon2 密码登录测试"""
from fastapi.testclient import TestClient

import backend.main_api as m
from backend.core.cache import cache
from backend.core.database import SessionLocal, AuditLog


def test_rate_limit_429():
    # 临时调低阈值验证超限拒绝，事后恢复并清计数（开测也先清，避免被其他用例的计数污染）
    old = m.RATE_LIMIT_REQUESTS
    m.RATE_LIMIT_REQUESTS = 5
    cache.delete('ratelimit:testclient')
    try:
        c = TestClient(m.app)
        codes = [c.get('/api/phone/list').status_code for _ in range(7)]
        assert codes[:5] == [200] * 5
        assert codes[5] == 429 and codes[6] == 429
    finally:
        m.RATE_LIMIT_REQUESTS = old
        cache.delete('ratelimit:testclient')


def test_audit_logged():
    # 变更请求落审计表
    db = SessionLocal()
    before = db.query(AuditLog).count()
    c = TestClient(m.app)
    c.post('/api/phone/generate', json={'count': 1})
    after = db.query(AuditLog).count()
    row = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    db.close()
    assert after == before + 1
    assert row.path == '/api/phone/generate' and row.method == 'POST'


def test_argon2_password_login(monkeypatch):
    # 生产哈希密码可登录
    from backend.core.crypto import PasswordManager
    monkeypatch.setattr(m, 'ADMIN_PASSWORD_HASH', PasswordManager.hash_password('S3cret!Passw0rd'))
    c = TestClient(m.app)
    r = c.post('/admin/login', data={'username': 'admin', 'password': 'S3cret!Passw0rd'})
    assert '管理后台' in r.text
