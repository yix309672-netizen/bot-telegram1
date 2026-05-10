# ============================================================================
# JWT Token 管理 - 企业级实现
# ============================================================================

import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class JWTManager:
    """JWT Token 管理器"""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """初始化 JWT 管理器"""
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_access_token(
        self,
        user_id: int,
        username: str,
        role: str = "user",
        expires_delta: Optional[timedelta] = None,
        additional_claims: Dict[str, Any] = None
    ) -> str:
        """创建访问 Token"""
        if expires_delta is None:
            expires_delta = timedelta(minutes=15)
        
        expire = datetime.utcnow() + expires_delta
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "type": "access",
            "iat": datetime.utcnow(),
            "exp": expire,
            "iss": "TeleBot",
            "aud": "TeleBot-API"
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        try:
            token = jwt.encode(
                payload,
                self.secret_key,
                algorithm=self.algorithm
            )
            logger.info(f"创建 Access Token: user_id={user_id}")
            return token
        except Exception as e:
            logger.error(f"Token 创建失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token 创建失败"
            )
    
    def create_refresh_token(
        self,
        user_id: int,
        username: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """创建刷新 Token"""
        if expires_delta is None:
            expires_delta = timedelta(days=7)
        
        expire = datetime.utcnow() + expires_delta
        payload = {
            "sub": str(user_id),
            "username": username,
            "type": "refresh",
            "iat": datetime.utcnow(),
            "exp": expire,
            "iss": "TeleBot",
            "aud": "TeleBot-API"
        }
        
        try:
            token = jwt.encode(
                payload,
                self.secret_key,
                algorithm=self.algorithm
            )
            logger.info(f"创建 Refresh Token: user_id={user_id}")
            return token
        except Exception as e:
            logger.error(f"Refresh Token 创建失败: {e}")
            raise
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """验证 Token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "require": ["exp", "iat", "sub"]
                }
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning(f"Token 已过期")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 已过期"
            )
        except jwt.InvalidSignatureError:
            logger.warning(f"Token 签名无效")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 签名无效"
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token 无效: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token 无效"
            )
