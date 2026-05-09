#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动独立会话转换服务（FastAPI）的小工具"""
import subprocess
import sys
import os

def main():
    base_dir = os.path.join(os.path.dirname(__file__), 'converter-service')
    cmd = [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8002', '--reload']
    print(f"[启动] 转换服务将在 {base_dir} 目录下启动，命令：{cmd}")
    proc = subprocess.Popen(cmd, cwd=base_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(f"[信息] 进程ID: {proc.pid}")

if __name__ == '__main__':
    main()