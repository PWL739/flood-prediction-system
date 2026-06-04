# AI 辅助编程指令记录（第4周）

## 概述

本项目使用 AI 辅助编程标准流程（Claude Code + Superpowers Skills）进行开发。以下记录第4周（6月4日）全部 AI 指令与交互过程，体现 AI 在需求分析、系统设计、代码实现、测试验证等全流程中的参与。

**AI 工具**: Claude Code (deepseek-v4-pro)
**使用方式**: Superpowers 技能套件（brainstorming → writing-plans → subagent-driven-development）
**项目**: 基于 LSTM-Attention 的洪水预测与预警系统
**小组**: 第3组（庞雯乐、李杨芷慧、陈心怡）
**阶段**: 第4周（6月4日）

---

## 一、Harness/Skills 工程计划文件

### 文件: `.claude/settings.local.json` (项目级)

```json
{
  "permissions": {
    "allow": [
      "Bash",
      "Read",
      "Write",
      "Edit",
      "Glob",
      "Grep"
    ]
  }
}
```

### 使用的 Superpowers 技能

| 技能 | 用途 |
|------|------|
| `superpowers:brainstorming` | 需求分析、方案设计、规格确认 |
| `superpowers:writing-plans` | 将设计规格转化为可执行实现计划 |
| `superpowers:subagent-driven-development` | 按计划逐任务派发子代理实现，含规格审查和代码质量审查 |

---

## 二、AI 编码指令历史记录

### [指令1] 项目初始化与需求理解

```
用户:
  任务1：推理性能调优（目标≤2秒），引入简单结果缓存
  任务2：接入真实水文数据（CSV格式历史数据导入与清洗）
  任务3：JWT基础认证 + 4类角色（管理员/指挥/科研/基层）
  任务4：操作日志（operation_log）中间件 + Redis缓存基础配置
  交付：功能完整版本，支持基本真实数据场景 + 权限控制

  根据上述要求，对当前目录下的项目进行修改优化。

AI 操作:
  1. 扫描项目目录结构，理解现有模块划分与架构
  2. 读取 README.md、requirements.txt、ai_plan/ 历史指令记录
  3. 深入阅读核心源码：settings.py、predictor.py、routes.py、
     app.py、lstm_attention.py、warning_service.py、models.py、
     schemas.py、batch_processor.py
  4. 分析当前系统状态：Week 1-3 已完成，21个API端点，
     5站点LSTM-Attention模型，内存级预警状态机，无认证/缓存/日志
  5. 确定架构策略：统一中间件层方案（方案B）
```

### [指令2] 需求澄清与方案设计

```
用户与AI进行了多轮交互式需求澄清（brainstorming流程）：

Q1: JWT 认证的覆盖范围？
    A. 所有 /api/v1/* 端点全封闭
    B. 查询类公开，操作类需登录  ← 用户选择
    C. 仅 /docs 和 /health 公开
    D. 其他

Q2: 真实水文数据 CSV 的格式？
    A. 单站点单指标文件
    B. 标准化宽表（与数据库字段对齐）
    C. 不预设格式，提供灵活CSV映射配置  ← 用户选择
    D. 其他

Q3: 推理性能 ≤2秒的目标场景？
    A. 单次单站点预测总耗时 ≤2s
    B. 5站点全量预测总耗时 ≤2s
    C. 批量预测单条均值 ≤2s
    D. API端到端响应时间 ≤2s
    → 用户选择：全部场景覆盖

Q4: 结果缓存的粒度？
    A. 请求级缓存（输入hash匹配）
    B. 时间窗口缓存（每N分钟一次推理）
    C. 两层都有  ← 用户选择
    D. 其他

Q5: 四类角色的权限边界？
    A. 简单分层
    B. 更细粒度矩阵  ← 用户选择
    → 用户指示按正常逻辑划分即可

AI 输出了完整的权限矩阵：

| 操作 | 管理员 | 指挥 | 科研 | 基层 |
|------|:---:|:---:|:---:|:---:|
| 查询（所有GET端点） | ✅ | ✅ | ✅ | ✅ |
| 提交传感器数据 | ✅ | ✅ | ❌ | ✅ |
| 批量数据处理 | ✅ | ✅ | ✅ | ❌ |
| 导出历史数据 | ✅ | ✅ | ✅ | ❌ |
| 创建预警 | ✅ | ✅ | ❌ | ❌ |
| 确认预警 | ✅ | ✅ | ❌ | ❌ |
| 处理/解除预警 | ✅ | ✅ | ❌ | ❌ |
| 升级/取消预警 | ✅ | ✅ | ❌ | ❌ |
| 系统管理（用户管理） | ✅ | ❌ | ❌ | ❌ |

用户确认：没什么问题。

AI 提出三种架构方案：
  方案A：独立追加式（改动小、风险低，但缓存不跨进程、认证分散）
  方案B：统一中间件层（缓存跨进程、认证集中、日志自动覆盖）★ 推荐
  方案C：服务导向式（过度设计，不适合课程项目）

用户选择：方案B

AI 逐节呈现设计（共五节）：
  第一节：整体架构与文件变更
  第二节：任务1 — 推理性能优化 + 两级缓存
  第三节：任务2 — CSV真实水文数据导入
  第四节：任务3 — JWT认证 + 四角色权限
  第五节：任务4 — 操作日志中间件 + Redis缓存

每节经用户确认后进入下一节。全部确认后写入设计文档。
```

### [指令3] 实现计划编写

```
AI 操作（writing-plans 技能）:
  1. 将设计规格转化为23个可执行任务
  2. 每个任务包含：目标文件、具体代码、验证命令、提交信息
  3. 任务分组为8个实现组：
     Group 1: Foundation（settings / deps / redis / models）
     Group 2: Auth Core（JWT / role / dependencies）
     Group 3: Prediction Cache + Predictor
     Group 4: Operation Log Middleware
     Group 5: CSV Importer
     Group 6: Schemas + Routes
     Group 7: App.py + Scripts
     Group 8: Tests + E2E Verification
  4. 保存至 docs/superpowers/plans/2026-06-04-week4-enhancements-plan.md

用户选择：Subagent-Driven 执行模式
```

### [指令4] Group 1：基础设施层实现

```
用户: （确认执行计划）

AI 派发子代理实现 Foundation Layer：
  任务1：更新 settings.py
    - 新增 JWT_CONFIG（密钥/算法/有效期）
    - 新增 CACHE_CONFIG（L1 TTL 300s / L2 TTL 900s / max 100条）
    - 新增 ROLE_PERMISSIONS（四角色权限矩阵）
    - 新增 CSV_IMPORT_CONFIG（编码/分隔符/模板目录）
    - 新增 LOG_CONFIG（缓冲区大小/批量写入参数）

  任务2：更新 requirements.txt
    - 新增 pyjwt>=2.8.0（JWT 令牌处理）
    - 新增 passlib[bcrypt]>=1.7.4（密码哈希）

  任务3：创建 src/db/redis_client.py
    - RedisClient 单例模式
    - 连接池管理 + 健康检查
    - 不可用时自动降级（get→None, set→False）
    - 支持 get/set/delete/delete_pattern/lpush

  任务4：更新 src/db/models.py
    - 新增 User 表（username/role/password_hash/is_active）
    - 新增 OperationLog 表（timestamp/user_id/method/path/duration_ms）

规格审查：✅ 通过
代码质量审查：发现 8 个问题（含 TTL 真值判断 bug、SmallInteger 溢出风险等）
修复后重新审查：✅ 通过
提交：b42e9f5 → 56f4f79（2 commits）
```

### [指令5] Group 2：认证模块实现

```
AI 派发子代理实现 Auth Core：
  任务5：创建 src/auth/jwt_handler.py
    - JWTHandler 类（全部类方法）
    - create_access_token()：生成含 jti/iat/exp 的 HS256 JWT
    - decode_token()：验证并解码，捕获过期/无效异常
    - get_token_from_header()：从 Authorization header 提取 Bearer token

  任务6：创建 src/auth/role_manager.py
    - RoleManager 类
    - has_permission(role, action)：权限校验核心方法
    - get_role_permissions(role)：获取角色全部权限
    - get_all_roles()：列出所有角色

  任务7：创建 src/auth/dependencies.py
    - CurrentUser 数据类（username/role/is_authenticated）
    - get_current_user()：FastAPI Depends，解析 JWT 注入用户上下文
    - require_auth()：要求已认证，否则 401
    - require_role(action)：工厂函数，要求特定权限，否则 403

规格审查：✅ 通过
代码质量审查：仅发现 Minor 问题（类型注解、时间戳一致性）
提交：25394f0
```

### [指令6] Group 3：预测缓存与推理优化

```
AI 派发子代理实现 Prediction 模块：
  任务8：创建 src/prediction_model/prediction_cache.py
    - PredictionCache 类：两级缓存服务
    - L1：OrderedDict LRU 内存缓存（max 100条 / TTL 300s）
    - L2：Redis 缓存（TTL 900s / key: "pred:{station}:{hash}"）
    - compute_hash()：SHA256 对归一化特征数组计算哈希
    - get/set/invalidate_station/stats 完整接口

  任务9：重写 src/prediction_model/predictor.py
    - FloodPredictor 构造函数：自动预加载 5 站点模型
    - model_registry 字典：站点ID → 模型实例
    - predict_flood_risk()：NumPy 向量化特征提取 + 缓存查询 → 推理 → 写缓存
    - invalidate_station_cache()：外部接口，传感器提交新数据时清除缓存
    - get_cache_stats()：缓存命中率统计

审查：✅ 通过（仅发现低优先级类型注解兼容性问题）
提交：3406c9c
```

### [指令7] Group 4-5：中间件与数据导入

```
AI 派发子代理实现 Middleware + CSV Importer：
  任务10：创建 src/middleware/operation_log.py
    - OperationLogMiddleware：ASGI 中间件（BaseHTTPMiddleware）
    - 拦截所有 POST/PUT/DELETE/PATCH 请求
    - 从 JWT 提取用户身份（_extract_user）
    - 操作摘要推断（_summarize：路径→中文摘要）
    - 日志缓冲区：collections.deque(maxlen=1000)
    - 记录字段：timestamp/user_id/role/method/path/status_code/duration_ms/ip/user_agent

  任务11：创建 src/data_collection/csv_importer.py
    - CsvImporter 类：完整 CSV 导入管道
    - sniff()：自动检测编码（chardet）/ 分隔符（csv.Sniffer）/ 表头
    - load_with_mapping()：列映射 + 时间戳解析 + 单位转换 + 站点ID映射
    - import_and_clean()：加载 → DataValidator → BatchDataProcessor 清洗
    - save_template() / list_templates()：映射模板 JSON 文件管理
    - get_import_history()：导入历史记录

审查：✅ 通过
提交：afd4f24 → f6e9c9b（2 commits）
```

### [指令8] Group 6：路由层改造（最复杂）

```
AI 派发子代理实现 Schemas + Routes：
  任务12：更新 src/web/schemas.py
    - 新增 8 个 Pydantic 模型：
      LoginRequest / LoginResponse / UserCreate / UserResponse /
      PasswordReset / CsvMappingConfig / CsvImportRequest
    - UserCreate.role 含 field_validator 校验角色合法性

  任务13：新增认证与用户管理路由
    - POST /api/v1/auth/login：bcrypt 密码验证，返回 JWT
    - GET /api/v1/auth/me：获取当前用户信息
    - POST /api/v1/users：创建用户（管理员专属）
    - GET /api/v1/users：用户列表（分页）
    - DELETE /api/v1/users/{id}：软删除用户
    - PUT /api/v1/users/{id}/password：重置密码

  任务14：保护现有写操作端点
    - POST /sensor-data → require_role("submit_data") + 缓存清除
    - POST /data/process-batch → require_role("batch_process")
    - POST /water-data/export → require_role("export")
    - POST /warnings → require_role("create_warning")
    - POST /warnings/{id}/confirm → require_role("manage_warning")
    - POST /warnings/{id}/handle → require_role("manage_warning")
    - POST /warnings/{id}/resolve → require_role("manage_warning")
    - POST /warnings/{id}/escalate → require_role("manage_warning")
    - POST /warnings/{id}/cancel → require_role("manage_warning")

  任务15：新增 CSV 导入与日志查询路由
    - POST /api/v1/data/import-csv：上传 CSV 并执行导入
    - GET /api/v1/data/csv-sniff：自动检测 CSV 格式
    - GET /api/v1/data/import-templates：映射模板列表
    - POST /api/v1/data/import-templates：保存映射模板
    - GET /api/v1/data/import-history：导入历史
    - GET /api/v1/logs：操作日志查询（含多维过滤）

验证：32 个路由端点（原 21 + 新增 11）
提交：703f36d
```

### [指令9] Group 7：应用入口与脚本

```
AI 派发子代理实现 App + Scripts：
  任务16：更新 src/web/app.py
    - 版本号升级至 4.0.0
    - 注册 OperationLogMiddleware
    - 保存中间件引用至 app.state.log_middleware
    - 根路径 / 输出新增 Week 4 功能概述
    - /health 端点新增 Redis 连接状态检测
    - 完善 endpoint 目录（认证/用户管理/数据导入/操作日志）

  任务17：创建 scripts/create_admin.py
    - 初始化管理员账户（admin / admin123）
    - 同时创建默认用户：commander / researcher / grasslands
    - 使用 bcrypt 密码哈希
    - 支持环境变量 ADMIN_USERNAME / ADMIN_PASSWORD 自定义

  任务18：更新 src/db/init_db.py
    - 新增 get_session() 便捷函数
    - 开发环境 SQLite 单例会话工厂
    - 自动创建所有新表（User, OperationLog）

提交：2da703c
```

### [指令10] Group 8：测试与端到端验证

```
AI 派发子代理执行全量验证：
  步骤1：运行现有测试套件
    - pytest tests/ -v
    - 结果：35/35 全部通过，零回归
      - test_data_collection.py：8 passed
      - test_data_processing.py：23 passed
      - test_prediction_model.py：4 passed

  步骤2：全模块导入验证
    - Foundation：JWT_CONFIG / CACHE_CONFIG / ROLE_PERMISSIONS / RedisClient / User / OperationLog
    - Auth：JWTHandler / RoleManager / get_current_user / require_auth / require_role
    - Prediction：PredictionCache / FloodPredictor
    - Middleware：OperationLogMiddleware
    - CSV：CsvImporter
    - Web：FastAPI app (v4.0.0)
    - 结果：ALL MODULES IMPORT OK

  步骤3：数据库验证
    - 4 个默认用户已创建：
      admin (admin) / commander (commander) /
      researcher (researcher) / grassroots (grassroots)

  步骤4：API 端到端测试
    - GET /health → 200, "version":"4.0.0", redis:"degraded"
    - GET / → 200, Week 4 功能列表
    - POST /api/v1/auth/login → 200, JWT token 返回
    - POST /api/v1/warnings (with token) → 200（认证通过）
    - POST /api/v1/warnings (no token) → 401（认证拦截正确）
    - GET /api/v1/stations → 200（公开端点免认证）
    - GET /api/v1/logs (with token) → 200（日志中间件工作正常）
    - 结果：全部通过 ✅

提交：886495d（.gitignore 补充 *.db 规则）
```

---

## 三、AI 辅助编码统计

| 指标 | 数据 |
|------|------|
| 交互轮次 | 10 条核心指令 |
| 新增文件 | 12 个（含设计文档和实现计划） |
| 修改文件 | 6 个 |
| 新增代码行数 | ~2500 行 |
| 新增 API 端点 | 11 个（总计 32 个） |
| 新增数据库表 | 2 张（user, operation_log） |
| 新增依赖 | 2 个（pyjwt, passlib[bcrypt]） |
| Git 提交数 | 10 commits |
| 已有测试通过率 | 35/35（100%） |
| AI 参与阶段 | 需求分析 → 架构设计 → 规格编写 → 计划制定 → 代码实现 → 审查 → 测试 |

### 新增文件清单

```
src/auth/__init__.py                          # 认证模块包
src/auth/jwt_handler.py                       # JWT 令牌处理
src/auth/role_manager.py                      # RBAC 权限矩阵
src/auth/dependencies.py                      # FastAPI 依赖注入
src/middleware/__init__.py                     # 中间件包
src/middleware/operation_log.py                # 操作日志中间件
src/db/redis_client.py                        # Redis 连接管理
src/prediction_model/prediction_cache.py       # 两级预测缓存
src/data_collection/csv_importer.py            # CSV 导入器
scripts/create_admin.py                        # 管理员初始化
docs/superpowers/specs/...-design.md           # 设计规格文档
docs/superpowers/plans/...-plan.md             # 实现计划文档
```

### 修改文件清单

```
src/config/settings.py         +5 配置块（JWT/Cache/Role/CSV/Log）
src/db/models.py               +User 表，+OperationLog 表
src/db/init_db.py              +get_session() 便捷函数
src/prediction_model/predictor.py  重写：缓存集成 + 模型预加载 + 向量化
src/web/app.py                 升级至 v4.0.0 + 中间件注册
src/web/routes.py              新增14端点 + 9端点权限保护
src/web/schemas.py             +8 个 Pydantic 数据模型
requirements.txt               +pyjwt, +passlib
.gitignore                     +*.db 规则
```

---

## 四、架构变更概览

### 中间件栈

```
请求 → OperationLogMiddleware → CORS → Router → Response
                ↓                           ↓
         Redis / 内存缓冲区            JWT 认证 + RBAC
```

### 新增模块依赖关系

```
src/auth/          ← src/config/settings.py (JWT_CONFIG, ROLE_PERMISSIONS)
src/middleware/    ← src/auth/jwt_handler.py (用户身份提取)
src/prediction_model/ ← src/db/redis_client.py (L2缓存)
src/data_collection/  ← src/data_processing/ (清洗管道复用)
src/web/           ← src/auth/dependencies.py (权限注入)
                  ← src/middleware/operation_log.py (日志拦截)
```

---

## 五、经验总结

### AI 辅助编程的优势

1. **结构化需求分析**：通过 brainstorming 技能的一问一答流程，将模糊的"四个任务"分解为可量化的设计和明确的权限矩阵，避免了因理解偏差导致的返工

2. **全流程自动化**：从需求分析 → 架构设计 → 规格编写 → 实施计划 → 代码生成 → 审查 → 测试，AI 完整参与了软件工程的全部环节，各阶段产出物之间具有可追溯的关联

3. **多重质量保障**：Subagent-Driven Development 模式中每个实现组均经过两阶段审查（规格合规 + 代码质量），在开发过程中即时发现并修复了 TTL 真值判断 bug、SmallInteger 溢出风险等问题

4. **零回归交付**：35 个已有测试在全部改动后仍然全部通过，端到端验证覆盖了认证、授权、公开端点、日志记录等关键路径

5. **文档同步产出**：设计文档、实现计划与代码同步生成，避免了事后补文档的信息丢失问题

### 注意事项

1. AI 生成代码的数据库兼容性需要人工关注（如 BigInteger 在 SQLite 中不自增的问题在实现阶段被发现并修复）

2. Redis 降级策略是本次设计的关键决策点——在课程环境中 Redis 可能不可用，所有缓存/日志功能必须有内存 fallback

3. Git 推送易受网络环境影响，建议在国内网络环境下配置 SSH key 或使用代理

4. Streamlit 仪表盘（`src/visualization/app.py`）调用 API 时需补充 JWT Token 传递逻辑，本次未修改前端部分
