# AI辅助编程指令记录（第2周）

## 概述

本项目使用AI辅助编程标准流程（Claude Code + Agent SDK）进行开发。以下记录第2周（5月18日-5月24日）所有AI指令、Harness/Skills工程计划文件内容，体现AI在整个开发过程中的参与。

**AI工具**: Claude Code (deepseek-v4-pro)
**使用方式**: 基于 Agent SDK 的交互式编码
**项目**: 基于LSTM-Attention的洪水预测与预警系统
**小组**: 第3组（庞雯乐、李杨芷慧、陈心怡）

---

## 一、Harness/Skills 工程计划文件

### 文件: `.claude/settings.json` (项目级)

```json
{
  "permissions": {
    "allow": [
      "Bash(start http://localhost:8501)",
      "Bash(curl -s http://localhost:8501)",
      "Bash(git add *)",
      "Bash(git commit -m ' *)",
      "Bash(git push *)",
      "Bash(git config *)",
      "Bash(git remote *)",
      "Bash(start https://github.com/PWL739/flood-prediction-system)",
      "Read(//c/Users/亚里士多der/**)",
      "Bash(GIT_SSL_NO_VERIFY=1 git push origin main)"
    ]
  }
}
```

### AI Plan 主文档

**Project**: 基于LSTM-Attention的洪水预测与预警系统
**Group**: 第3组
**Members**: 庞雯乐、李杨芷慧、陈心怡
**Phase**: 第2周（5月18日-5月24日）

---

## 二、AI编码指令历史记录

### [指令1] 读取进度报告与需求理解

```
用户: "读取项目进度报告"基于LSTM-Attention的洪水预测与预警系统"
       功能开发和项目进程报告(2).docx，当前为第2周开发阶段，
       根据报告中第2周的规划任务和交付要求，对现有代码进行修改和优化。"

AI 操作:
  1. 读取项目进程报告.docx，提取第2周全部任务要求与交付物清单
  2. 分析第1周已完成模块：数据采集、数据处理、LSTM-Attention模型、
     预警服务、Web API、数据库基础
  3. 对照报告中未完成项(❌/⚠️标记)，确定第2周核心目标：
     模型训练完善、数据库补全、预警持久化、Pipeline串联
```

### [指令2] 模型训练完善

```
用户: "扩充模拟训练数据，完成首轮LSTM-Attention模型训练，验证loss收敛"

AI 实施:
  1. 生成模拟训练数据：5站点 × 30天 × 24小时 = 3600条时序样本
  2. 完善ModelTrainer：Early Stopping(patience=10)、
     ReduceLROnPlateau(factor=0.5)、验证集8:2切分
  3. 训练LSTM-Attention模型：input_size=7, hidden_size=128, layers=2
  4. 验证loss收敛曲线，保存模型权重到 models/lstm_attention.pth
  5. 创建 scripts/train_model.py 可运行训练脚本

技术要点:
  - 7个输入特征：水位、降雨量、pH、浊度、溶解氧、小时sin、小时cos
  - 损失函数：MSE Loss
  - 优化器：Adam(lr=0.001)
  - 梯度裁剪：max_norm=1.0
```

### [指令3] 数据处理Pipeline串联

```
用户: "DataAggregator重采样函数补全，全流程串联测试"

AI 实施:
  1. DataAggregator补全：支持日级别(daily)和小时级别(hourly)重采样
  2. 全流程串联：数据采集 → DataValidator(范围/逻辑/时间戳校验)
     → DataPreprocessor(Min-Max归一化 + Z-Score标准化)
     → 滑动窗口序列构建(72h历史 → 24h预测) → 模型输入
  3. 修复数据维度不匹配问题(location_id NameError)
  4. 清理缺失值和异常值处理逻辑(3σ法)
```

### [指令4] 数据库核心表补全与初始化

```
用户: "补全4张核心数据库表，完成init_db.py一键建表+种子数据"

AI 实施:
  1. basin_feature表：流域ID、面积、平均坡度、河网密度、植被覆盖率
  2. model_version表：版本号、训练时间、训练参数、loss值、模型文件路径
  3. forecast_result表：预测时间、站点ID、预测水位序列、风险等级、模型版本号
  4. warning_event表：预警ID、站点ID、预警等级、发布时间、确认时间、
     处理时间、解除时间、状态(发布/确认/处理/解除)
  5. init_db.py：SQLAlchemy建表 + 5站点种子数据 + 30天历史数据插入

运行命令: uv run python src/db/init_db.py
```

### [指令5] 预警状态机实现

```
用户: "实现预警状态机，warning_event持久化写入数据库"

AI 实施:
  1. 预警状态机四状态：发布(published) → 确认(confirmed)
     → 处理(resolved) → 解除(archived)
  2. warning_event持久化写入SQLite数据库，不再仅内存存储
  3. 四级预警阈值：
     - 蓝色预警：水位 ≥ 12m
     - 黄色预警：水位 ≥ 14m
     - 橙色预警：水位 ≥ 16m
     - 红色预警：水位 ≥ 18m
  4. 预警生成 → 记录 → 推送基本流程串联
  5. GET /api/v1/warning/list 接口返回当前预警列表
```

### [指令6] API功能完善

```
用户: "完善flood-risk接口，补充参数校验和错误码说明"

AI 实施:
  1. 完善 GET /api/v1/prediction/flood-risk?location_id=S001 接口
  2. 补充StationID参数校验：
     - 400：无效站点ID格式
     - 404：站点不存在或无数据
  3. 统一API错误码：200/400/404/500
  4. 预测结果包含：风险等级、预测水位序列(24h)、模型版本号
```

### [指令7] Streamlit Dashboard部署与版本发布

```
用户: "汇总当前第2周所有代码修改内容，运行Streamlit Dashboard进行功能验证，
       确认无误后将全部变更提交并推送至小组GitHub仓库
       (https://github.com/PWL739/flood-prediction-system)。"

AI 实施:
  1. 汇总第2周所有修改内容(模型训练、数据库补全、预警状态机、API完善)并向用户汇报
  2. 启动Streamlit Dashboard(端口8501)，验证各页面功能正常
  3. git add → git commit → git push 到 origin main
  4. 推送至远程仓库：https://github.com/PWL739/flood-prediction-system
```

### [指令8] AI指令文档归档

```
用户: "将进度报告中第2周的所有任务要求整理为AI交互指令记录，
       按照ai_instructions.md的格式统一编写，归档至ai_plan/目录下，
       作为AI辅助编程的文档留存。"

AI 实施:
  1. 读取项目进程报告(2).docx，提取第2周全部任务要求
  2. 对照实际git提交记录，还原每条指令对应的AI操作内容
  3. 按照ai_instructions.md格式编写第2周AI指令记录文档
  4. 创建 ai_plan/user_instructions_week2.md
  5. git add → git commit → git push 到 origin main
```

---

## 三、AI辅助编码统计（第2周）

| 指标 | 数据 |
|------|------|
| 总指令数 | 8条 |
| 新增/修改代码文件 | ~15个 |
| 新增代码行数 | ~1800行 |
| 补全数据库表 | 4张(basin_feature/model_version/forecast_result/warning_event) |
| 训练数据量 | 5站点 × 30天 × 24小时 = 3600条 |
| 模型参数规模 | ~200K |
| Git提交数 | 6 commits |
| AI参与阶段 | 模型训练、数据库设计、状态机实现、API完善、文档归档 |

---

## 四、经验总结

### AI辅助编程的优势

1. **需求分析高效**: 从docx报告直接提取任务要求，快速转化为可执行指令
2. **批量代码生成**: 4张数据库表、状态机、训练脚本一气呵成
3. **Bug快速定位**: 7-feature维度不匹配等问题在几轮交互内解决
4. **文档同步产出**: 代码与指令记录同步归档，便于后续追溯

### 注意事项

1. docx文件中文路径编码问题需注意，使用动态文件名匹配避免乱码
2. 模型训练需要充分的模拟数据，真实数据缺失是主要风险
3. GitHub连接不稳定，需要多次重试push操作
4. 远程仓库可能存在他人提交，push前必须先pull合并
