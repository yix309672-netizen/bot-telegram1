# ============================================================================
# 安全工具函数
# ============================================================================

import hmac
import hashlib
import logging
import uuid
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Request

logger = logging.getLogger(__name__)

class SecurityUtils:
    """安全工具类"""
    
    @staticmethod
    def get_client_ip(request: Request) -> str:
        """获取真实客户端 IP"""
        # 优先使用 X-Forwarded-For（代理情况）
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        
        # 其次使用 X-Real-IP
        x_real_ip = request.headers.get("X-Real-IP")
        if x_real_ip:
            return x_real_ip
        
        # 最后使用 client 信息
        return request.client.host if request.client else "unknown"
    
    @staticmethod
    def generate_request_id() -> str:
        """生成请求 ID"""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_signature(method: str, path: str, body: str, timestamp: str, secret: str) -> str:
        """生成请求签名"""
        signature_string = f"{method}\n{path}\n{body}\n{timestamp}"
        signature = hmac.new(
            secret.encode(),
            signature_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    @staticmethod
    def verify_signature_timing(timestamp: str, ttl: int = 300) -> bool:
        """验证时间戳有效性（防重放）"""
        try:
            ts = int(timestamp)
            now = datetime.utcnow().timestamp()
            return abs(now - ts) <= ttl
        except:
            return False
    
    @staticmethod
    def sanitize_sensitive_data(data: dict, sensitive_fields: list = None) -> dict:
        """脱敏敏感数据"""
        if sensitive_fields is None:
            sensitive_fields = [
                'password', 'password_hash', 'api_hash', 'phone_number',
                'session_string', 'mfa_secret', 'credit_card', 'ssn'
            ]
        
        sanitized = data.copy()
        for field in sensitive_fields:
            if field in sanitized:
                if isinstance(sanitized[field], str):
                    # 显示前4个和后4个字符
                    if len(sanitized[field]) > 8:
                        sanitized[field] = f"{sanitized[field][:4]}***{sanitized[field][-4:]}"
                    else:
                        sanitized[field] = "***REDACTED***"
                else:
                    sanitized[field] = "***REDACTED***"
        
        return sanitized
