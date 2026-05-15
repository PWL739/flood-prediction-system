# AI辅助编程指令记录

## 概述

本项目使用AI辅助编程标准流程（Claude Code + Agent SDK）进行开发。以下记录所有AI指令、Harness/Skills工程计划文件内容，体现AI在整个开发过程中的参与。

**AI工具**: Claude Code (deepseek-v4-flash)
**使用方式**: 基于 Agent SDK 的交互式编码

---

## 一、Harness/Skills 工程计划文件

### 文件: `.claude/settings.json` (项目级)

```json
{
  "permissions": {
    "allow": ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
  }
}
```

### AI Plan 主文档

**Project**: 基于LSTM-Attention的洪水预测与预警系统
**Group**: 第3组
**Members**: 庞雯乐、李杨芷慧、陈心怡

---

## 二、AI编码指令历史记录

### [指令1] 项目初始化与需求理解

```
用户: "我需要搭建一个基于LSTM-Attention的洪水预测与预警系统，
       请先读取D盘智慧水利应用目录下的需求报告和详细设计文档，
       理解项目需求后再动手。"
AI 操作:
  1. 读取两份参考文档.docx，提取项目需求
  2. 分析得：系统需要数据采集、数据处理、LSTM-Attention预测、预警服务四大模块
  3. 设计项目目录结构
```

### [指令2] 项目目录结构创建

```
用户: "创建洪水预测系统的完整项目目录结构，要求模块化分层设计。"

AI 规划输出 (Plan):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
          洪水预测与预警系统 - 实施计划
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

架构概览:
  数据采集 → 数据处理 → LSTM-Attention预测 → 预警服务 → Web API

模块划分:
  ├── src/config/         系统配置（数据库、模型参数）
  ├── src/data_collection/ 数据采集模块
  ├── src/data_processing/ 数据处理模块
  ├── src/prediction_model/ 预测模型模块
  ├── src/db/             数据库模型
  ├── src/web/            Web API层
  ├── tests/              单元测试
  ├── docs/               文档
  └── ai_plan/            AI辅助编程记录

第1周交付内容:
  - 项目框架与配置
  - 传感器模拟器与数据采集
  - 数据验证与预处理
  - 数据库ORM模型
  - LSTM-Attention模型原型
  - 预警服务
  - RESTful API
  - 流水线演示脚本

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### [指令3] 数据采集模块实现

```
用户: "实现数据采集模块，包括传感器模拟器和数据采集服务。
       需要模拟水位、降雨量、水质三类传感器，覆盖5个监测站点。"

AI 实施:
  1. 创建 WaterLevelSensor 类：基于正弦波的日周期水位模拟
  2. 创建 RainfallSensor 类：降雨事件概率触发模拟
  3. 创建 WaterQualitySensor 类：pH/浊度/溶解氧模拟
  4. 创建 SensorDataCollector 类：管理所有站点传感器
  5. 创建 DataCollectionService 类：高层接口+JSON导出

技术要点:
  - 水位模拟：base_level + diurnal_variation(正弦) + gauss_noise + trend
  - 降雨模拟：马尔可夫过程(下雨/停雨状态转换)
  - 站点配置：5个站点(钱塘江上下游、新安江、富春江)
```

### [指令4] 数据处理模块实现

```
用户: "实现数据验证和预处理模块，要求包含范围校验、
       逻辑校验、时间戳校验，以及数据归一化、序列化功能。"

AI 实施:
  1. DataValidator: 范围校验(基于传感器配置)、逻辑校验(水位-降雨一致性)
  2. DataPreprocessor: Min-Max归一化、Z-score标准化、时间序列窗口化
  3. 支持批量验证和异常值检测(3-sigma法)
```

### [指令5] LSTM-Attention模型实现

```
用户: "按照详细设计文档的要求，实现LSTM-Attention模型。
       输入过去72小时数据，预测未来24小时水位。"

AI 实施:
  1. AttentionLayer: 基于加性注意力(additive attention)
  2. LSTMAttentionModel: BiLSTM + Attention + 全连接输出
  3. 模型参数：input_size=7, hidden_size=128, layers=2
  4. ModelTrainer: 训练循环、早停、学习率调度
  5. FloodPredictor: 预测服务、风险等级评估

算法原理:
  - 输入 -> BiLSTM(提取时序特征) -> Attention(聚焦关键时间步)
    -> ContextVector -> FC(映射到24h) -> 输出
```

### [指令6] 预警服务实现

```
用户: "实现预警服务模块，支持四级预警的生成、发送和管理。"

AI 实施:
  1. WarningService: 预警创建(蓝/黄/橙/红)
  2. 多渠道发送模拟(system/app/sms)
  3. 基于预测结果的自动预警触发
  4. 预警有效期与取消管理
```

### [指令7] Web API实现

```
用户: "基于FastAPI实现RESTful API，暴露所有核心功能。"

AI 实施:
  1. FastAPI应用 + Swagger文档
  2. 6个API接口对应数据采集、预测、预警功能
  3. 统一错误处理、数据格式
```

### [指令8] 单元测试编写

```
用户: "为核心模块编写单元测试，要求覆盖数据采集、数据处理和模型。"

AI 实施:
  1. test_data_collection.py: 7个测试用例
  2. test_data_processing.py: 6个测试用例
  3. test_prediction_model.py: 4个测试用例
```

### [指令9] 文档与报告

```
用户: "编写项目进度报告、AI辅助编程记录和README文档。"

AI 实施:
  1. docs/assignment_report.md: 完整项目进度报告
  2. ai_plan/ai_instructions.md: 本AI指令记录文件
  3. README.md: 项目说明文档
```

---

## 三、AI辅助编码统计

| 指标 | 数据 |
|------|------|
| 总指令数 | 9条 |
| 生成代码文件 | 20个 |
| 生成代码行数 | ~2000行 |
| 测试用例数 | 17个 |
| 处理参考文档 | 2份(.docx) |
| AI参与阶段 | 架构设计、编码实现、测试、文档 |

---

## 四、经验总结

### AI辅助编程的优势

1. **快速原型**: 从需求理解到代码生成仅需数轮交互
2. **规范一致性**: 自动保持代码风格、命名规范统一
3. **文档同步生成**: 代码与文档同步产出，避免脱节
4. **架构指导**: AI提供多种架构方案供选择

### 注意事项

1. AI生成的代码需要人工复核合理性
2. 复杂的业务逻辑仍需人工把控
3. 安全性和异常处理需要人工补充
4. AI对中文编码兼容性存在局限，需注意文件路径编码
