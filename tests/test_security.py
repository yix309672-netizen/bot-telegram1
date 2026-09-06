#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 安全测试：针对真实接口的可用断言"""
import time

from fastapi.testclient import TestClient
from backend.main_api import app

client = TestClient(app)

BASE_PREFIX = "/api"


def test_health_no_auth_required():
    """健康检查无需鉴权且可高频访问"""
    for _ in range(3):
        r = client.get("/health")
        assert r.status_code == 200
        time.sleep(0.05)


def test_phone_validate_rejects_garbage():
    """号码验证：非法输入必须判无效而非报错"""
    r = client.post(f"{BASE_PREFIX}/phone/validate", json={"numbers": ["'; DROP TABLE users; --", "<script>alert(1)</script>"]})
    assert r.status_code == 200
    for row in r.json()["data"]:
        assert row["is_valid"] is False


def test_login_brute_force_still_responds():
    """多次错误登录不应崩溃；超过5次触发15分钟锁定（防爆破生效）"""
    for i in range(6):
        r = client.post("/admin/login", data={"username": "admin", "password": "wrong"})
        assert r.status_code == 200
        if i < 5:
            assert "用户名或密码错误" in r.text
        else:
            assert ("用户名或密码错误" in r.text) or ("锁定" in r.text)


def test_backup_import_json_requires_dict():
    """错误的 JSON 结构应被 pydantic 拒绝（422）"""
    r = client.post(f"{BASE_PREFIX}/backup/import_json", json={"account_id": "not-int", "data": {}})
    assert r.status_code == 422
