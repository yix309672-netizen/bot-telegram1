#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简单的 HTTP 测试脚本，调用 /to-tdata 接口进行基本响应测试"""
import json
import urllib.request

def main():
    url = 'http://127.0.0.1:8002/to-tdata'
    payload = {'backup': {'data': '示例数据', 'format': 'json'}, 'options': {}}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        print(resp.read().decode())

if __name__ == '__main__':
    main()