# 第2周AI操作指令（用户视角）

## 概述

本文档记录我在第2周（5月18日-5月24日）对AI（Claude Code）下达的开发指令。项目为"基于LSTM-Attention的洪水预测与预警系统"，课程：智慧水利应用，小组：第3组（庞雯乐、李杨芷慧、陈心怡）。

AI工具：Claude Code (deepseek-v4-pro)
仓库地址：https://github.com/PWL739/flood-prediction-system

---

## 指令列表

### [指令1] 读取进度报告，按照第2周要求修改代码

**日期**: 2026年5月23日

我让AI先读两份文档：`第三组_洪水预测与预警系统_功能开发和项目进度报告.docx` 和 `"基于LSTM-Attention的洪水预测与预警系统"功能开发和项目进程报告(2).docx`，理解第1周已完成的工作和第2周的要求。

具体指令：
- "第三组_洪水预测与预警系统_功能开发和项目进度报告.docx，你读这个进度报告，现在是第二周，按照我们的要求，修改代码"
- "flood-prediction-system\"基于LSTM-Attention的洪水预测与预警系统"功能开发和项目进程报告(2).docx，搞错了，要读的是这个报告，你再根据这个报告里的第二周要求修改优化代码"

---

### [指令2] 模型训练完善

**来源**: 报告 第2周 任务1 + 六-2-任务1

我要求AI：
1. 扩充模拟训练数据（5站点×30天×24小时），生成足够的训练样本
2. 完善ModelTrainer，支持Early Stopping、学习率调度（ReduceLROnPlateau）、验证集评估
3. 完成首轮LSTM-Attention模型训练，验证loss收敛
4. 生成首批模型权重文件（.pth或.h5），保存到models/目录
5. 交付物：可运行训练脚本 `scripts/train_model.py`
   - 运行命令：`uv run python scripts/train_model.py`

---

### [指令3] 数据处理Pipeline串联

**来源**: 报告 第2周 任务4 + 六-2-任务2

我要求AI：
1. DataAggregator重采样函数补全（独立函数，支持日/小时级别重采样）
2. 全流程串联测试：数据采集 → DataValidator → DataPreprocessor → 序列构建 → 模型输入
3. 确保7个特征（feature）完整输入模型
4. 修复数据流中可能出现的维度不匹配问题
5. 清理缺失值和异常值处理逻辑

---

### [指令4] 数据库核心表补全与初始化

**来源**: 报告 第2周 任务2 + 六-2-任务4

我要求AI：
1. 补全4张核心数据库表：
   - `basin_feature`（流域特征）：流域ID、面积、平均坡度、河网密度、植被覆盖率等
   - `model_version`（模型版本）：版本号、训练时间、训练参数、loss值、模型文件路径
   - `forecast_result`（预测结果）：预测时间、站点ID、预测水位序列、风险等级、模型版本号
   - `warning_event`（预警事件）：预警ID、站点ID、预警等级、发布时间、确认时间、处理时间、解除时间、状态
2. 完成 `src/db/init_db.py`，支持一键建表 + 种子数据插入（5个站点、30天历史数据）
   - 运行命令：`uv run python src/db/init_db.py`

---

### [指令5] 预警状态机实现

**来源**: 报告 第2周 任务3 + 六-2-任务3

我要求AI：
1. 实现预警状态机：发布 → 确认 → 处理 → 解除，共4个状态
2. warning_event持久化写入数据库（不再仅内存存储）
3. 四级预警阈值配置（已在settings.py）：
   - 蓝色预警：水位 ≥ 12m
   - 黄色预警：水位 ≥ 14m
   - 橙色预警：水位 ≥ 16m
   - 红色预警：水位 ≥ 18m
4. 预警生成 → 记录 → 推送基本流程串联
5. 交付物：`GET /api/v1/warning/list`（返回当前预警列表）

---

### [指令6] API功能完善

**来源**: 报告 第2周 任务3交付 + 六-2-任务5

我要求AI：
1. 完善 `GET /api/v1/prediction/flood-risk?location_id=S001` 接口
2. 补充StationID参数校验（错误码：400无效站点、404无数据）
3. 统一API错误码说明（200/400/404/500）
4. 预测结果中包含风险等级、预测水位序列、模型版本号

---

### [指令7] 运行系统并上传GitHub

**日期**: 2026年5月23日

我要求AI：
1. "现在相比之前有什么修改？我要怎么把他上传到我们小组的github仓库里？"
2. "完成好直接给我运行界面，我确认一下，确认完成再传到我的仓库"
3. 运行Streamlit Dashboard（端口8501）
4. git add → git commit → git push 到 origin main（仓库：PWL739/flood-prediction-system）

---

## AI执行结果总结

AI在第2周完成了以下工作（对应git commits）：

| Commit | 内容 |
|--------|------|
| `733da63` | Fix: 7-feature model input for LSTM-Attention (input_size=7) |
| `7d41fc6` | Fix: resolve location_id NameError and ensure 7-feature model input |
| `7691c6c` | Week 2: 数据预处理增强 + 时序存储优化 + API增强 |
| `cf6563e` | Week 2 完整实现: 核心数据表补全 + 预警状态机 + 训练脚本 + Streamlit仪表盘 |
| `7598da1` | docs: update README to reflect current project state (Week 2 completion) |

---

## 备注

- 本文档与 `ai_instructions.md`（AI操作视角）互为补充，本文档是我的指令输入视角
- 后续周次（第3周、第4周）的指令将继续追加到本文件
