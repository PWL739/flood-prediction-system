# Week 4 增强功能设计文档

**项目**：基于 LSTM-Attention 的洪水预测与预警系统
**日期**：2026-06-04
**状态**：已确认

---

## 一、概述

本文档描述第 4 周四个增强任务的设计方案：

1. **推理性能调优**：预测总耗时 ≤2 秒，引入两级结果缓存
2. **真实水文数据接入**：CSV 格式历史数据导入与清洗
3. **JWT 认证 + 四角色权限**：管理员/指挥/科研/基层
4. **操作日志中间件 + Redis 缓存**：基础配置落地

**架构策略：统一中间件层（方案 B）** — 将缓存、认证、日志统一为 FastAPI 中间件栈，Redis 作为共享基础设施，CSV 导入复用现有数据处理管道。

---

## 二、整体架构

### 中间件栈顺序

```
请求 → OperationLogMiddleware → AuthMiddleware → Router → Response
                ↓                      ↓
           Redis/DB 日志           JWT 校验 + RBAC
```

### 文件变更一览

```
src/
├── config/
│   └── settings.py              ✏️ 新增 JWT_SECRET, CACHE_CONFIG, ROLE_PERMISSIONS, CSV_IMPORT_CONFIG
├── data_collection/
│   └── csv_importer.py          ✨ CSV 灵活导入器（列映射+清洗+入库）
├── prediction_model/
│   ├── predictor.py             ✏️ 集成 PredictionCache，优化推理路径，模型预加载
│   └── prediction_cache.py      ✨ 两级缓存服务（L1 内存 + L2 Redis）
├── auth/
│   ├── __init__.py              ✨
│   ├── jwt_handler.py           ✨ JWT 生成/验证/解析
│   ├── role_manager.py          ✨ RBAC 权限矩阵
│   └── dependencies.py          ✨ FastAPI Depends 注入（get_current_user, require_role）
├── middleware/
│   ├── __init__.py              ✨
│   └── operation_log.py         ✨ 操作日志 ASGI 中间件
├── db/
│   ├── models.py                ✏️ 新增 User 表、OperationLog 表
│   └── redis_client.py          ✨ Redis 连接池管理
├── web/
│   ├── app.py                   ✏️ 注册中间件
│   ├── routes.py                ✏️ 操作端点加 Depends(auth)，新增 auth/logs/users/import 路由
│   └── schemas.py               ✏️ 新增登录/用户/CSV映射/日志查询 Pydantic
└── scripts/
    └── create_admin.py          ✨ 初始化管理员脚本

data/
└── import_templates/            ✨ CSV 映射模板存储目录
```

### 新增依赖

```
pyjwt>=2.8.0        # JWT 令牌处理
passlib[bcrypt]>=1.7.4  # 密码 bcrypt 哈希
```

---

## 三、任务1：推理性能优化 + 两级缓存

### 目标

- 单站点预测（数据预处理 + 模型推理 + 后处理）≤ 500ms
- 5 站点全量预测（串行）≤ 2s
- API 端到端响应时间 ≤ 2s

### 推理加速策略

1. **模型预加载**：FastAPI 启动时自动加载 5 个站点模型到 `FloodPredictor.model_registry`（字典），避免运行时 I/O
2. **TorchScript 可选编译**：`torch.jit.script(model)` 加速 20-30%，作为可选优化
3. **预处理向量化**：`predict_flood_risk()` 中将 pandas DataFrame 处理改为纯 NumPy 操作，消除 pandas 开销
4. **保持** `torch.no_grad()` + `model.eval()` 模式

### 两级缓存设计

```
请求预测(station_id, input_hash)
  │
  ├─ L1 内存缓存命中? ──→ 返回（<1ms）
  │     dict: {(station_id, input_hash): (prediction_result, created_at)}
  │     TTL: 5 分钟, max_size: 100 条, LRU 淘汰
  │
  ├─ L2 Redis 缓存命中? ──→ 回填 L1 → 返回（<10ms）
  │     key: "pred:{station_id}:{input_hash}"
  │     value: JSON 序列化的预测结果
  │     TTL: 15 分钟
  │
  └─ 未命中 → 执行推理 → 写 L2 → 写 L1 → 返回
```

### 关键设计细节

- `input_hash` = SHA256(归一化特征值最后 72 行的 bytes)，捕获输入数据实质性变化
- 时间窗口缓存：同一站点 5 分钟内多次请求共享同一结果（通过 L1 TTL 实现）
- Redis 不可用时自动降级为纯 L1 缓存，记录 WARNING 日志但不阻塞预测
- 缓存失效：当 `/sensor-data` 提交新数据时，主动清除对应站点的 L1/L2 缓存

### PredictionCache 类接口

```python
class PredictionCache:
    def __init__(self, redis_client=None)
    def get(station_id: str, input_hash: str) -> dict | None
    def set(station_id: str, input_hash: str, result: dict) -> None
    def invalidate_station(station_id: str) -> None
    def stats() -> dict  # 命中率等
```

### 文件变更

| 文件 | 动作 | 内容 |
|------|------|------|
| `src/prediction_model/prediction_cache.py` | 新增 | PredictionCache 类 |
| `src/prediction_model/predictor.py` | 修改 | 集成缓存、向量化预处理、模型预加载 |
| `src/db/redis_client.py` | 新增 | Redis 连接池管理 |
| `src/config/settings.py` | 修改 | CACHE_CONFIG 字典 |

---

## 四、任务2：CSV 真实水文数据导入

### 导入流程

```
CSV 文件路径
  │
  ├─ 1. 自动嗅探：chardet 检测编码，csv.Sniffer 检测分隔符/表头
  │
  ├─ 2. 列映射：用户提供映射配置（JSON），指定 CSV 列 → 系统标准字段
  │     必选字段：station_id, timestamp, water_level
  │     可选字段：flow_rate, rainfall, temperature, ph, turbidity, dissolved_oxygen
  │
  ├─ 3. 预处理：
  │     - 时间戳解析（自动检测格式，支持 ISO 8601 / yyyy-MM-dd HH:mm / Unix 时间戳）
  │     - 单位转换（cm→m, mm/h→mm 等，在映射配置中声明）
  │     - 站点 ID 映射（CSV 中的站点名 → 系统 S001-S005）
  │     - 缺失值标记
  │
  ├─ 4. 数据清洗：复用 DataValidator + BatchDataProcessor 管道
  │     - 范围校验（基于 SENSOR_CONFIG）
  │     - 3σ 异常值检测
  │     - 缺失值线性插值
  │     - 质量评分
  │
  └─ 5. 入库/导出：
  │     - 写入 cleaned_water_data 表
  │     - 可选导出为清洗后 JSON
  │     - 返回导入摘要（总数/有效/无效/质量分）
```

### 映射配置格式

```json
{
  "template_name": "水利部标准格式",
  "description": "某省水文局标准 CSV 导出格式",
  "column_mapping": {
    "station_id": "测站编码",
    "timestamp": "时间",
    "water_level": "水位(m)",
    "flow_rate": "流量(m³/s)",
    "rainfall": "降雨量(mm)",
    "temperature": "温度(℃)",
    "ph": "pH",
    "turbidity": "浊度(NTU)",
    "dissolved_oxygen": "溶解氧(mg/L)"
  },
  "datetime_format": "%Y-%m-%d %H:%M:%S",
  "skip_rows": 2,
  "encoding": "utf-8",
  "delimiter": ",",
  "unit_conversions": {
    "water_level": "cm_to_m"
  },
  "station_id_mapping": {
    "钱塘江上游": "S001",
    "钱塘江中游": "S002"
  }
}
```

### 新增 API 端点

| 方法 | 端点 | 权限 | 说明 |
|------|------|------|------|
| `POST` | `/api/v1/data/import-csv` | 管理员/指挥/科研 | 上传 CSV 文件 + 映射配置，执行导入 |
| `GET` | `/api/v1/data/import-templates` | 登录用户 | 获取已保存的映射模板列表 |
| `POST` | `/api/v1/data/import-templates` | 管理员/指挥/科研 | 保存新映射模板 |
| `GET` | `/api/v1/data/import-history` | 管理员/指挥/科研 | 查询导入历史记录 |

### CsvImporter 类接口

```python
class CsvImporter:
    def __init__(self)
    def sniff(self, filepath: str) -> dict  # 自动检测编码/分隔符/表头
    def load_with_mapping(
        self, filepath: str, mapping: dict
    ) -> tuple[list[dict], dict]  # 返回 (records, summary)
    def import_and_clean(
        self, filepath: str, mapping: dict
    ) -> dict  # 完整流程：加载→清洗→入库，返回摘要
```

### 文件变更

| 文件 | 动作 | 内容 |
|------|------|------|
| `src/data_collection/csv_importer.py` | 新增 | CsvImporter 类 |
| `src/web/routes.py` | 修改 | 新增 4 个导入端点 |
| `src/web/schemas.py` | 修改 | CsvMappingConfig, ImportResult |
| `data/import_templates/` | 新增目录 | 存放 .json 映射模板 |

---

## 五、任务3：JWT 认证 + 四角色权限

### 认证流程

```
POST /api/v1/auth/login  (公开)
  Body: {"username": "...", "password": "..."}
  │
  └─→ 200: {"code": 200, "data": {"access_token": "eyJ...",
        "token_type": "bearer", "expires_in": 7200,
        "user": {"username": "...", "role": "commander", "display_name": "..."}}}
  └─→ 401: 用户名或密码错误

后续操作请求:
  Authorization: Bearer eyJ...
    │
    ├─ 解析 JWT → user_id + role
    │
    └─ Depends(require_role("commander")) → 校验通过 → 执行
                                          → 403 → {"code": 403, "message": "权限不足"}
```

### 端点权限划分

**公开端点（无需认证）：**
- 所有 GET 端点（查询类）
- `POST /api/v1/auth/login`
- `GET /docs`, `GET /redoc`, `GET /health`, `GET /`

**需认证端点（需 JWT）：**

| 端点 | admin | commander | researcher | grassroots |
|------|:---:|:---:|:---:|:---:|
| `POST /api/v1/sensor-data` | ✅ | ✅ | ❌ | ✅ |
| `POST /api/v1/data/process-batch` | ✅ | ✅ | ✅ | ❌ |
| `POST /api/v1/data/import-csv` | ✅ | ✅ | ✅ | ❌ |
| `POST /api/v1/water-data/export` | ✅ | ✅ | ✅ | ❌ |
| `POST /api/v1/warnings` | ✅ | ✅ | ❌ | ❌ |
| `POST /api/v1/warnings/{id}/confirm` | ✅ | ✅ | ❌ | ❌ |
| `POST /api/v1/warnings/{id}/handle` | ✅ | ✅ | ❌ | ❌ |
| `POST /api/v1/warnings/{id}/resolve` | ✅ | ✅ | ❌ | ❌ |
| `POST /api/v1/warnings/{id}/escalate` | ✅ | ✅ | ❌ | ❌ |
| `POST /api/v1/warnings/{id}/cancel` | ✅ | ✅ | ❌ | ❌ |
| `POST /api/v1/users` | ✅ | ❌ | ❌ | ❌ |
| `DELETE /api/v1/users/{id}` | ✅ | ❌ | ❌ | ❌ |
| `PUT /api/v1/users/{id}/password` | ✅ | ❌ | ❌ | ❌ |
| `GET /api/v1/users` | ✅ | ❌ | ❌ | ❌ |
| `GET /api/v1/logs` | ✅ | ✅ | ❌ | ❌ |
| `GET /api/v1/data/import-templates` | ✅ | ✅ | ✅ | ✅ |
| `POST /api/v1/data/import-templates` | ✅ | ✅ | ✅ | ❌ |
| `GET /api/v1/data/import-history` | ✅ | ✅ | ✅ | ❌ |

**逻辑：** 指挥是决策者（管预警），基层是数据采集者（报数据），科研是分析者（查数据+分析），管理员是全局管理者。

### JWT 设计

- **算法**：HS256
- **有效期**：2 小时（access_token），无 refresh token（课程项目简化）
- **Payload**：`{sub: username, role: "admin", jti: uuid4, exp: ..., iat: ...}`
- **Secret**：`JWT_SECRET_KEY` 环境变量，默认值 `"flood-prediction-secret-key-change-in-production"`

### User 模型（新增数据库表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer, PK, 自增 | |
| `username` | String(50), UNIQUE, NOT NULL | 登录用户名 |
| `password_hash` | String(128), NOT NULL | bcrypt 哈希 |
| `role` | String(20), NOT NULL | admin / commander / researcher / grassroots |
| `display_name` | String(100) | 显示名称 |
| `is_active` | Boolean, default=True | 启用/禁用 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

### 新增 API 端点

| 方法 | 端点 | 权限 | 说明 |
|------|------|------|------|
| `POST` | `/api/v1/auth/login` | 公开 | 登录获取 Token |
| `GET` | `/api/v1/auth/me` | 登录用户 | 获取当前用户信息 |
| `POST` | `/api/v1/users` | 管理员 | 创建用户 |
| `GET` | `/api/v1/users` | 管理员 | 用户列表（支持分页） |
| `DELETE` | `/api/v1/users/{id}` | 管理员 | 删除用户（软删除，设 is_active=False） |
| `PUT` | `/api/v1/users/{id}/password` | 管理员 | 重置密码 |

### 认证模块结构

```
src/auth/
├── __init__.py           # 空
├── jwt_handler.py        # JWTHandler 类
│   - create_access_token(data: dict) -> str
│   - decode_token(token: str) -> dict
│   - get_token_from_header(authorization: str) -> str
├── role_manager.py       # RoleManager 类 + ROLE_PERMISSIONS 字典
│   - has_permission(role: str, action: str) -> bool
│   - get_role_permissions(role: str) -> list[str]
├── dependencies.py       # FastAPI Depends 可注入函数
│   - get_current_user(authorization: str | None) -> UserPayload
│   - require_role(action: str) -> Callable  (工厂函数，返回 Depends)
```

### 初始化

`scripts/create_admin.py`：读取环境变量 `ADMIN_USERNAME`/`ADMIN_PASSWORD`（默认 admin/admin123），创建默认管理员账户。

### 文件变更

| 文件 | 动作 | 内容 |
|------|------|------|
| `src/auth/__init__.py` | 新增 | |
| `src/auth/jwt_handler.py` | 新增 | JWT 处理 |
| `src/auth/role_manager.py` | 新增 | 权限矩阵 |
| `src/auth/dependencies.py` | 新增 | FastAPI 依赖注入 |
| `src/db/models.py` | 修改 | 新增 User 表 |
| `src/web/routes.py` | 修改 | 操作端点加 Depends，新增 auth/users 路由 |
| `src/web/schemas.py` | 修改 | LoginRequest, LoginResponse, UserCreate 等 |
| `src/config/settings.py` | 修改 | JWT_SECRET_KEY, ROLE_PERMISSIONS |
| `scripts/create_admin.py` | 新增 | 管理员初始化脚本 |

---

## 六、任务4：操作日志中间件 + Redis 缓存基础配置

### 操作日志中间件

**实现**：FastAPI `@app.middleware("http")` — 纯 ASGI 中间件，不侵入路由代码。

**记录范围**：所有 POST / PUT / DELETE 请求。

**日志结构**：

```python
{
    "id": int,                      # 自增主键
    "timestamp": datetime,          # 请求到达时间
    "user_id": str | None,          # 从 JWT 解析，未认证为 "anonymous"
    "role": str | None,             # 用户角色
    "method": str,                  # HTTP 方法
    "path": str,                    # 请求路径
    "status_code": int,             # 响应状态码
    "duration_ms": int,             # 请求处理耗时
    "ip_address": str,              # 客户端 IP
    "user_agent": str | None,       # User-Agent
    "request_summary": str | None,  # 操作摘要（从路径和请求体推断）
}
```

**操作摘要推断规则**：
- 从路径中提取操作类型（如 `/warnings` → "预警操作"，`/sensor-data` → "传感器数据提交"）
- 从请求体中提取关键字段（如预警标题、站点 ID）
- 长度限制 200 字符

**存储策略**：
- 内存缓冲区：`collections.deque(maxlen=1000)`，供实时查询
- 数据库持久化：写入 `operation_log` 表，异步批量写入（缓冲区满 50 条或 30 秒刷入）

**查询端点**：`GET /api/v1/logs`（管理员/指挥）
- 查询参数：`user_id`, `method`, `path`, `start_time`, `end_time`, `limit`(默认100), `offset`

### OperationLog 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK 自增 | |
| `timestamp` | DateTime NOT NULL | 请求时间 |
| `user_id` | String(50) | 用户标识 |
| `role` | String(20) | 角色 |
| `method` | String(10) NOT NULL | HTTP 方法 |
| `path` | String(200) NOT NULL | 请求路径 |
| `status_code` | Integer | 响应状态码 |
| `duration_ms` | Integer | 耗时（毫秒） |
| `ip_address` | String(45) | 客户端 IP |
| `user_agent` | String(500) | |
| `request_summary` | String(200) | 操作摘要 |

### Redis 缓存基础配置

复用已有 `REDIS_CONFIG`（`settings.py`），激活并用于以下场景：

| 场景 | Key 模式 | 类型 | TTL | 说明 |
|------|---------|------|-----|------|
| 预测结果 L2 缓存 | `pred:{station_id}:{input_hash}` | String (JSON) | 15 min | 跨进程预测缓存 |
| JWT 黑名单 | `jwt:blacklist:{jti}` | String | Token 剩余有效期 | 登出/强制失效 |
| 操作日志缓冲 | `log:buffer` | List (LPUSH) | 持久 | 异步批量写入 DB |
| 站点实时数据快照 | `realtime:{station_id}` | String (JSON) | 5 min | 加速实时查询 |
| 速率限制计数器 | `ratelimit:{user_id}:{window}` | String (INCR) | 窗口时长 | 预留，当前不启用 |

### Redis 连接管理

```python
# src/db/redis_client.py
class RedisClient:
    _instance = None

    def __new__(cls) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pool = None
        return cls._instance

    @property
    def client(self) -> redis.Redis | None:
        """返回 Redis 客户端，不可用时返回 None"""
        ...

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl: int | None = None) -> bool: ...
    def delete(self, key: str) -> bool: ...
    def health_check(self) -> bool: ...
```

**降级策略**：Redis 不可用时所有 `get` 返回 `None`，`set` 返回 `False`，调用方自动降级（L1 缓存、内存日志缓冲、跳过黑名单校验）。

### 文件变更

| 文件 | 动作 | 内容 |
|------|------|------|
| `src/middleware/__init__.py` | 新增 | |
| `src/middleware/operation_log.py` | 新增 | OperationLogMiddleware |
| `src/db/redis_client.py` | 新增 | RedisClient 单例 |
| `src/db/models.py` | 修改 | 新增 OperationLog 表 |
| `src/web/app.py` | 修改 | 注册中间件 |
| `src/web/routes.py` | 修改 | 新增 `/logs` 查询端点 + 传感器提交时清除缓存 |
| `src/config/settings.py` | 修改 | LOG_CONFIG, REDIS_TTL 配置 |

---

## 七、错误处理约定

- **401**：Token 缺失、无效或过期
- **403**：角色权限不足
- **404**：资源不存在（站点、预警等，保持不变）
- **422**：Pydantic 请求体验证失败（FastAPI 默认）
- **500**：服务器内部错误（Redis 不可用不触发 500，仅降级）

---

## 八、测试要点

1. **预测缓存**：命中/未命中/过期/Redis 降级
2. **CSV 导入**：标准格式/带映射/缺少必选列/编码错误
3. **JWT 认证**：登录/过期 Token/错误 Token/公开端点免认证
4. **RBAC**：每种角色尝试越权操作 → 403
5. **操作日志**：操作被记录/匿名用户记录/日志查询权限
6. **Redis 降级**：关闭 Redis → 系统正常运行（缓存降级、日志写内存）

---

## 九、兼容性说明

- 现有端点路径不变，公开 GET 端点行为不变
- 现有 POST/PUT/DELETE 端点新增 Authorization header 要求
- Streamlit 仪表盘调用 API 时需在请求头中携带 Token（从 Streamlit session 获取）
- 新的 User/OperationLog 表通过 `init_db.py` 自动创建
