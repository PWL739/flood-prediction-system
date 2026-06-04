"""两级预测结果缓存 —— L1 内存 + L2 Redis"""

import hashlib
import json
import time
import logging
from collections import OrderedDict
from typing import Optional

from src.config.settings import CACHE_CONFIG
from src.db.redis_client import redis_client

logger = logging.getLogger(__name__)


class PredictionCache:
    """两级缓存: L1 (内存 OrderedDict LRU) + L2 (Redis)"""

    def __init__(self):
        self._l1_cache: OrderedDict[str, tuple[dict, float]] = OrderedDict()
        self._max_size = CACHE_CONFIG["l1_max_size"]
        self._l1_ttl = CACHE_CONFIG["l1_ttl_seconds"]
        self._l2_ttl = CACHE_CONFIG["l2_ttl_seconds"]
        self._l2_prefix = CACHE_CONFIG["l2_key_prefix"]
        self._hits = 0
        self._misses = 0

    @staticmethod
    def compute_hash(features_array) -> str:
        """计算输入特征数组的 SHA256 哈希"""
        raw_bytes = features_array.astype("float32").tobytes()
        return hashlib.sha256(raw_bytes).hexdigest()[:16]

    def _make_key(self, station_id: str, input_hash: str) -> str:
        return f"{station_id}:{input_hash}"

    def _make_l2_key(self, station_id: str, input_hash: str) -> str:
        return f"{self._l2_prefix}:{station_id}:{input_hash}"

    def _l1_get(self, key: str) -> Optional[dict]:
        """L1 内存缓存查询"""
        if key not in self._l1_cache:
            return None
        result, created_at = self._l1_cache[key]
        if time.time() - created_at > self._l1_ttl:
            del self._l1_cache[key]
            return None
        # LRU: move to end
        self._l1_cache.move_to_end(key)
        return result

    def _l1_set(self, key: str, result: dict):
        """L1 内存缓存写入"""
        if key in self._l1_cache:
            self._l1_cache.move_to_end(key)
            self._l1_cache[key] = (result, time.time())
            return
        if len(self._l1_cache) >= self._max_size:
            self._l1_cache.popitem(last=False)  # 淘汰最旧
        self._l1_cache[key] = (result, time.time())

    def _l2_get(self, station_id: str, input_hash: str) -> Optional[dict]:
        """L2 Redis 缓存查询"""
        key = self._make_l2_key(station_id, input_hash)
        raw = redis_client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def _l2_set(self, station_id: str, input_hash: str, result: dict):
        """L2 Redis 缓存写入"""
        key = self._make_l2_key(station_id, input_hash)
        redis_client.set(key, json.dumps(result, ensure_ascii=False, default=str), ttl=self._l2_ttl)

    def get(self, station_id: str, input_hash: str) -> Optional[dict]:
        """两级缓存查询"""
        cache_key = self._make_key(station_id, input_hash)

        # L1 查询
        result = self._l1_get(cache_key)
        if result is not None:
            self._hits += 1
            return result

        # L2 查询
        result = self._l2_get(station_id, input_hash)
        if result is not None:
            self._hits += 1
            self._l1_set(cache_key, result)  # 回填 L1
            return result

        self._misses += 1
        return None

    def set(self, station_id: str, input_hash: str, result: dict):
        """写入两级缓存"""
        cache_key = self._make_key(station_id, input_hash)
        self._l1_set(cache_key, result)
        self._l2_set(station_id, input_hash, result)

    def invalidate_station(self, station_id: str):
        """清除指定站点的所有缓存（L1 + L2）"""
        # 清除 L1
        keys_to_remove = [k for k in self._l1_cache if k.startswith(f"{station_id}:")]
        for k in keys_to_remove:
            del self._l1_cache[k]

        # 清除 L2
        pattern = f"{self._l2_prefix}:{station_id}:*"
        removed = redis_client.delete_pattern(pattern)
        logger.info("缓存清除: station=%s, L1=%d, L2=%d",
                     station_id, len(keys_to_remove), removed)

    def stats(self) -> dict:
        """缓存统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": round(hit_rate, 4),
            "l1_size": len(self._l1_cache),
            "l1_max_size": self._max_size,
        }
