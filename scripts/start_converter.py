#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动独立会话转换服务（backend.main_web:app，端口8002）"""
import os
import subprocess
import sys


def main():
    # 项目根目录（scripts 的上一级），服务模块为 backend.main_web
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    port = os.getenv("CONVERTER_PORT", "8002")
    cmd = [sys.executable, '-m', 'uvicorn', 'backend.main_web:app',
           '--host', '0.0.0.0', '--port', str(port)]
    print(f"[启动] 转换服务，命令：{' '.join(cmd)}，目录：{root}")
    proc = subprocess.Popen(cmd, cwd=root)
    print(f"[信息] 进程ID: {proc.pid}，健康检查：http://localhost:{port}/health")


if __name__ == '__main__':
    main()
