# Week 4 增强功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inference caching, CSV data import, JWT+RBAC auth, and operation logging middleware to the flood prediction system.

**Architecture:** Unified FastAPI middleware stack (OperationLog → Auth → Router). Redis as shared cache infrastructure. CSV import reuses existing data processing pipeline. Auth via JWT Bearer tokens with role-based dependency injection.

**Tech Stack:** FastAPI, PyJWT, passlib[bcrypt], Redis, SQLAlchemy, PyTorch, pandas

---

### Task 1: Update settings.py with new configuration

**Files:**
- Modify: `src/config/settings.py`

- [ ] **Step 1: Add new configuration blocks to settings.py**

Add the following blocks at the end of `src/config/settings.py` (append, do not delete anything):

```python
# JWT 认证配置
JWT_CONFIG = {
    "secret_key": os.getenv("JWT_SECRET_KEY", "flood-prediction-secret-key-change-in-production"),
    "algorithm": "HS256",
    "access_token_expire_minutes": 120,
}

# 缓存配置
CACHE_CONFIG = {
    "l1_max_size": 100,
    "l1_ttl_seconds": 300,         # 5分钟
    "l2_ttl_seconds": 900,         # 15分钟
    "l2_key_prefix": "pred",
    "realtime_ttl_seconds": 300,   # 5分钟
}

# 角色权限映射
ROLE_PERMISSIONS = {
    "admin":      ["query", "submit_data", "batch_process", "export",
                   "create_warning", "manage_warning", "manage_users", "view_logs"],
    "commander":  ["query", "submit_data", "batch_process", "export",
                   "create_warning", "manage_warning", "view_logs"],
    "researcher": ["query", "batch_process", "export"],
    "grassroots": ["query", "submit_data"],
}

# CSV 导入配置
CSV_IMPORT_CONFIG = {
    "templates_dir": str(BASE_DIR / "data" / "import_templates"),
    "max_file_size_mb": 50,
    "supported_encodings": ["utf-8", "gbk", "gb2312", "latin-1"],
}

# 操作日志配置
LOG_CONFIG = {
    "buffer_max_size": 1000,
    "db_flush_batch_size": 50,
    "db_flush_interval_seconds": 30,
}
```

- [ ] **Step 2: Run Python to verify settings loads without error**

```bash
python -c "from src.config.settings import JWT_CONFIG, CACHE_CONFIG, ROLE_PERMISSIONS; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/config/settings.py
git commit -m "feat: add JWT, cache, role, CSV import, and log config to settings"
```

---

### Task 2: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add new dependencies**

Append to `requirements.txt` (do not remove existing lines):

```
pyjwt>=2.8.0
passlib[bcrypt]>=1.7.4
```

- [ ] **Step 2: Install dependencies**

```bash
pip install pyjwt>=2.8.0 "passlib[bcrypt]>=1.7.4"
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pyjwt and passlib dependencies"
```

---

### Task 3: Create Redis client module

**Files:**
- Create: `src/db/redis_client.py`

- [ ] **Step 1: Write the RedisClient singleton**

Create `src/db/redis_client.py`:

```python
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
```

- [ ] **Step 2: Verify module imports**

```bash
python -c "from src.db.redis_client import redis_client; print('available:', redis_client.available)"
```
Expected: prints availability status (True if Redis running, False otherwise — either is OK)

- [ ] **Step 3: Commit**

```bash
git add src/db/redis_client.py
git commit -m "feat: add Redis client singleton with graceful degradation"
```

---

### Task 4: Add User and OperationLog models to models.py

**Files:**
- Modify: `src/db/models.py`

- [ ] **Step 1: Append User and OperationLog models**

Append the following to the end of `src/db/models.py` (do not modify existing classes):

```python

# ==================== 用户认证模型 ====================

class User(Base):
    """用户表 —— 支持四类角色"""
    __tablename__ = "user"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, comment="登录用户名")
    password_hash = Column(String(128), nullable=False, comment="bcrypt 密码哈希")
    role = Column(String(20), nullable=False, comment="角色: admin/commander/researcher/grassroots")
    display_name = Column(String(100), comment="显示名称")
    is_active = Column(SmallInteger, default=1, comment="启用: 1-是, 0-否")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        Index("idx_user_username", "username"),
        Index("idx_user_role", "role"),
    )


# ==================== 操作日志模型 ====================

class OperationLog(Base):
    """操作日志表 —— 记录所有非GET请求"""
    __tablename__ = "operation_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now, comment="请求时间")
    user_id = Column(String(50), comment="用户标识")
    role = Column(String(20), comment="用户角色")
    method = Column(String(10), nullable=False, comment="HTTP 方法")
    path = Column(String(200), nullable=False, comment="请求路径")
    status_code = Column(SmallInteger, comment="响应状态码")
    duration_ms = Column(SmallInteger, comment="处理耗时(毫秒)")
    ip_address = Column(String(45), comment="客户端IP")
    user_agent = Column(String(500), comment="User-Agent")
    request_summary = Column(String(200), comment="操作摘要")

    __table_args__ = (
        Index("idx_log_timestamp", "timestamp"),
        Index("idx_log_user_id", "user_id"),
        Index("idx_log_method_path", "method", "path"),
    )
```

- [ ] **Step 2: Fix imports if needed**

The new models use `Column`, `BigInteger`, `String`, `DateTime`, `SmallInteger`, `Index` — all already imported at the top of `models.py`. No import changes needed.

- [ ] **Step 3: Verify models import correctly**

```bash
python -c "from src.db.models import User, OperationLog; print('User table:', User.__tablename__); print('OperationLog table:', OperationLog.__tablename__)"
```
Expected: prints both table names

- [ ] **Step 4: Commit**

```bash
git add src/db/models.py
git commit -m "feat: add User and OperationLog ORM models"
```

---

### Task 5: Create JWT handler

**Files:**
- Create: `src/auth/__init__.py`
- Create: `src/auth/jwt_handler.py`

- [ ] **Step 1: Create empty __init__.py**

Create `src/auth/__init__.py` (empty file):

```bash
touch src/auth/__init__.py
```

- [ ] **Step 2: Write JWTHandler**

Create `src/auth/jwt_handler.py`:

```python
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
```

- [ ] **Step 3: Verify JWT handler works**

```bash
python -c "
from src.auth.jwt_handler import JWTHandler
token = JWTHandler.create_access_token({'sub': 'admin', 'role': 'admin'})
print('Token created:', token[:30] + '...')
payload = JWTHandler.decode_token(token)
print('Decoded sub:', payload['sub'])
print('Decoded role:', payload['role'])
"
```
Expected: prints token prefix and decoded values

- [ ] **Step 4: Commit**

```bash
git add src/auth/__init__.py src/auth/jwt_handler.py
git commit -m "feat: add JWT handler for token creation and validation"
```

---

### Task 6: Create role manager

**Files:**
- Create: `src/auth/role_manager.py`

- [ ] **Step 1: Write RoleManager**

Create `src/auth/role_manager.py`:

```python
"""角色权限管理 —— RBAC 权限矩阵"""

from typing import List
from src.config.settings import ROLE_PERMISSIONS


class RoleManager:
    """角色权限管理器"""

    PERMISSIONS = ROLE_PERMISSIONS

    # 权限动作到端点前缀的映射
    ACTION_ENDPOINT_MAP = {
        "query":            "GET",
        "submit_data":      "POST:/sensor-data",
        "batch_process":    "POST:/data/process-batch",
        "export":           "POST:/water-data/export",
        "create_warning":   "POST:/warnings",
        "manage_warning":   "POST:/warnings/",    # confirm/handle/resolve/escalate/cancel
        "manage_users":     "POST:/users",
        "view_logs":        "GET:/logs",
    }

    @classmethod
    def has_permission(cls, role: str, action: str) -> bool:
        """检查角色是否有指定权限
        Args:
            role: 角色名 (admin/commander/researcher/grassroots)
            action: 权限动作名
        Returns:
            True 如果有权限
        """
        if role not in cls.PERMISSIONS:
            return False
        return action in cls.PERMISSIONS[role]

    @classmethod
    def get_role_permissions(cls, role: str) -> List[str]:
        """获取角色的所有权限列表"""
        return cls.PERMISSIONS.get(role, [])

    @classmethod
    def get_all_roles(cls) -> List[str]:
        """获取所有可用角色"""
        return list(cls.PERMISSIONS.keys())
```

- [ ] **Step 2: Verify role manager**

```bash
python -c "
from src.auth.role_manager import RoleManager
print('Admin can manage_users:', RoleManager.has_permission('admin', 'manage_users'))
print('Commander can manage_users:', RoleManager.has_permission('commander', 'manage_users'))
print('Grassroots permissions:', RoleManager.get_role_permissions('grassroots'))
"
```
Expected:
```
Admin can manage_users: True
Commander can manage_users: False
Grassroots permissions: ['query', 'submit_data']
```

- [ ] **Step 3: Commit**

```bash
git add src/auth/role_manager.py
git commit -m "feat: add RBAC role manager with permission matrix"
```

---

### Task 7: Create auth dependencies

**Files:**
- Create: `src/auth/dependencies.py`

- [ ] **Step 1: Write FastAPI auth dependencies**

Create `src/auth/dependencies.py`:

```python
"""FastAPI 认证与授权依赖注入"""

from typing import Optional
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.auth.jwt_handler import JWTHandler
from src.auth.role_manager import RoleManager

security = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    """当前用户上下文"""
    username: str
    role: str
    is_authenticated: bool = True


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> CurrentUser:
    """从 Authorization header 解析当前用户。
    未提供 Token 时返回未认证用户（用于公开端点可选注入）。
    提供但无效/过期 Token 时抛出 401。
    """
    if credentials is None:
        return CurrentUser(username="anonymous", role="anonymous", is_authenticated=False)

    token = credentials.credentials
    payload = JWTHandler.decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=401,
            detail={"code": 401, "message": "Token 无效或已过期", "data": None},
        )

    return CurrentUser(
        username=payload.get("sub", "unknown"),
        role=payload.get("role", "anonymous"),
        is_authenticated=True,
    )


def require_auth():
    """要求用户已认证（任意角色），否则返回 401。
    用法: Depends(require_auth)
    """
    async def _require_auth(user: CurrentUser = Depends(get_current_user)):
        if not user.is_authenticated:
            raise HTTPException(
                status_code=401,
                detail={"code": 401, "message": "请先登录", "data": None},
            )
        return user
    return _require_auth


def require_role(action: str):
    """要求当前用户具有指定权限，否则返回 403。
    用法: Depends(require_role("create_warning"))

    Args:
        action: 权限动作名 (如 'submit_data', 'create_warning')
    """
    async def _require_role(user: CurrentUser = Depends(require_auth())):
        if not RoleManager.has_permission(user.role, action):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": 403,
                    "message": f"权限不足，角色 '{user.role}' 没有 '{action}' 权限",
                    "data": None,
                },
            )
        return user
    return _require_role
```

- [ ] **Step 2: Verify dependencies import**

```bash
python -c "from src.auth.dependencies import get_current_user, require_auth, require_role, CurrentUser; print('All imports OK')"
```
Expected: `All imports OK`

- [ ] **Step 3: Commit**

```bash
git add src/auth/dependencies.py
git commit -m "feat: add FastAPI auth dependencies (get_current_user, require_role)"
```

---

### Task 8: Create PredictionCache service

**Files:**
- Create: `src/prediction_model/prediction_cache.py`

- [ ] **Step 1: Write PredictionCache class**

Create `src/prediction_model/prediction_cache.py`:

```python
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
```

- [ ] **Step 2: Verify PredictionCache works**

```bash
python -c "
import numpy as np
from src.prediction_model.prediction_cache import PredictionCache

cache = PredictionCache()
features = np.random.randn(72, 7)
h = cache.compute_hash(features)

# Test miss
result = cache.get('S001', h)
print('Miss:', result)

# Test set + hit
cache.set('S001', h, {'test': 'data'})
result = cache.get('S001', h)
print('Hit:', result)

# Test stats
print('Stats:', cache.stats())

# Test invalidate
cache.invalidate_station('S001')
result = cache.get('S001', h)
print('After invalidate (L2 depends on Redis):', result)
"
```
Expected: Miss=None, Hit={'test': 'data'}, Stats shows 1 hit 1 miss, After invalidate=None

- [ ] **Step 3: Commit**

```bash
git add src/prediction_model/prediction_cache.py
git commit -m "feat: add two-level prediction cache (L1 memory + L2 Redis)"
```

---

### Task 9: Update predictor.py with cache integration and model preloading

**Files:**
- Modify: `src/prediction_model/predictor.py`

- [ ] **Step 1: Rewrite predictor.py with cache, vectorization, and model registry**

Rewrite `src/prediction_model/predictor.py`:

```python
"""预测服务模块 —— 加载模型进行预测，并生成预警信息
Week 4: 集成两级缓存、向量化预处理、模型预加载
"""

import torch
import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from src.config.settings import WARNING_THRESHOLDS, MODEL_CONFIG, MONITOR_STATIONS
from src.prediction_model.lstm_attention import LSTMAttentionModel
from src.prediction_model.prediction_cache import PredictionCache

logger = logging.getLogger(__name__)


class FloodPredictor:
    """洪水预测服务 —— 支持多站点模型预加载 + 两级缓存"""

    FEATURE_COLS = ["water_level", "flow_rate", "rainfall", "temperature", "ph", "turbidity", "dissolved_oxygen"]

    def __init__(self, model: Optional[LSTMAttentionModel] = None, models_dir: Optional[str] = None):
        self._default_model = model or LSTMAttentionModel()
        self._default_model.eval()
        self.model_registry: Dict[str, LSTMAttentionModel] = {}
        self.cache = PredictionCache()
        self._models_dir = Path(models_dir) if models_dir else Path(__file__).parent.parent.parent / "models"
        self._preload_models()

    def _preload_models(self):
        """启动时预加载所有站点模型"""
        for station in MONITOR_STATIONS:
            sid = station["id"]
            model_path = self._models_dir / f"lstm_attention_{sid}.pt"
            if model_path.exists():
                try:
                    model = LSTMAttentionModel()
                    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
                    model.eval()
                    self.model_registry[sid] = model
                    logger.info("模型加载成功: %s", model_path)
                except Exception as e:
                    logger.warning("模型加载失败 %s: %s", model_path, e)
        if not self.model_registry:
            logger.info("未找到预训练模型，使用默认模型（随机权重）")

    def _get_model(self, station_id: str) -> LSTMAttentionModel:
        """获取站点对应模型，未预加载则使用默认模型"""
        return self.model_registry.get(station_id, self._default_model)

    @torch.no_grad()
    def predict(self, input_sequence: np.ndarray, station_id: str = "default") -> np.ndarray:
        """执行预测（纯 NumPy 输入 → NumPy 输出，无缓存）"""
        model = self._get_model(station_id)
        input_tensor = torch.FloatTensor(input_sequence)
        output = model(input_tensor)
        return output.numpy()

    @torch.no_grad()
    def predict_with_attention_weights(self, input_sequence: np.ndarray, station_id: str = "default") -> dict:
        """执行预测并返回注意力权重"""
        model = self._get_model(station_id)
        input_tensor = torch.FloatTensor(input_sequence)
        result = model.predict_with_attention(input_tensor)
        return {
            "prediction": result["prediction"].numpy(),
            "attention_weights": result["attention_weights"].numpy(),
        }

    def predict_flood_risk(self, recent_data: pd.DataFrame) -> Dict:
        """预测洪水风险 —— 集成两级缓存"""
        seq_length = MODEL_CONFIG["seq_length"]
        if len(recent_data) < seq_length:
            return {"error": f"数据不足，需要至少{seq_length}条记录"}

        station_id = (
            recent_data["location_id"].iloc[0]
            if "location_id" in recent_data.columns
            else "unknown"
        )

        # 提取特征并转换为 NumPy（向量化）
        features = np.zeros((len(recent_data), len(self.FEATURE_COLS)), dtype=np.float32)
        for i, col in enumerate(self.FEATURE_COLS):
            if col in recent_data.columns:
                features[:, i] = recent_data[col].values.astype(np.float32)

        features = features[-seq_length:]  # 取最后 72 行

        # 归一化（纯 NumPy）
        mean = features.mean(axis=0, keepdims=True)
        std = features.std(axis=0, keepdims=True)
        std[std == 0] = 1.0
        features_norm = (features - mean) / std

        # 计算输入哈希，查询缓存
        input_hash = PredictionCache.compute_hash(features_norm)
        cached = self.cache.get(station_id, input_hash)
        if cached is not None:
            return cached

        # 执行推理
        input_seq = features_norm.reshape(1, seq_length, -1)
        att_result = self.predict_with_attention_weights(input_seq, station_id)
        predictions = att_result["prediction"][0]
        attention_weights = att_result["attention_weights"][0].tolist()

        # 去归一化
        predicted_levels = predictions * std[0, 0] + mean[0, 0]

        # 风险等级评估
        max_predicted_level = float(predicted_levels.max())
        risk_level = self._assess_risk_level(max_predicted_level)

        station_name = self._get_station_name(station_id)

        result = {
            "predict_time": datetime.now().isoformat(),
            "station_name": station_name,
            "location_id": station_id,
            "max_predicted_water_level": round(max_predicted_level, 2),
            "hourly_predictions": [
                {"hour": i + 1, "level": round(float(l), 2)}
                for i, l in enumerate(predicted_levels[:24])
            ],
            "risk_level": risk_level["level"],
            "risk_name": risk_level["name"],
            "confidence": risk_level["confidence"],
            "attention_weights": attention_weights,
        }

        # 写入缓存
        self.cache.set(station_id, input_hash, result)

        return result

    def _assess_risk_level(self, water_level: float) -> Dict:
        """评估风险等级"""
        if water_level >= WARNING_THRESHOLDS["level_4"]["water_level"]:
            return {"level": 4, "name": "红色预警", "confidence": 0.85}
        elif water_level >= WARNING_THRESHOLDS["level_3"]["water_level"]:
            return {"level": 3, "name": "橙色预警", "confidence": 0.88}
        elif water_level >= WARNING_THRESHOLDS["level_2"]["water_level"]:
            return {"level": 2, "name": "黄色预警", "confidence": 0.92}
        elif water_level >= WARNING_THRESHOLDS["level_1"]["water_level"]:
            return {"level": 1, "name": "蓝色预警", "confidence": 0.95}
        return {"level": 0, "name": "正常", "confidence": 0.98}

    def predict_all_stations(self, station_data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """预测所有站点的洪水风险"""
        results = []
        for station_id, data in station_data.items():
            if data is not None and len(data) >= MODEL_CONFIG["seq_length"]:
                result = self.predict_flood_risk(data)
                result["station_id"] = station_id
                result["station_name"] = self._get_station_name(station_id)
                results.append(result)
        return results

    def invalidate_station_cache(self, station_id: str):
        """外部接口：清除指定站点预测缓存"""
        self.cache.invalidate_station(station_id)

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        return self.cache.stats()

    @staticmethod
    def _get_station_name(station_id: str) -> str:
        """获取站点名称"""
        for station in MONITOR_STATIONS:
            if station["id"] == station_id:
                return station["name"]
        return station_id
```

- [ ] **Step 2: Verify predictor imports**

```bash
python -c "from src.prediction_model.predictor import FloodPredictor; p = FloodPredictor(); print('Models loaded:', len(p.model_registry)); print('Cache stats:', p.get_cache_stats())"
```
Expected: prints model count and cache stats

- [ ] **Step 3: Commit**

```bash
git add src/prediction_model/predictor.py
git commit -m "feat: integrate prediction cache, vectorized preprocessing, and model preloading"
```

---

### Task 10: Create operation log middleware

**Files:**
- Create: `src/middleware/__init__.py`
- Create: `src/middleware/operation_log.py`

- [ ] **Step 1: Create empty __init__.py**

```bash
touch src/middleware/__init__.py
```

- [ ] **Step 2: Write OperationLogMiddleware**

Create `src/middleware/operation_log.py`:

```python
"""操作日志中间件 —— 自动记录所有非GET请求"""

import json
import time
import logging
from collections import deque
from datetime import datetime
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.auth.jwt_handler import JWTHandler
from src.config.settings import LOG_CONFIG

logger = logging.getLogger(__name__)


class OperationLogMiddleware(BaseHTTPMiddleware):
    """记录所有 POST/PUT/DELETE 请求到内存缓冲区 + 数据库"""

    # 请求路径到操作摘要的映射
    PATH_SUMMARY_MAP = {
        "/sensor-data":            "传感器数据提交",
        "/data/process-batch":     "批量数据处理",
        "/data/import-csv":        "CSV数据导入",
        "/water-data/export":      "历史数据导出",
        "/warnings":               "预警操作",
        "/auth/login":             "用户登录",
        "/users":                  "用户管理",
    }

    def __init__(self, app, db_session_factory=None):
        super().__init__(app)
        self._buffer: deque = deque(maxlen=LOG_CONFIG["buffer_max_size"])
        self._db_session_factory = db_session_factory
        self._batch_size = LOG_CONFIG["db_flush_batch_size"]
        self._flush_interval = LOG_CONFIG["db_flush_interval_seconds"]
        self._last_flush = time.time()

    @staticmethod
    def _extract_user(authorization: Optional[str]) -> tuple:
        """从 Authorization header 提取用户信息"""
        token = JWTHandler.get_token_from_header(authorization)
        if token:
            payload = JWTHandler.decode_token(token)
            if payload:
                return payload.get("sub", "anonymous"), payload.get("role", "unknown")
        return "anonymous", None

    @staticmethod
    def _summarize(path: str) -> str:
        """根据请求路径生成操作摘要"""
        for prefix, summary in OperationLogMiddleware.PATH_SUMMARY_MAP.items():
            if prefix in path:
                return summary
        return path.split("/")[-1] if path else "未知操作"

    async def dispatch(self, request: Request, call_next):
        # 只记录写操作
        if request.method.upper() not in ("POST", "PUT", "DELETE", "PATCH"):
            return await call_next(request)

        start_time = time.time()
        user_id, role = self._extract_user(request.headers.get("authorization"))

        # 执行实际请求
        response: Response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)

        # 构建日志条目
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "role": role,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "ip_address": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "")[:500],
            "request_summary": self._summarize(request.url.path),
        }

        # 写入内存缓冲区
        self._buffer.append(log_entry)

        return response

    def get_recent_logs(self, limit: int = 100) -> list:
        """获取最近的操作日志（从内存缓冲区）"""
        items = list(self._buffer)
        return items[-limit:]

    def get_all_buffered_logs(self) -> list:
        """获取所有缓冲区日志"""
        return list(self._buffer)
```

- [ ] **Step 3: Verify middleware imports**

```bash
python -c "from src.middleware.operation_log import OperationLogMiddleware; print('Middleware imported OK')"
```
Expected: `Middleware imported OK`

- [ ] **Step 4: Commit**

```bash
git add src/middleware/__init__.py src/middleware/operation_log.py
git commit -m "feat: add operation log middleware for write request auditing"
```

---

### Task 11: Create CSV importer

**Files:**
- Create: `src/data_collection/csv_importer.py`

- [ ] **Step 1: Write CsvImporter class**

Create `src/data_collection/csv_importer.py`:

```python
"""CSV 水文数据导入器 —— 灵活列映射 + 自动嗅探 + 清洗入库"""

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from src.data_processing.data_validator import DataValidator
from src.data_processing.batch_processor import BatchDataProcessor
from src.config.settings import CSV_IMPORT_CONFIG, MONITOR_STATIONS

logger = logging.getLogger(__name__)

# 系统标准字段
STANDARD_FIELDS = [
    "station_id", "timestamp", "water_level", "flow_rate",
    "rainfall", "temperature", "ph", "turbidity", "dissolved_oxygen",
]
REQUIRED_FIELDS = ["station_id", "timestamp", "water_level"]


class CsvImporter:
    """CSV 数据导入器 —— 支持灵活列映射、自动嗅探和单位转换"""

    UNIT_CONVERSIONS = {
        "cm_to_m": lambda x: x / 100.0,
        "mm_to_m": lambda x: x / 1000.0,
        "none": lambda x: x,
    }

    def __init__(self):
        self.validator = DataValidator()
        self.processor = BatchDataProcessor()
        self.import_history: List[dict] = []
        self._templates_dir = Path(CSV_IMPORT_CONFIG["templates_dir"])
        self._templates_dir.mkdir(parents=True, exist_ok=True)

    def sniff(self, filepath: str) -> dict:
        """自动检测 CSV 文件格式
        Returns:
            {"encoding": str, "delimiter": str, "has_header": bool, "headers": [...], "row_count": int}
        """
        result = {
            "encoding": "utf-8",
            "delimiter": ",",
            "has_header": True,
            "headers": [],
            "row_count": 0,
            "sample_rows": [],
        }

        # 尝试检测编码
        for enc in CSV_IMPORT_CONFIG["supported_encodings"]:
            try:
                with open(filepath, "r", encoding=enc) as f:
                    content = f.read(5000)
                result["encoding"] = enc
                break
            except (UnicodeDecodeError, LookupError):
                continue

        # 检测分隔符
        try:
            with open(filepath, "r", encoding=result["encoding"]) as f:
                sample = f.read(8192)
            sniffer = csv.Sniffer()
            result["delimiter"] = sniffer.sniff(sample).delimiter
            result["has_header"] = sniffer.has_header(sample)
        except Exception:
            pass  # 使用默认逗号分隔符

        # 读取表头和行数
        try:
            df = pd.read_csv(
                filepath,
                encoding=result["encoding"],
                sep=result["delimiter"],
                nrows=5,
            )
            result["headers"] = list(df.columns)
            result["sample_rows"] = df.head(3).to_dict("records")

            # 计数总行数
            with open(filepath, "r", encoding=result["encoding"]) as f:
                result["row_count"] = sum(1 for _ in f) - (1 if result["has_header"] else 0)
        except Exception as e:
            logger.error("CSV 读取失败: %s", e)
            result["error"] = str(e)

        return result

    def load_with_mapping(self, filepath: str, mapping: dict) -> Tuple[List[dict], dict]:
        """根据列映射加载 CSV 并转换为标准格式
        Args:
            filepath: CSV 文件路径
            mapping: 映射配置字典，包含 column_mapping, datetime_format, skip_rows 等
        Returns:
            (records, summary): 标准格式记录列表和摘要信息
        """
        column_mapping = mapping.get("column_mapping", {})
        datetime_format = mapping.get("datetime_format", None)
        skip_rows = mapping.get("skip_rows", 0)
        encoding = mapping.get("encoding", "utf-8")
        delimiter = mapping.get("delimiter", ",")
        unit_conversions = mapping.get("unit_conversions", {})
        station_id_mapping = mapping.get("station_id_mapping", {})

        # 反转映射：CSV列名 → 标准字段名
        reverse_mapping = {v: k for k, v in column_mapping.items()}

        # 检查必选字段
        missing_required = [
            f for f in REQUIRED_FIELDS
            if f not in column_mapping
        ]
        if missing_required:
            raise ValueError(f"映射配置缺少必选字段: {missing_required}")

        # 读取 CSV
        df = pd.read_csv(
            filepath,
            encoding=encoding,
            sep=delimiter,
            skiprows=skip_rows,
        )

        summary = {
            "file": filepath,
            "total_rows": len(df),
            "mapped_columns": list(column_mapping.keys()),
            "warnings": [],
        }

        # 重命名列
        df.rename(columns=reverse_mapping, inplace=True)

        # 只保留标准字段
        keep_cols = [c for c in STANDARD_FIELDS if c in df.columns]
        df = df[keep_cols]

        # 站点ID映射
        if station_id_mapping:
            if "station_id" in df.columns:
                df["station_id"] = df["station_id"].map(
                    lambda x: station_id_mapping.get(str(x), x)
                )
                mapped_count = df["station_id"].isin(station_id_mapping.values()).sum()
                summary["station_id_mapped"] = int(mapped_count)

        # 时间戳解析
        if "timestamp" in df.columns:
            try:
                if datetime_format:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], format=datetime_format)
                else:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
            except Exception as e:
                summary["warnings"].append(f"时间戳解析部分失败: {e}")
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

            invalid_ts = df["timestamp"].isna().sum()
            if invalid_ts > 0:
                summary["warnings"].append(f"{invalid_ts} 行时间戳无效，已跳过")
            df = df.dropna(subset=["timestamp"])

        # 单位转换
        for field, conv_name in unit_conversions.items():
            if field in df.columns and conv_name in self.UNIT_CONVERSIONS:
                conv_func = self.UNIT_CONVERSIONS[conv_name]
                df[field] = pd.to_numeric(df[field], errors="coerce")
                df[field] = df[field].apply(conv_func)
                summary["warnings"].append(f"已对 '{field}' 执行单位转换: {conv_name}")

        summary["valid_rows"] = len(df)

        return df.to_dict("records"), summary

    def import_and_clean(self, filepath: str, mapping: dict) -> dict:
        """完整导入流程：加载 → 清洗 → 返回结果
        Args:
            filepath: CSV 文件路径
            mapping: 映射配置
        Returns:
            {"status": "success"/"error", "summary": {...}, "cleaned_count": int, ...}
        """
        # Step 1: 加载并映射
        try:
            records, load_summary = self.load_with_mapping(filepath, mapping)
        except Exception as e:
            return {
                "status": "error",
                "message": f"CSV加载失败: {e}",
                "summary": {},
            }

        if len(records) == 0:
            return {
                "status": "error",
                "message": "映射后无有效数据",
                "summary": load_summary,
            }

        # Step 2: 清洗（复用现有管道）
        try:
            clean_result = self.processor.process_pipeline(records)
        except Exception as e:
            logger.warning("自动清洗失败，返回原始数据: %s", e)
            clean_result = {"status": "partial", "message": str(e)}

        # Step 3: 记录导入历史
        history_entry = {
            "time": datetime.now().isoformat(),
            "file": filepath,
            "template": mapping.get("template_name", "unknown"),
            "total_rows": load_summary.get("total_rows", 0),
            "valid_rows": load_summary.get("valid_rows", 0),
            "status": clean_result.get("status", "unknown"),
        }
        self.import_history.append(history_entry)

        return {
            "status": clean_result.get("status", "success"),
            "load_summary": load_summary,
            "clean_summary": clean_result.get("clean_summary", {}),
            "feature_count": clean_result.get("feature_count", 0),
            "dataset_samples": clean_result.get("dataset_samples", 0),
        }

    # ---- 映射模板管理 ----

    def save_template(self, template: dict) -> str:
        """保存映射模板到文件"""
        name = template.get("template_name", "untitled")
        filename = f"{name}.json"
        filepath = self._templates_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        return str(filepath)

    def list_templates(self) -> List[dict]:
        """列出所有已保存的映射模板"""
        templates = []
        if self._templates_dir.exists():
            for f in self._templates_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        templates.append(json.load(fp))
                except Exception:
                    continue
        return templates

    def get_import_history(self, limit: int = 50) -> List[dict]:
        """获取导入历史"""
        return self.import_history[-limit:]
```

- [ ] **Step 2: Verify CSV importer imports**

```bash
python -c "from src.data_collection.csv_importer import CsvImporter; importer = CsvImporter(); print('Templates:', importer.list_templates())"
```
Expected: `Templates: []`

- [ ] **Step 3: Commit**

```bash
git add src/data_collection/csv_importer.py
git commit -m "feat: add CSV importer with flexible column mapping and auto-sniffing"
```

---

### Task 12: Update schemas.py with new Pydantic models

**Files:**
- Modify: `src/web/schemas.py`

- [ ] **Step 1: Append new Pydantic models**

Append to the end of `src/web/schemas.py` (do not modify existing classes):

```python

# ==================== 认证相关模型 ====================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(..., min_length=1, max_length=100, description="密码")


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(default=7200, description="过期时间(秒)")
    user: dict = Field(default_factory=dict, description="用户信息")


class UserCreate(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=2, max_length=50, description="登录用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    role: str = Field(..., description="角色: admin/commander/researcher/grassroots")
    display_name: Optional[str] = Field(default=None, max_length=100, description="显示名称")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        valid_roles = {"admin", "commander", "researcher", "grassroots"}
        if v not in valid_roles:
            raise ValueError(f"无效角色: {v}，有效值为: {valid_roles}")
        return v


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    role: str
    display_name: Optional[str] = None
    is_active: int
    created_at: str


class PasswordReset(BaseModel):
    """密码重置请求"""
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


# ==================== CSV 导入相关模型 ====================

class CsvMappingConfig(BaseModel):
    """CSV 列映射配置"""
    template_name: str = Field(..., min_length=1, description="模板名称")
    description: Optional[str] = Field(default="", description="模板描述")
    column_mapping: dict = Field(..., description="列名映射: 标准字段 → CSV列名")
    datetime_format: Optional[str] = Field(default=None, description="时间格式，如 %Y-%m-%d %H:%M:%S")
    skip_rows: int = Field(default=0, ge=0, description="跳过的行数")
    encoding: str = Field(default="utf-8", description="文件编码")
    delimiter: str = Field(default=",", description="分隔符")
    unit_conversions: Optional[dict] = Field(default_factory=dict, description="单位转换")
    station_id_mapping: Optional[dict] = Field(default_factory=dict, description="站点ID映射")


class CsvImportRequest(BaseModel):
    """CSV 导入请求"""
    filepath: str = Field(..., min_length=1, description="CSV 文件路径")
    mapping: CsvMappingConfig = Field(..., description="列映射配置")


class ImportResult(BaseModel):
    """导入结果"""
    status: str = Field(..., description="状态: success/error")
    load_summary: dict = Field(default_factory=dict)
    clean_summary: dict = Field(default_factory=dict)
    feature_count: int = Field(default=0)
    dataset_samples: int = Field(default=0)
    message: Optional[str] = Field(default=None)


class SniffResult(BaseModel):
    """CSV 嗅探结果"""
    encoding: str
    delimiter: str
    has_header: bool
    headers: list
    row_count: int
    sample_rows: list


# ==================== 操作日志查询模型 ====================

class LogQueryParams(BaseModel):
    """日志查询参数"""
    user_id: Optional[str] = Field(default=None, description="用户ID过滤")
    method: Optional[str] = Field(default=None, description="HTTP方法过滤")
    path: Optional[str] = Field(default=None, description="路径过滤")
    start_time: Optional[str] = Field(default=None, description="起始时间 ISO 8601")
    end_time: Optional[str] = Field(default=None, description="结束时间 ISO 8601")
    limit: int = Field(default=100, ge=1, le=1000, description="返回条数")
    offset: int = Field(default=0, ge=0, description="偏移量")
```

- [ ] **Step 2: Verify schemas import**

```bash
python -c "from src.web.schemas import LoginRequest, UserCreate, CsvMappingConfig, CsvImportRequest; print('All schemas OK')"
```
Expected: `All schemas OK`

- [ ] **Step 3: Commit**

```bash
git add src/web/schemas.py
git commit -m "feat: add Pydantic schemas for auth, CSV import, and log query"
```

---

### Task 13: Add auth and user management routes

**Files:**
- Modify: `src/web/routes.py`

- [ ] **Step 1: Add new imports at the top of routes.py**

Add these lines to the existing import block in `src/web/routes.py` (do not remove existing imports):

```python
from src.auth.dependencies import get_current_user, require_auth, require_role, CurrentUser
from src.auth.jwt_handler import JWTHandler
from src.auth.role_manager import RoleManager
from src.config.settings import JWT_CONFIG
from src.web.schemas import (
    # ... existing imports remain ...
    LoginRequest, UserCreate, PasswordReset,
    CsvMappingConfig, CsvImportRequest,
)
```

- [ ] **Step 2: Add auth routes before the existing routes**

Insert these routes after the `router = APIRouter(prefix="/api/v1")` line and service instances, before the existing `# ==================== 统一响应工具 ====================` comment:

```python
# 新增服务实例
from src.data_collection.csv_importer import CsvImporter
csv_importer = CsvImporter()

# ==================== 认证相关 ====================

@router.post("/auth/login")
async def login(request: LoginRequest):
    """用户登录"""
    # 使用 SQLite 数据库查询（需要 DB session，这里先用内存 fallback）
    # 实际使用时从数据库加载用户
    from src.db.models import User
    from src.db.init_db import get_session
    import bcrypt

    session = get_session()
    try:
        user = session.query(User).filter(
            User.username == request.username,
            User.is_active == 1,
        ).first()

        if not user:
            raise HTTPException(
                status_code=401,
                detail={"code": 401, "message": "用户名或密码错误", "data": None},
            )

        # 验证密码
        try:
            from passlib.hash import bcrypt as passlib_bcrypt
            password_valid = passlib_bcrypt.verify(request.password, user.password_hash)
        except Exception:
            # fallback: 直接比较（开发环境）
            import hashlib
            password_valid = (user.password_hash == hashlib.sha256(request.password.encode()).hexdigest())

        if not password_valid:
            raise HTTPException(
                status_code=401,
                detail={"code": 401, "message": "用户名或密码错误", "data": None},
            )

        token = JWTHandler.create_access_token({
            "sub": user.username,
            "role": user.role,
        })

        return success_response({
            "access_token": token,
            "token_type": "bearer",
            "expires_in": JWT_CONFIG["access_token_expire_minutes"] * 60,
            "user": {
                "username": user.username,
                "role": user.role,
                "display_name": user.display_name,
            },
        }, message="登录成功")
    finally:
        session.close()


@router.get("/auth/me")
async def get_current_user_info(user: CurrentUser = Depends(require_auth())):
    """获取当前登录用户信息"""
    return success_response({
        "username": user.username,
        "role": user.role,
        "is_authenticated": user.is_authenticated,
    })
```

- [ ] **Step 3: Add user management routes**

Insert after the auth routes:

```python
# ==================== 用户管理 ====================

@router.post("/users")
async def create_user(
    request: UserCreate,
    current_user: CurrentUser = Depends(require_role("manage_users")),
):
    """创建新用户（管理员）"""
    from src.db.models import User
    from src.db.init_db import get_session
    from passlib.hash import bcrypt

    session = get_session()
    try:
        existing = session.query(User).filter(User.username == request.username).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail={"code": 400, "message": f"用户名 '{request.username}' 已存在", "data": None},
            )

        new_user = User(
            username=request.username,
            password_hash=bcrypt.hash(request.password),
            role=request.role,
            display_name=request.display_name or request.username,
            is_active=1,
        )
        session.add(new_user)
        session.commit()

        return success_response({
            "id": new_user.id,
            "username": new_user.username,
            "role": new_user.role,
            "display_name": new_user.display_name,
        }, message="用户创建成功")
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail={"code": 500, "message": f"创建失败: {e}", "data": None},
        )
    finally:
        session.close()


@router.get("/users")
async def list_users(
    current_user: CurrentUser = Depends(require_role("manage_users")),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """用户列表（管理员）"""
    from src.db.models import User
    from src.db.init_db import get_session

    session = get_session()
    try:
        total = session.query(User).count()
        users = session.query(User).order_by(User.id).offset(offset).limit(limit).all()
        return success_response({
            "total": total,
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "role": u.role,
                    "display_name": u.display_name,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ],
        })
    finally:
        session.close()


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: CurrentUser = Depends(require_role("manage_users")),
):
    """删除用户（软删除，管理员）"""
    from src.db.models import User
    from src.db.init_db import get_session

    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail={"code": 404, "message": "用户不存在", "data": None})

        user.is_active = 0
        session.commit()
        return success_response(None, message=f"用户 '{user.username}' 已删除")
    finally:
        session.close()


@router.put("/users/{user_id}/password")
async def reset_password(
    user_id: int,
    request: PasswordReset,
    current_user: CurrentUser = Depends(require_role("manage_users")),
):
    """重置密码（管理员）"""
    from src.db.models import User
    from src.db.init_db import get_session
    from passlib.hash import bcrypt

    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail={"code": 404, "message": "用户不存在", "data": None})

        user.password_hash = bcrypt.hash(request.new_password)
        session.commit()
        return success_response(None, message=f"用户 '{user.username}' 密码已重置")
    finally:
        session.close()
```

- [ ] **Step 4: Verify routes file still imports correctly**

```bash
python -c "from src.web.routes import router; print('Routes OK, endpoints:', len(router.routes))"
```
Expected: prints number of routes (should increase from current 21)

- [ ] **Step 5: Commit**

```bash
git add src/web/routes.py
git commit -m "feat: add auth login, user CRUD routes with RBAC protection"
```

---

### Task 14: Add auth protection to existing write endpoints + cache invalidation

**Files:**
- Modify: `src/web/routes.py`

- [ ] **Step 1: Protect POST /sensor-data with auth and add cache invalidation**

Find the `submit_sensor_data` function in `routes.py` and update its signature and add cache invalidation.
Replace the function signature:

```python
@router.post("/sensor-data")
async def submit_sensor_data(data: SensorDataSubmit):
```

With:

```python
@router.post("/sensor-data")
async def submit_sensor_data(
    data: SensorDataSubmit,
    current_user: CurrentUser = Depends(require_role("submit_data")),
):
```

And add after the `return success_response(...)` line, before the return:

```python
    # 清除对应站点的预测缓存
    for reading in data.readings:
        predictor.invalidate_station_cache(reading.station_id)
```

- [ ] **Step 2: Protect POST /data/process-batch**

Replace:

```python
@router.post("/data/process-batch")
async def process_batch_data(filepath: str = Query(..., description="数据文件路径")):
```

With:

```python
@router.post("/data/process-batch")
async def process_batch_data(
    filepath: str = Query(..., description="数据文件路径"),
    current_user: CurrentUser = Depends(require_role("batch_process")),
):
```

- [ ] **Step 3: Protect POST /water-data/export**

Replace:

```python
@router.post("/water-data/export")
async def export_historical_data(query: HistoricalDataExport):
```

With:

```python
@router.post("/water-data/export")
async def export_historical_data(
    query: HistoricalDataExport,
    current_user: CurrentUser = Depends(require_role("export")),
):
```

- [ ] **Step 4: Protect POST /warnings**

Replace:

```python
@router.post("/warnings")
async def create_warning(warning_data: WarningCreate):
```

With:

```python
@router.post("/warnings")
async def create_warning(
    warning_data: WarningCreate,
    current_user: CurrentUser = Depends(require_role("create_warning")),
):
```

- [ ] **Step 5: Protect all warning state machine endpoints**

Replace the 5 warning state machine function signatures:

```python
# confirm
async def confirm_warning(
    warning_id: str,
    confirmed_by: str = Query("system", description="确认人"),
):
# → add: current_user: CurrentUser = Depends(require_role("manage_warning")),

# handle
async def handle_warning(
    warning_id: str,
    handled_by: str = Query("system", description="处理人"),
):
# → add: current_user: CurrentUser = Depends(require_role("manage_warning")),

# resolve
async def resolve_warning(
    warning_id: str,
    resolved_by: str = Query("system", description="解除人"),
):
# → add: current_user: CurrentUser = Depends(require_role("manage_warning")),

# escalate
async def escalate_warning(warning_id: str):
# → add: current_user: CurrentUser = Depends(require_role("manage_warning")),

# cancel
async def cancel_warning(warning_id: str):
# → add: current_user: CurrentUser = Depends(require_role("manage_warning")),
```

- [ ] **Step 6: Verify routes compile**

```bash
python -c "from src.web.routes import router; print('Protected routes OK')"
```
Expected: `Protected routes OK`

- [ ] **Step 7: Commit**

```bash
git add src/web/routes.py
git commit -m "feat: add RBAC protection to all write endpoints with cache invalidation"
```

---

### Task 15: Add CSV import and log query routes

**Files:**
- Modify: `src/web/routes.py`

- [ ] **Step 1: Add CSV import routes**

Append the following routes before the last line of `routes.py`:

```python
# ==================== CSV 数据导入 ====================

@router.post("/data/import-csv")
async def import_csv_data(
    request: CsvImportRequest,
    current_user: CurrentUser = Depends(require_role("batch_process")),
):
    """导入 CSV 水文数据（管理员/指挥/科研）"""
    filepath = request.filepath
    if not Path(filepath).exists():
        raise HTTPException(status_code=404, detail={"code": 404, "message": f"文件不存在: {filepath}", "data": None})

    mapping = request.mapping.model_dump()
    result = csv_importer.import_and_clean(filepath, mapping)

    if result["status"] == "error":
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "message": result.get("message", "导入失败"), "data": result},
        )

    return success_response(result, message="导入完成")


@router.get("/data/import-templates")
async def get_import_templates(
    current_user: CurrentUser = Depends(require_auth()),
):
    """获取 CSV 映射模板列表（需登录）"""
    templates = csv_importer.list_templates()
    return success_response(templates)


@router.post("/data/import-templates")
async def save_import_template(
    template: CsvMappingConfig,
    current_user: CurrentUser = Depends(require_role("batch_process")),
):
    """保存 CSV 映射模板（管理员/指挥/科研）"""
    filepath = csv_importer.save_template(template.model_dump())
    return success_response({"filepath": filepath}, message="模板保存成功")


@router.get("/data/import-history")
async def get_import_history(
    current_user: CurrentUser = Depends(require_role("batch_process")),
    limit: int = Query(50, ge=1, le=200),
):
    """获取导入历史（管理员/指挥/科研）"""
    history = csv_importer.get_import_history(limit)
    return success_response(history)


@router.get("/data/csv-sniff")
async def sniff_csv(
    filepath: str = Query(..., description="CSV 文件路径"),
    current_user: CurrentUser = Depends(require_role("batch_process")),
):
    """自动检测 CSV 格式（管理员/指挥/科研）"""
    if not Path(filepath).exists():
        raise HTTPException(status_code=404, detail={"code": 404, "message": f"文件不存在: {filepath}", "data": None})

    result = csv_importer.sniff(filepath)
    return success_response(result)


# ==================== 操作日志查询 ====================

@router.get("/logs")
async def get_operation_logs(
    user_id: Optional[str] = Query(None, description="用户ID过滤"),
    method: Optional[str] = Query(None, description="HTTP方法过滤"),
    path: Optional[str] = Query(None, description="路径过滤"),
    limit: int = Query(100, ge=1, le=500, description="返回条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: CurrentUser = Depends(require_role("view_logs")),
):
    """查询操作日志（管理员/指挥）"""
    from src.middleware.operation_log import OperationLogMiddleware

    # 从中间件缓冲区获取日志（需要在 app.py 中保存引用）
    # 暂时从 request.app 获取
    logs = []
    if hasattr(request.app, "state") and hasattr(request.app.state, "log_middleware"):
        logs = request.app.state.log_middleware.get_all_buffered_logs()
    else:
        # Fallback: 直接导入中间件的单例
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("无法获取操作日志中间件引用")
        return success_response({"total": 0, "logs": []})

    # 过滤
    if user_id:
        logs = [l for l in logs if l.get("user_id") == user_id]
    if method:
        logs = [l for l in logs if l.get("method", "").upper() == method.upper()]
    if path:
        logs = [l for l in logs if path in l.get("path", "")]

    total = len(logs)
    # 倒序（最近的在前面）
    logs = sorted(logs, key=lambda x: str(x.get("timestamp", "")), reverse=True)
    paged = logs[offset: offset + limit]

    # 序列化
    serialized = []
    for log in paged:
        entry = dict(log)
        if hasattr(entry.get("timestamp"), "isoformat"):
            entry["timestamp"] = entry["timestamp"].isoformat()
        serialized.append(entry)

    return success_response({"total": total, "logs": serialized})
```

- [ ] **Step 2: Verify routes compile**

```bash
python -c "from src.web.routes import router; print('All routes OK')"
```
Expected: `All routes OK`

- [ ] **Step 3: Commit**

```bash
git add src/web/routes.py
git commit -m "feat: add CSV import and operation log query routes"
```

---

### Task 16: Update app.py to register middleware and expose log middleware reference

**Files:**
- Modify: `src/web/app.py`

- [ ] **Step 1: Update app.py**

Edit `src/web/app.py` to add middleware registration. Add after the CORS middleware and before `app.include_router(router)`:

```python
# 操作日志中间件
from src.middleware.operation_log import OperationLogMiddleware

log_middleware = OperationLogMiddleware(app)
app.add_middleware(OperationLogMiddleware)

# 将中间件引用保存到 app.state 供日志查询端点使用
app.state.log_middleware = log_middleware
```

*Note: Since OperationLogMiddleware is already instantiated in `add_middleware`, we need to pass it correctly. Update the full app.py:*

Rewrite `src/web/app.py`:

```python
"""Web应用入口 —— FastAPI 服务

启动: uvicorn src.web.app:app --reload
文档: http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.web.routes import router
from src.config.settings import API_CONFIG
from src.middleware.operation_log import OperationLogMiddleware

app = FastAPI(
    title="基于LSTM-Attention的洪水预测与预警系统",
    description="智慧水利应用课程作业 —— 第3组 | Week 4 增强版",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 操作日志中间件（在 CORS 之后，Auth 通过 Depends 实现）
log_middleware = OperationLogMiddleware(app)
# 保存引用供日志查询使用
app.state.log_middleware = log_middleware

app.include_router(router)


@app.get("/")
async def root():
    """根路径，返回API概述"""
    return {
        "name": "基于LSTM-Attention的洪水预测与预警系统",
        "version": "4.0.0",
        "group": "第3组",
        "week": "Week 4",
        "features": {
            "auth": "JWT 认证 + 四角色权限",
            "cache": "两级预测缓存 (L1内存 + L2 Redis)",
            "import": "CSV 灵活导入 + 自动清洗",
            "logging": "操作日志中间件",
        },
        "endpoints": {
            "认证": {
                "POST /api/v1/auth/login": "用户登录",
                "GET /api/v1/auth/me": "当前用户信息",
            },
            "用户管理": {
                "POST /api/v1/users": "创建用户 (管理员)",
                "GET /api/v1/users": "用户列表 (管理员)",
                "DELETE /api/v1/users/{id}": "删除用户 (管理员)",
                "PUT /api/v1/users/{id}/password": "重置密码 (管理员)",
            },
            "监测站点": {
                "GET /api/v1/stations": "获取站点列表",
            },
            "实时数据": {
                "GET /api/v1/water-data/realtime": "获取实时水文数据",
                "POST /api/v1/sensor-data": "提交传感器数据 (需认证)",
            },
            "历史数据": {
                "GET /api/v1/water-data/history": "查询历史数据",
                "POST /api/v1/water-data/export": "导出历史数据 (需认证)",
            },
            "数据导入": {
                "POST /api/v1/data/import-csv": "导入CSV数据 (需认证)",
                "GET /api/v1/data/csv-sniff": "检测CSV格式 (需认证)",
                "GET /api/v1/data/import-templates": "映射模板列表 (需认证)",
                "POST /api/v1/data/import-templates": "保存映射模板 (需认证)",
                "GET /api/v1/data/import-history": "导入历史 (需认证)",
            },
            "预测": {
                "GET /api/v1/prediction/flood-risk": "洪水风险预测",
                "GET /api/v1/prediction/all-stations": "所有站点预测",
                "GET /api/v1/prediction/attention-heatmap": "注意力热力图",
            },
            "预警管理": {
                "POST /api/v1/warnings": "创建预警 (需认证)",
                "GET /api/v1/warnings/active": "生效预警列表",
                "GET /api/v1/warning/list": "预警列表",
                "POST /api/v1/warnings/{id}/confirm": "确认预警 (需认证)",
                "POST /api/v1/warnings/{id}/handle": "处理预警 (需认证)",
                "POST /api/v1/warnings/{id}/resolve": "解除预警 (需认证)",
                "POST /api/v1/warnings/{id}/escalate": "升级预警 (需认证)",
                "POST /api/v1/warnings/{id}/cancel": "取消预警 (需认证)",
                "GET /api/v1/warnings/{id}/state": "预警状态查询",
            },
            "操作日志": {
                "GET /api/v1/logs": "操作日志查询 (管理员/指挥)",
            },
            "系统": {
                "GET /health": "健康检查",
                "GET /api/v1/collection/stats": "采集统计",
                "GET /api/v1/data-stats": "数据统计",
                "POST /api/v1/data/process-batch": "批量处理 (需认证)",
            },
        },
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    from datetime import datetime
    from src.db.redis_client import redis_client
    return {
        "status": "healthy",
        "version": "4.0.0",
        "timestamp": datetime.now().isoformat(),
        "redis": "connected" if redis_client.health_check() else "degraded",
    }


def start():
    """启动服务"""
    import uvicorn
    uvicorn.run(
        "src.web.app:app",
        host=API_CONFIG["host"],
        port=API_CONFIG["port"],
        reload=API_CONFIG["debug"],
    )


if __name__ == "__main__":
    start()
```

- [ ] **Step 2: Verify app loads**

```bash
python -c "from src.web.app import app; print('App OK, title:', app.title)"
```
Expected: `App OK, title: 基于LSTM-Attention的洪水预测与预警系统`

- [ ] **Step 3: Commit**

```bash
git add src/web/app.py
git commit -m "feat: register operation log middleware and update API overview for Week 4"
```

---

### Task 17: Create admin initialization script

**Files:**
- Create: `scripts/create_admin.py`

- [ ] **Step 1: Write create_admin.py**

Create `scripts/create_admin.py`:

```python
"""初始化管理员账户脚本

用法:
    python scripts/create_admin.py
    ADMIN_USERNAME=myadmin ADMIN_PASSWORD=mypass python scripts/create_admin.py
"""

import os
import sys

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.hash import bcrypt
from src.db.models import User, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_URL = os.getenv("DATABASE_URL", "sqlite:///flood_prediction.db")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def create_admin():
    engine = create_engine(DB_URL, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        existing = session.query(User).filter(User.username == ADMIN_USERNAME).first()
        if existing:
            print(f"管理员 '{ADMIN_USERNAME}' 已存在，跳过创建")
            return

        admin = User(
            username=ADMIN_USERNAME,
            password_hash=bcrypt.hash(ADMIN_PASSWORD),
            role="admin",
            display_name="系统管理员",
            is_active=1,
        )
        session.add(admin)

        # 同时创建其他角色的默认用户
        defaults = [
            ("commander", "指挥员", "commander123"),
            ("researcher", "科研人员", "researcher123"),
            ("grassroots", "基层人员", "grassroots123"),
        ]
        for username, display_name, password in defaults:
            if not session.query(User).filter(User.username == username).first():
                session.add(User(
                    username=username,
                    password_hash=bcrypt.hash(password),
                    role=username,
                    display_name=display_name,
                    is_active=1,
                ))

        session.commit()
        print(f"管理员 '{ADMIN_USERNAME}' 创建成功")
        print(f"默认用户已创建: commander, researcher, grassroots")
        print("默认密码: commander123 / researcher123 / grassroots123")
    except Exception as e:
        session.rollback()
        print(f"创建失败: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    print(f"数据库: {DB_URL}")
    create_admin()
    print("完成")
```

- [ ] **Step 2: Run the script**

```bash
python scripts/create_admin.py
```
Expected: `管理员 'admin' 创建成功` (or `已存在` if run twice)

- [ ] **Step 3: Commit**

```bash
git add scripts/create_admin.py
git commit -m "feat: add admin user initialization script with default accounts"
```

---

### Task 18: Update init_db.py — add get_session() helper

**Files:**
- Modify: `src/db/init_db.py`

The current `init_db.py` has `create_dev_engine()` and `get_session_factory()` but no simple `get_session()` singleton. The routes in Tasks 13-15 call `from src.db.init_db import get_session`, so we need to add it.

- [ ] **Step 1: Append get_session() to init_db.py**

Append the following to the end of `src/db/init_db.py` (do not modify existing code):

```python

# ==================== 便捷会话管理 ====================

import os

_dev_session_factory = None

def get_session():
    """获取数据库会话（开发环境使用 SQLite 单例）"""
    global _dev_session_factory
    if _dev_session_factory is None:
        db_url = os.getenv("DATABASE_URL", "sqlite:///flood_prediction.db")
        engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(engine)  # 确保所有表（含 User, OperationLog）已创建
        _dev_session_factory = sessionmaker(bind=engine)
    return _dev_session_factory()
```

- [ ] **Step 2: Verify get_session() works and creates all tables**

```bash
python -c "
from src.db.init_db import get_session
from src.db.models import User, OperationLog
s = get_session()
from sqlalchemy import inspect
inspector = inspect(s.bind)
tables = inspector.get_table_names()
print('Tables:', sorted(tables))
assert 'user' in tables, 'User table missing!'
assert 'operation_log' in tables, 'OperationLog table missing!'
print('All tables present')
s.close()
"
```
Expected: prints sorted table names including `user` and `operation_log`

- [ ] **Step 3: Commit**

```bash
git add src/db/init_db.py
git commit -m "feat: add get_session() helper with auto table creation"
```

---

### Task 19: Write tests for JWT handler and role manager

**Files:**
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write auth tests**

Create `tests/test_auth.py`:

```python
"""认证模块单元测试"""

import pytest
import time
from src.auth.jwt_handler import JWTHandler
from src.auth.role_manager import RoleManager


class TestJWTHandler:
    """JWT 令牌处理测试"""

    def test_create_and_decode_token(self):
        """测试令牌生成和解析"""
        token = JWTHandler.create_access_token({"sub": "admin", "role": "admin"})
        assert token is not None
        assert len(token) > 20

        payload = JWTHandler.decode_token(token)
        assert payload is not None
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"
        assert "exp" in payload
        assert "jti" in payload

    def test_decode_invalid_token(self):
        """测试无效令牌"""
        payload = JWTHandler.decode_token("invalid.token.here")
        assert payload is None

    def test_decode_empty_token(self):
        """测试空字符串令牌"""
        payload = JWTHandler.decode_token("")
        assert payload is None

    def test_get_token_from_header(self):
        """测试从 Authorization header 提取 token"""
        token = JWTHandler.get_token_from_header("Bearer eyJxxx.yyy.zzz")
        assert token == "eyJxxx.yyy.zzz"

        assert JWTHandler.get_token_from_header(None) is None
        assert JWTHandler.get_token_from_header("") is None
        assert JWTHandler.get_token_from_header("Basic xxx") is None

    def test_token_uniqueness(self):
        """测试每次生成的 token 不同"""
        t1 = JWTHandler.create_access_token({"sub": "admin", "role": "admin"})
        t2 = JWTHandler.create_access_token({"sub": "admin", "role": "admin"})
        assert t1 != t2  # jti 不同


class TestRoleManager:
    """角色权限管理测试"""

    def test_admin_full_access(self):
        """管理员拥有全部权限"""
        for action in ["query", "submit_data", "batch_process", "export",
                       "create_warning", "manage_warning", "manage_users", "view_logs"]:
            assert RoleManager.has_permission("admin", action), f"Admin should have {action}"

    def test_commander_permissions(self):
        """指挥权限"""
        assert RoleManager.has_permission("commander", "create_warning")
        assert RoleManager.has_permission("commander", "manage_warning")
        assert not RoleManager.has_permission("commander", "manage_users")

    def test_researcher_permissions(self):
        """科研权限"""
        assert RoleManager.has_permission("researcher", "query")
        assert RoleManager.has_permission("researcher", "batch_process")
        assert not RoleManager.has_permission("researcher", "submit_data")
        assert not RoleManager.has_permission("researcher", "create_warning")

    def test_grassroots_permissions(self):
        """基层权限"""
        assert RoleManager.has_permission("grassroots", "query")
        assert RoleManager.has_permission("grassroots", "submit_data")
        assert not RoleManager.has_permission("grassroots", "batch_process")
        assert not RoleManager.has_permission("grassroots", "create_warning")

    def test_invalid_role(self):
        """测试无效角色"""
        assert not RoleManager.has_permission("invalid_role", "query")
        assert RoleManager.get_role_permissions("invalid_role") == []

    def test_get_all_roles(self):
        """测试获取所有角色"""
        roles = RoleManager.get_all_roles()
        assert "admin" in roles
        assert "commander" in roles
        assert "researcher" in roles
        assert "grassroots" in roles
```

- [ ] **Step 2: Run auth tests**

```bash
pytest tests/test_auth.py -v
```
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_auth.py
git commit -m "test: add JWT handler and role manager unit tests"
```

---

### Task 20: Write tests for PredictionCache

**Files:**
- Create: `tests/test_prediction_cache.py`

- [ ] **Step 1: Write cache tests**

Create `tests/test_prediction_cache.py`:

```python
"""预测缓存单元测试"""

import numpy as np
import time
from src.prediction_model.prediction_cache import PredictionCache


class TestPredictionCache:
    """两级缓存测试"""

    def setup_method(self):
        self.cache = PredictionCache()
        self.features = np.random.randn(72, 7).astype(np.float32)

    def test_compute_hash_consistency(self):
        """相同输入产生相同哈希"""
        h1 = PredictionCache.compute_hash(self.features)
        h2 = PredictionCache.compute_hash(self.features)
        assert h1 == h2

    def test_compute_hash_different(self):
        """不同输入产生不同哈希"""
        h1 = PredictionCache.compute_hash(self.features)
        f2 = np.random.randn(72, 7).astype(np.float32)
        h2 = PredictionCache.compute_hash(f2)
        assert h1 != h2

    def test_cache_miss(self):
        """未命中返回 None"""
        h = PredictionCache.compute_hash(self.features)
        result = self.cache.get("S001", h)
        assert result is None

    def test_cache_set_and_hit(self):
        """写入后命中"""
        h = PredictionCache.compute_hash(self.features)
        test_result = {"prediction": [1, 2, 3]}
        self.cache.set("S001", h, test_result)
        result = self.cache.get("S001", h)
        assert result == test_result

    def test_cache_invalidate_station(self):
        """按站点清除缓存"""
        h = PredictionCache.compute_hash(self.features)
        self.cache.set("S001", h, {"data": "S001"})
        self.cache.set("S002", h, {"data": "S002"})

        self.cache.invalidate_station("S001")
        assert self.cache.get("S001", h) is None  # S001 被清除
        # S002 L1 仍存在（Redis 取决于环境）

    def test_cache_stats(self):
        """统计信息"""
        h = PredictionCache.compute_hash(self.features)
        self.cache.get("S001", h)  # miss
        self.cache.set("S001", h, {"test": 1})
        self.cache.get("S001", h)  # hit

        stats = self.cache.stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["hit_rate"] > 0

    def test_lru_eviction(self):
        """LRU 淘汰：超过 max_size 时淘汰最旧条目"""
        # 创建一个小容量的缓存来测试淘汰
        small_cache = PredictionCache()
        small_cache._max_size = 3

        for i in range(5):
            f = np.random.randn(72, 7).astype(np.float32)
            h = PredictionCache.compute_hash(f)
            small_cache.set(f"S00{i % 5 + 1}", h, {"index": i})

        # L1 大小不超过 max_size
        assert len(small_cache._l1_cache) <= 3
```

- [ ] **Step 2: Run cache tests**

```bash
pytest tests/test_prediction_cache.py -v
```
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_prediction_cache.py
git commit -m "test: add prediction cache unit tests"
```

---

### Task 21: Write tests for CSV importer

**Files:**
- Create: `tests/test_csv_importer.py`

- [ ] **Step 1: Write CSV importer tests**

Create `tests/test_csv_importer.py`:

```python
"""CSV 导入器单元测试"""

import os
import tempfile
from pathlib import Path
from src.data_collection.csv_importer import CsvImporter


class TestCsvImporter:
    """CSV 导入测试"""

    def setup_method(self):
        self.importer = CsvImporter()

    def _create_test_csv(self, content: str) -> str:
        """创建临时 CSV 文件用于测试"""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        )
        tmp.write(content)
        tmp.close()
        return tmp.name

    def test_sniff_basic_csv(self):
        """测试基本 CSV 嗅探"""
        path = self._create_test_csv(
            "时间,水位(m),流量(m³/s),降雨量(mm)\n"
            "2024-01-01 00:00,12.5,300,0\n"
            "2024-01-01 01:00,12.6,310,2.5\n"
        )
        try:
            result = self.importer.sniff(path)
            assert result["encoding"] == "utf-8"
            assert result["row_count"] == 2
            assert len(result["headers"]) == 4
        finally:
            os.unlink(path)

    def test_load_with_mapping(self):
        """测试列映射加载"""
        path = self._create_test_csv(
            "测站编码,时间,水位(m),流量(m³/s),降雨量(mm)\n"
            "S001,2024-01-01 00:00,12.5,300,0\n"
            "S001,2024-01-01 01:00,12.6,310,2.5\n"
        )
        mapping = {
            "column_mapping": {
                "station_id": "测站编码",
                "timestamp": "时间",
                "water_level": "水位(m)",
                "flow_rate": "流量(m³/s)",
                "rainfall": "降雨量(mm)",
            },
            "datetime_format": "%Y-%m-%d %H:%M",
            "encoding": "utf-8",
            "delimiter": ",",
        }
        try:
            records, summary = self.importer.load_with_mapping(path, mapping)
            assert len(records) == 2
            assert records[0]["station_id"] == "S001"
            assert records[0]["water_level"] == "12.5" or records[0]["water_level"] == 12.5
            assert summary["valid_rows"] == 2
        finally:
            os.unlink(path)

    def test_load_missing_required_field(self):
        """缺少必选字段时抛出异常"""
        path = self._create_test_csv("时间,温度\n2024-01-01,25\n")
        mapping = {
            "column_mapping": {
                "timestamp": "时间",
                "temperature": "温度",
            },
        }
        try:
            import pytest
            with pytest.raises(ValueError, match="必选字段"):
                self.importer.load_with_mapping(path, mapping)
        finally:
            os.unlink(path)

    def test_template_save_and_list(self):
        """测试模板保存和列表"""
        template = {
            "template_name": "test_template",
            "column_mapping": {"station_id": "站号"},
            "encoding": "utf-8",
            "delimiter": ",",
        }
        path = self.importer.save_template(template)
        assert os.path.exists(path)

        templates = self.importer.list_templates()
        assert any(t["template_name"] == "test_template" for t in templates)

        # cleanup
        os.unlink(path)

    def test_import_history(self):
        """测试导入历史"""
        history = self.importer.get_import_history()
        assert isinstance(history, list)
```

- [ ] **Step 2: Run CSV importer tests**

```bash
pytest tests/test_csv_importer.py -v
```
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_csv_importer.py
git commit -m "test: add CSV importer unit tests"
```

---

### Task 22: Run full test suite

**Files:**
- None (verification only)

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests pass (existing tests from Week 1-3 + new Week 4 tests)

- [ ] **Step 2: Fix any failing tests**

If any tests fail, fix them inline. Common issues:
- Import errors due to missing dependencies → ensure `pip install` completed
- Redis connection errors → tests should handle Redis being unavailable (degraded mode)

- [ ] **Step 3: Run the API startup check**

```bash
python -c "
from src.web.app import app
print('FastAPI app loaded successfully')
print('Routes:', len(app.routes))
"
```
Expected: prints success message

- [ ] **Step 4: Verify create_admin script**

```bash
python scripts/create_admin.py
```
Expected: creates default accounts (or reports existing)

- [ ] **Step 5: Final commit if any fixes were made**

```bash
git add -A
git commit -m "chore: final test fixes and verification for Week 4"
```

---

### Task 23: Verify end-to-end workflow

**Files:**
- None (manual verification)

- [ ] **Step 1: Start the API server in background**

```bash
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000 &
sleep 3
```

- [ ] **Step 2: Test health endpoint**

```bash
curl -s http://localhost:8000/health | python -m json.tool
```
Expected: `{"status": "healthy", "version": "4.0.0", ...}`

- [ ] **Step 3: Test login endpoint**

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -m json.tool
```
Expected: returns access_token

- [ ] **Step 4: Test protected endpoint with token**

```bash
# 获取 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 使用 token 访问受保护端点
curl -s -X POST http://localhost:8000/api/v1/warnings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"warning_type":1,"warning_level":2,"title":"测试预警","content":"E2E测试","affected_location":"S001","expire_hours":24}' | python -m json.tool
```
Expected: 200 with warning created

- [ ] **Step 5: Test without token (should fail)**

```bash
curl -s -X POST http://localhost:8000/api/v1/warnings \
  -H "Content-Type: application/json" \
  -d '{"warning_type":1,"warning_level":2,"title":"Unauthorized Test","content":"Should fail","affected_location":"S001","expire_hours":24}' | python -m json.tool
```
Expected: 401

- [ ] **Step 6: Test public GET endpoint (should work without token)**

```bash
curl -s http://localhost:8000/api/v1/stations | python -m json.tool
```
Expected: 200 with station list

- [ ] **Step 7: Stop the API server**

```bash
kill %1 2>/dev/null || true
```

- [ ] **Step 8: Commit any final changes**

```bash
git status
# commit if needed
```
