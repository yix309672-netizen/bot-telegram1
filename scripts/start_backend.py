#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一后端启动入口（R1起展示页与转换服务已并入8000，无需独立8002服务）"""
import os
import subprocess
import sys


def main():
    # 项目根目录（scripts 的上一级），服务模块为 backend.main_api
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    port = os.getenv("API_PORT", "8000")
    cmd = [sys.executable, '-m', 'uvicorn', 'backend.main_api:app',
           '--host', '0.0.0.0', '--port', str(port)]
    print(f"[启动] 统一后端（含展示页/转换服务），命令：{' '.join(cmd)}，目录：{root}")
    print(f"[信息] 管理页：http://localhost:{port}/admin/login，健康检查：http://localhost:{port}/health")
    proc = subprocess.Popen(cmd, cwd=root)
    print(f"[信息] 进程ID: {proc.pid}")


if __name__ == '__main__':
    main()
