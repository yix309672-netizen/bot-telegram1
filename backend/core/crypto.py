# ============================================================================
# 加密和密钥管理 - 企业级实现
# ============================================================================

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend
from passlib.context import CryptContext
import base64
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# 密码加密上下文（Argon2 最安全）
try:
    pwd_context = CryptContext(
        schemes=["argon2", "bcrypt"],
        deprecated="auto"
    )
except Exception as e:
    logger.warning(f"Argon2 不可用，使用 bcrypt: {e}")
    pwd_context = CryptContext(
        schemes=["bcrypt"],
        deprecated="auto"
    )

class EncryptionManager:
    """字段级加密管理"""
    
    def __init__(self, encryption_key: str):
        """初始化加密管理器"""
        try:
            key = encryption_key.encode()
            salt = b'telegram_secure_'  # 实际生产环境应使用随机盐
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            derived_key = base64.urlsafe_b64encode(kdf.derive(key))
            self.cipher_suite = Fernet(derived_key)
        except Exception as e:
            logger.error(f"加密管理器初始化失败: {e}")
            raise
    
    def encrypt(self, data: str) -> str:
        """加密字符串"""
        try:
            encrypted = self.cipher_suite.encrypt(data.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"加密失败: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """解密字符串"""
        try:
            decrypted = self.cipher_suite.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"解密失败: {e}")
            raise

class PasswordManager:
    """密码管理"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """使用 Argon2/bcrypt 加密密码"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.warning(f"密码验证异常: {e}")
            return False
    
    @staticmethod
    def validate_password_strength(password: str, config=None) -> Tuple[bool, str]:
        """验证密码强度"""
        errors = []
        
        # 使用默认配置
        min_length = 12 if config is None else config.MIN_PASSWORD_LENGTH
        require_uppercase = True if config is None else config.PASSWORD_REQUIRE_UPPERCASE
        require_numbers = True if config is None else config.PASSWORD_REQUIRE_NUMBERS
        require_special = True if config is None else config.PASSWORD_REQUIRE_SPECIAL
        
        if len(password) < min_length:
            errors.append(f"密码至少需要 {min_length} 个字符")
        
        if require_uppercase and not any(c.isupper() for c in password):
            errors.append("密码需要至少一个大写字母")
        
        if require_numbers and not any(c.isdigit() for c in password):
            errors.append("密码需要至少一个数字")
        
        if require_special and not any(c in "!@#$%^&*_-" for c in password):
            errors.append("密码需要至少一个特殊字符 (!@#$%^&*_-)")
        
        return len(errors) == 0, " | ".join(errors) if errors else ""
