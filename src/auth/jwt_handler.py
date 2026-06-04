"""JWT 令牌处理 —— 生成、验证、解析"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from src.config.settings import JWT_CONFIG


class JWTHandler:
    """JWT 令牌管理器"""

    SECRET_KEY = JWT_CONFIG["secret_key"]
    ALGORITHM = JWT_CONFIG["algorithm"]
    EXPIRE_MINUTES = JWT_CONFIG["access_token_expire_minutes"]

    @classmethod
    def create_access_token(cls, data: dict) -> str:
        """创建访问令牌
        Args:
            data: 包含 'sub' (username) 和 'role' 的字典
        Returns:
            JWT 字符串
        """
        to_encode = data.copy()
        to_encode["jti"] = uuid.uuid4().hex
        to_encode["iat"] = datetime.now(timezone.utc)
        to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=cls.EXPIRE_MINUTES)
        return jwt.encode(to_encode, cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    @classmethod
    def decode_token(cls, token: str) -> Optional[dict]:
        """解码并验证令牌
        Args:
            token: JWT 字符串
        Returns:
            解码后的 payload 字典，无效时返回 None
        """
        try:
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    @classmethod
    def get_token_from_header(cls, authorization: Optional[str]) -> Optional[str]:
        """从 Authorization header 提取 Bearer token"""
        if not authorization:
            return None
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        return parts[1]

    @classmethod
    def get_token_jti(cls, payload: dict) -> Optional[str]:
        """从 payload 中提取 JWT ID"""
        return payload.get("jti")
