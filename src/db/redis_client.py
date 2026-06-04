"""Redis 连接管理 —— 单例模式，不可用时自动降级"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis-py 未安装，Redis 功能不可用")


class RedisClient:
    """Redis 客户端单例，不可用时返回 None 不抛异常"""

    _instance: Optional["RedisClient"] = None

    def __new__(cls) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
            cls._instance._available = False
            cls._instance._init_client()
        return cls._instance

    def _init_client(self):
        if not REDIS_AVAILABLE:
            return
        try:
            from src.config.settings import REDIS_CONFIG
            self._client = redis.Redis(
                host=REDIS_CONFIG["host"],
                port=REDIS_CONFIG["port"],
                db=REDIS_CONFIG["db"],
                password=REDIS_CONFIG["password"] or None,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            self._client.ping()
            self._available = True
            logger.info("Redis 连接成功: %s:%s", REDIS_CONFIG["host"], REDIS_CONFIG["port"])
        except Exception as e:
            self._available = False
            logger.warning("Redis 不可用，将使用降级模式: %s", e)

    @property
    def available(self) -> bool:
        return self._available and self._client is not None

    @property
    def client(self):
        """返回原始 redis 客户端，不可用时返回 None"""
        return self._client if self.available else None

    def get(self, key: str) -> Optional[str]:
        """获取缓存值，不可用时返回 None"""
        if not self.available:
            return None
        try:
            return self._client.get(key)
        except Exception as e:
            logger.warning("Redis GET 失败: %s", e)
            return None

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """设置缓存值，不可用时返回 False"""
        if not self.available:
            return False
        try:
            if ttl:
                self._client.setex(key, ttl, value)
            else:
                self._client.set(key, value)
            return True
        except Exception as e:
            logger.warning("Redis SET 失败: %s", e)
            return False

    def delete(self, key: str) -> bool:
        """删除缓存键，不可用时返回 False"""
        if not self.available:
            return False
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.warning("Redis DELETE 失败: %s", e)
            return False

    def delete_pattern(self, pattern: str) -> int:
        """按模式删除键，返回删除数量"""
        if not self.available:
            return 0
        try:
            keys = self._client.keys(pattern)
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning("Redis DELETE_PATTERN 失败: %s", e)
            return 0

    def lpush(self, key: str, value: str) -> bool:
        """列表左推入"""
        if not self.available:
            return False
        try:
            self._client.lpush(key, value)
            return True
        except Exception as e:
            logger.warning("Redis LPUSH 失败: %s", e)
            return False

    def health_check(self) -> bool:
        """健康检查"""
        if not self.available:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            self._available = False
            return False


# 全局单例
redis_client = RedisClient()
