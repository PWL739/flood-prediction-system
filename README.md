# 基于 LSTM-Attention 的洪水预测与预警系统 Flood Prediction & Early Warning System

利用 BiLSTM + Attention 机制，基于 5 个监测站点过去 72 小时水文数据，预测未来 24 小时水位变化，并实现四级洪水预警与状态机管理。**Week 3 新增：注意力热力图、FastAPI+Streamlit 全接口对接、预警统计看板。**

## 组别 Team

**第 3 组** | 智慧水利应用课程

| 成员 | 角色 | 职责 |
|------|------|------|
| 庞雯乐 | 项目经理 | 需求分析、系统架构设计 |
| 李杨芷慧 | AI 开发 | LSTM-Attention 模型开发与训练、API 开发 |
| 陈心怡 | 前端与可视化 | Streamlit 仪表盘、数据可视化 |

## 系统架构 Architecture

```
┌──────────────┐    ┌──────────────┐    ┌───────────────┐    ┌──────────────┐
│  传感器模拟   │───▶│  数据处理管道  │───▶│  LSTM-Attention│───▶│  预警状态机   │
│  5站点×30天   │    │  校验/清洗/   │    │  训练 + 推理   │    │  发布→确认→  │
│  水位/降雨/水质│    │  聚合/特征工程 │    │  5站点独立模型 │    │  处理→解除    │
└──────────────┘    └──────────────┘    └───────────────┘    └──────────────┘
       │                                                              │
       └─────────────────── FastAPI + Streamlit ──────────────────────┘
                           RESTful API / 可视化仪表盘
```

## 项目结构 Project Structure

```
flood-prediction-system/
├── src/
│   ├── config/settings.py            # 系统配置（站点、模型参数、阈值）
│   ├── data_collection/              # 数据采集模块
│   │   ├── sensor_simulator.py       #   传感器模拟器（水位/降雨/水质，Markov过程）
│   │   └── data_collector.py         #   数据采集服务（5站点管理）
│   ├── data_processing/              # 数据处理模块
│   │   ├── data_validator.py         #   数据校验与清洗
│   │   ├── data_preprocessor.py      #   预处理（归一化/标准化/滑动窗口）
│   │   ├── data_aggregator.py        #   时序聚合与流域特征计算
│   │   └── batch_processor.py        #   批量数据处理管道
│   ├── prediction_model/             # 预测模型模块
│   │   ├── lstm_attention.py         #   BiLSTM + Attention 模型定义
│   │   ├── trainer.py                #   训练器（Early Stopping）
│   │   ├── predictor.py              #   推理与洪水风险评估
│   │   └── warning_service.py        #   预警服务 + 状态机
│   ├── db/                           # 数据库模块
│   │   ├── models.py                 #   ORM 模型（10 张表，含数据分层存储）
│   │   ├── init_db.py                #   数据库初始化
│   │   └── data_ingestion.py         #   数据入库管道
│   ├── web/                          # Web API 模块
│   │   ├── app.py                    #   FastAPI 应用入口
│   │   ├── routes.py                 #   API 路由（21个端点）
│   │   └── schemas.py                #   Pydantic 数据模型
│   └── visualization/                # 可视化模块
│       └── app.py                    #   Streamlit 仪表盘（7页面，含注意力热力图）
├── scripts/
│   ├── run_pipeline.py               # 端到端流程演示
│   ├── train_model.py                # 模型训练脚本（5站点 × 30天 × 24h）
│   ├── run_api.sh                    # API 启动脚本
│   └── run_streamlit.sh             # Streamlit 启动脚本
├── models/                           # 已训练模型
│   ├── lstm_attention_S001.pt        #   站点 S001 模型
│   ├── lstm_attention_S002.pt        #   站点 S002 模型
│   ├── lstm_attention_S003.pt        #   站点 S003 模型
│   ├── lstm_attention_S004.pt        #   站点 S004 模型
│   ├── lstm_attention_S005.pt        #   站点 S005 模型
│   └── training_summary.json         #   训练结果汇总
├── data/                             # 数据文件
├── tests/                            # 单元测试
│   ├── test_data_collection.py
│   ├── test_data_processing.py
│   └── test_prediction_model.py
├── ai_plan/                          # AI 辅助编程记录
├── requirements.txt
└── README.md
```

## 核心模块 Core Modules

### 1. 传感器模拟 Data Collection

| 类 | 功能 |
|----|------|
| `WaterLevelSensor` | 模拟水位数据（日周期 + 噪声） |
| `RainfallSensor` | 模拟降雨事件（Markov 过程） |
| `WaterQualitySensor` | 模拟水质数据（pH、浊度、溶解氧） |
| `SensorDataCollector` | 管理 5 个监测站点 |
| `DataCollectionService` | 高层采集接口，含实时 + 批量采集 |

### 2. 数据处理 Data Processing

- **DataValidator**: 范围校验 / 逻辑校验 / 时间戳校验，批量校验 + 质量评分
- **DataPreprocessor**: Min-Max 归一化 / Z-score 标准化 / 滑动窗口（72→24）
- **DataAggregator**: 24h 时序聚合统计 + 流域特征计算（坡度、植被覆盖率等）
- **BatchDataProcessor**: 批量数据文件加载 + 完整处理管道（清洗→特征工程→数据集构建）

### 3. LSTM-Attention 预测模型

**算法流程**: BiLSTM 提取时序特征 → Attention 聚焦关键时间步 → 全连接层输出 24h 水位预测

| 参数 | 值 |
|------|-----|
| input_size | 7（水位、流量、降雨、温度、pH、浊度、溶解氧） |
| hidden_size | 128 |
| num_layers | 2（双向） |
| seq_length | 72 小时 |
| output_size | 24 小时 |
| batch_size | 16 |
| epochs | 30（Early Stopping） |

5 个站点独立训练，模型权重保存至 `models/` 目录。

### 4. 预警状态机 Warning State Machine

```
已发布 (1) → 已确认 (2) → 处理中 (3) → 已解除 (4)
    ↓                                     ↓
  已取消 (0)                            已取消 (0)
```

四个预警等级：🔵 蓝色 → 🟡 黄色 → 🟠 橙色 → 🔴 红色

支持预警升级（escalate）和取消（cancel）操作。

### 5. 数据库 Database

10 张表，含三层数据分层存储（原始→清洗→特征）：

| 表名 | 说明 |
|------|------|
| `monitor_station` | 监测站点信息 |
| `water_monitoring_data` | 水文监测时序数据 |
| `water_quality_data` | 水质监测数据 |
| `flood_prediction_record` | 预测记录 |
| `warning_info` | 预警信息（含状态机字段） |
| `basin_feature` | 流域水文特征（24h聚合统计） |
| `forecast_result` | 完整预测结果 |
| `model_version` | 模型版本管理 |
| `raw_water_data` | 原始数据层（Tier 1） |
| `cleaned_water_data` | 清洗数据层（Tier 2） |
| `feature_data` | 特征数据层（Tier 3） |

### 6. Web API

FastAPI 提供 21 个 RESTful 端点，统一 JSON 响应格式 `{"code": 200, "message": "success", "data": ...}`：

**站点管理**: `GET /api/v1/stations`

**实时数据**: `GET /api/v1/water-data/realtime` | `POST /api/v1/sensor-data`

**历史数据**: `GET /api/v1/water-data/history` | `POST /api/v1/water-data/export`

**批量处理**: `GET /api/v1/data-stats` | `POST /api/v1/data/process-batch`

**预测**: `GET /api/v1/prediction/flood-risk` | `GET /api/v1/prediction/all-stations` | `GET /api/v1/prediction/attention-heatmap` (Week 3 新增)

**预警管理**: `POST /api/v1/warnings` | `GET /api/v1/warnings/active` | `GET /api/v1/warning/list`

**状态机操作**: `POST /api/v1/warnings/{id}/confirm` | `/handle` | `/resolve` | `/escalate` | `/cancel` | `GET /api/v1/warnings/{id}/state`

### 7. Streamlit 可视化仪表盘

启动后访问 `http://localhost:8501`，提供 7 个功能页面：

| 页面 | 功能 | Week |
|------|------|------|
| 🏠 系统概览 | 核心指标卡片、系统工作流程、站点列表、预警等级体系 | W1 |
| 📡 实时监测 | 5站点实时概览卡片、水位对比图、降雨量对比图、单站点详情仪表盘 | W1+W3 |
| 📊 数据分析 | 历史趋势图（API对接）、数据验证演示、批量处理工具 | W1+W3 |
| 🔮 预测分析 | LSTM-Attention 预测、24h水位柱状图、风险等级判定、API在线/离线切换 | W1+W3 |
| 🔥 注意力热力图 | **72h历史注意力权重分布 + 72×24热力图矩阵 + 预测关联分析** | W3 新增 |
| ⚠️ 预警管理 | **统计看板（按状态+等级双维度饼图）**、预警列表、创建预警、状态机操作 | W2+W3 |
| 🤖 模型管理 | 训练结果汇总、Loss对比图、模型架构配置 | W2 |

支持 **FastAPI 在线模式**（自动检测 `http://localhost:8000`）和**离线模拟模式**自动切换。

## 快速开始 Quick Start

### 安装依赖

```bash
pip install -r requirements.txt
```

### 训练模型

```bash
cd flood-prediction-system
python scripts/train_model.py
```

### 启动 API 服务

```bash
uvicorn src.web.app:app --reload
# Swagger UI: http://localhost:8000/docs
```

### 启动可视化仪表盘

```bash
streamlit run src/visualization/app.py --server.port 8501
```

### 运行端到端流程演示

```bash
python scripts/run_pipeline.py
```

### 运行测试

```bash
pytest tests/ -v
```

## 开发进度 Development Schedule

| 阶段 | 时间 | 内容 | 状态 |
|------|------|------|------|
| Week 1 | 5.14 - 5.20 | 架构设计 + 传感器模拟 + 数据校验 + LSTM-Attention 模型 + API 基础 | ✅ 已完成 |
| Week 2 | 5.21 - 5.27 | 数据预处理增强 + 时序存储优化 + API 增强 + 批量处理 + 模型训练脚本 + 数据库表补全 + 预警状态机 + Streamlit 仪表盘 | ✅ 已完成 |
| Week 3 | 5.25 - 5.31 | 注意力热力图 (72h×24h) + FastAPI+Streamlit 全接口对接 + 预警统计看板（双维度饼图）+ 5站点多面板对比图 | ✅ 已完成 |

## AI 辅助编程 AI-Assisted Programming

本项目遵循 AI 辅助编程标准流程，详见 [ai_plan/](ai_plan/)。

## License

课程项目，仅供教学使用。
