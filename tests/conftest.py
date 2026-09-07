# coding=utf-8
"""pytest全局前置：锁定测试用环境变量（先于app导入，不会被.env覆盖）"""
import os

os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "")
os.environ.setdefault("ENABLE_AUTH", "false")
os.environ.setdefault("API_KEY", "")
os.environ.setdefault("JWT_SECRET", "pytest-fixed-test-secret")
os.environ.setdefault("RATE_LIMIT_REQUESTS", "100")
