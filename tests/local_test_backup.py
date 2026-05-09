#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
备份导入接口测试
"""

import pytest
import requests
import json

BASE_URL = "http://localhost:8000"

def test_backup_import():
    """测试备份导入接口"""
    test_data = "test backup data"
    response = requests.post(
        f"{BASE_URL}/backup/import",
        json={"data": test_data}
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["data_length"] == len(test_data)

def test_json_backup_import():
    """测试 JSON 备份导入接口"""
    test_json = {
        "users": [{"id": 1, "name": "test"}],
        "settings": {"theme": "dark"}
    }
    response = requests.post(
        f"{BASE_URL}/backup/import_json",
        json=test_json
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "keys" in data
    assert set(data["keys"]) == set(test_json.keys())

def test_backup_import_empty():
    """测试空数据导入"""
    response = requests.post(
        f"{BASE_URL}/backup/import",
        json={"data": ""}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data_length"] == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
