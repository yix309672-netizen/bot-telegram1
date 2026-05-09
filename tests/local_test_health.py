#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 健康接口测试（本地部署分支命名避免命名冲突）
"""

import pytest
import requests
import time

BASE_URL = "http://localhost:8000"

def test_health_endpoint():
    """测试健康检查接口"""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok" or data.get("status") == "healthy"

def test_root_endpoint():
    """测试根路径接口"""
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "endpoints" in data

def test_health_response_time():
    """测试健康接口响应时间"""
    start = time.time()
    response = requests.get(f"{BASE_URL}/health")
    elapsed = time.time() - start
    assert response.status_code == 200
    assert elapsed < 1.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
