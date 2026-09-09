# ============================================================================
# 企业级安全配置 - 完全兼容现有 .env 文件
# ============================================================================

import os
import secrets
from datetime import timedelta
from typing import List
from functools import lru_cache

class SecurityConfig:
    """
    安全配置类 - 兼容现有环境变量
    
    说明：
    - 使用现有的 .env 变量（如 JWT_SECRET, DB_HOST 等）
    - 添加新的安全变量，都有默认值
    - 不会改动现有的 bot.py 和 main_api.py
    - 完全向后兼容
    """
    
    # ===== 基础配置 =====
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # ===== 密钥管理 =====
    # 使用现有的 JWT_SECRET，如果没有则生成新的
    SECRET_KEY: str = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", secrets.token_urlsafe(32)))
    
    # 新增加密密钥（用于字段加密）
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", secrets.token_urlsafe(32))
    
    # ===== 现有数据库配置（保持兼容）=====
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "telegram")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "telegrampass")
    DB_NAME: str = os.getenv("DB_NAME", "telegramdb")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    
    # ===== Redis（保持兼容）=====
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_URL: str = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
    
    # ===== JWT 配置 =====
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_BLACKLIST_ENABLED: bool = True
    
    # ===== CORS 配置 =====
    ALLOWED_ORIGINS: List[str] = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000"
    ).split(",")
    
    ALLOWED_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    ALLOWED_HEADERS: List[str] = [
        "Content-Type",
        "Authorization",
        "X-Request-ID",
        "X-CSRF-Token"
    ]
    
    # ===== 速率限制 =====
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60
    
    # ===== 密码策略 =====
    MIN_PASSWORD_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    
    # ===== 登录安全 =====
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_ATTEMPT_LOCK_MINUTES: int = 15
    SESSION_TIMEOUT_MINUTES: int = 30
    
    # ===== API 签名 =====
    API_SIGNATURE_ENABLED: bool = os.getenv("API_SIGNATURE_ENABLED", "true").lower() == "true"
    API_SIGNATURE_TTL: int = 300
    
    # ===== 日志 =====
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    AUDIT_LOG_ENABLED: bool = True
    LOG_SENSITIVE_DATA: bool = False
    
    # ===== 文件上传 =====
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [".da", ".session", ".json"]
    
    # ===== 安全响应头 =====
    SECURITY_HEADERS: dict = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }

@lru_cache
def get_security_config():
    """获取安全配置（缓存）"""
    return SecurityConfig()
