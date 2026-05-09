#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 测试脚本"""
import requests
import json

print("=== 测试生成号码 ===")
r = requests.post('http://localhost:8000/phone/generate', json={'count': 5})
print(r.text)

print("\n=== 测试号码列表 ===")
r2 = requests.get('http://localhost:8000/phone/list')
print(r2.text)

print("\n=== 测试发送短信 ===")
r3 = requests.post('http://localhost:8000/sms/send', json={'phone': '85212345678', 'content': 'Test message', 'sender': 'TestBot'})
print(r3.text)

print("\n=== 测试短信列表 ===")
r4 = requests.get('http://localhost:8000/sms/list')
print(r4.text)