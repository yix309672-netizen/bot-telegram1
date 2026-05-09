#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 Python 直接请求 /to-tdata 的快速测试脚本"""
import json
import urllib.request

def main():
    url = 'http://127.0.0.1:8002/to-tdata'
    payload = {'backup': {'data': '示例数据', 'format': 'json'}, 'options': {}}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(resp.read().decode())
    except Exception as e:
        print('请求失败:', e)

if __name__ == '__main__':
    main()