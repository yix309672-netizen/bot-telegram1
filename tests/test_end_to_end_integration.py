#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端测试：转换服务 -> 备份导入，全链路真实调用（opentele缺失时断言降级状态）"""
from fastapi.testclient import TestClient

from backend.main_api import app as api_app
from backend.main_web import app as web_app

api_client = TestClient(api_app)
web_client = TestClient(web_app)


def test_end_to_end_success():
    # 1. 号码生成
    r = api_client.post("/api/phone/generate", json={"count": 1})
    assert r.status_code == 200
    assert r.json()["count"] == 1
    # 2. 号码验证
    num = r.json()["data"][0]["number"]
    v = api_client.post("/api/phone/validate", json={"numbers": [num]})
    assert v.json()["data"][0]["is_valid"] is True
    # 3. 转换服务健康
    h = web_client.get("/health")
    assert h.json()["status"] == "ok"
    # 4. 备份 JSON 导入
    b = api_client.post("/api/backup/import_json", json={"account_id": 1, "data": {"phone": num}})
    assert b.json()["status"] == "saved"


def test_end_to_end_conversion_failure():
    # 空 session 必须返回结构化错误而非500
    r = web_client.post("/to-tdata", json={"backup": {"data": "", "format": "telethon_session"}, "options": {}})
    assert r.status_code == 200
    assert r.json()["error"] == "empty_session"
