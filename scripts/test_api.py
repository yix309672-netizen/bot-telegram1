#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主接口冒烟测试：健康→生成→验证→导入→短信→转换健康"""
import json
import os
import urllib.request

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
CONVERTER_URL = os.getenv("CONVERTER_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")


def call(method, url, payload=None):
    # 带鉴权头的通用调用
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.load(resp)


def main():
    print("=== 健康检查 ===")
    print(call("GET", API_URL + "/health"))
    print("\n=== 生成号码 ===")
    _, g = call("POST", API_URL + "/api/phone/generate", {"count": 2})
    print(g)
    num = g["data"][0]["number"]
    print("\n=== 验证号码 ===")
    print(call("POST", API_URL + "/api/phone/validate", {"numbers": [num, "123"]}))
    print("\n=== 导入号码 ===")
    print(call("POST", API_URL + "/api/phone/import", {"numbers": [num, "123"]}))
    print("\n=== 发送短信 ===")
    print(call("POST", API_URL + "/api/sms/send", {"phone": num, "content": "smoke test"}))
    print("\n=== 转换服务健康 ===")
    try:
        print(call("GET", CONVERTER_URL + "/health"))
    except Exception as e:
        print(f"转换服务未启动（先跑 scripts/start_converter.py）: {e}")


if __name__ == '__main__':
    main()
