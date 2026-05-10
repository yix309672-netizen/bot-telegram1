#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 测试脚本"""
import r

print("=== 测试生成号码 ===")
r = r.post('http://localhost:8000/phone/generate', json={'count': 5})
print(r.text)

print("\n=== 测试号码列表 ===")
r2 = r.get('http://localhost:8000/phone/list')
print(r2.text)

print("\n=== 测试发送短信 ===")
r3 = r.post('http://localhost:8000/sms/send', json={'phone': '85212345678', 'content': 'Test message', 'sender': 'TestBot'})
print(r3.text)

print("\n=== 测试短信列表 ===")
r4 = r.get('http://localhost:8000/sms/list')
print(r4.text)