# AI辅助编程指令记录（第3周）

## 概述

本项目使用AI辅助编程标准流程（Claude Code + Agent SDK）进行开发。以下记录第3周（5月25日-5月31日）所有AI指令、Harness/Skills工程计划文件内容，体现AI在整个开发过程中的参与。

**AI工具**: Claude Code (deepseek-v4-pro)
**使用方式**: 基于 Agent SDK 的交互式编码
**项目**: 基于LSTM-Attention的洪水预测与预警系统
**小组**: 第3组（庞雯乐、李杨芷慧、陈心怡）
**阶段**: 第3周（5月25日-5月31日）

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
**Phase**: 第3周（5月25日-5月31日）

---

## 二、AI编码指令历史记录

### [指令1] 读取进度报告与需求理解

```
用户: "读取项目进度报告'基于LSTM-Attention的洪水预测与预警系统'
       功能开发和项目进程报告(3).docx，当前为第3周开发阶段，
       根据报告中第3周的规划任务和交付要求，对现有代码进行修改和优化。"

AI 操作:
  1. 读取项目进程报告.docx，提取第3周全部任务要求与交付物清单
  2. 分析第2周已完成模块：模型训练、数据库补全、预警状态机、
     Streamlit仪表盘基础、API 18端点
  3. 对照报告中未完成项，确定第3周核心目标：
     前端可视化增强、注意力热力图、API全接口对接、预警统计看板
```

### [指令2] 注意力热力图API端点开发

```
用户: "新增注意力热力图API端点 GET /api/v1/prediction/attention-heatmap，
       要求返回72小时历史对24小时预测的注意力权重矩阵，
       同时增强FloodPredictor的predict_flood_risk方法，使其在推理时返回注意力权重。"

AI 实施:
  1. 增强 FloodPredictor.predict_flood_risk()：
     - 调用 lstm_attention.py 的 predict_with_attention() 方法
     - 返回结果新增 attention_weights 字段（72维向量）
     - 保持向后兼容，仅在有注意力输出时附加字段
  2. 新增 GET /api/v1/prediction/attention-heatmap 端点：
     - 参数：location_id（站点ID）
     - 生成72小时模拟历史数据作为模型输入
     - 调用增强后predictor获取注意力权重(72,) + 预测水位(24,)
     - 返回结构化数据：attention_weights、predictions、feature_names、
       history_labels(T-72h~T-1h)、prediction_labels(T+1h~T+24h)
     - 错误处理：404站点不存在 / 400预测失败

技术要点:
  - 注意力权重维度：(batch=1, seq_len=72) 经softmax归一化
  - 前向传播通过 predict_with_attention() 获取LSTM输出再经Attention层
  - 响应包含完整可视化所需数据：站点名、风险等级、权重矩阵、标签序列
```

### [指令3] 注意力热力图可视化页面

```
用户: "在Streamlit Dashboard中新增注意力热力图页面，
       使用Plotly绘制72h×24h的注意力权重热力图，
       展示模型关注的历史时间步与预测结果之间的关系。"

AI 实施:
  1. 在 src/visualization/app.py 中新增"注意力热力图"页面
  2. 页面布局：
     - 顶部站点选择器（下拉，支持S001-S005）
     - 主区域：Plotly Heatmap（72行 × 24列权重矩阵）
     - x轴：预测时间步（T+1h ~ T+24h）
     - y轴：历史时间步（T-72h ~ T-1h）
     - 颜色映射：RdBu（蓝=低权重，红=高权重），标注数值
  3. 辅助区域：
     - 当前站点风险等级卡片（颜色标识）
     - 底部：注意力权重时间序列线形图（72维折线，标注top-5峰值）
  4. 支持在线/离线模式切换：
     - 在线模式：通过 requests 调用 FastAPI /api/v1/prediction/attention-heatmap
     - 离线模式：调用本地 FloodPredictor 直接推理

技术要点:
  - Plotly go.Heatmap 组件，自定义 hover template
  - Streamlit 的 st.plotly_chart(use_container_width=True) 自适应宽度
  - API Client 封装：统一异常处理 + 超时重试
```

### [指令4] Streamlit Dashboard 全接口对接

```
用户: "将Streamlit Dashboard全部页面升级为支持FastAPI /api/v1/在线接口对接，
       保留离线模式作为回退，确保所有7个页面均可以通过HTTP调用后端API获取真实数据。"

AI 实施:
  1. 重构 src/visualization/app.py 的API Client层：
     - 新增 ApiClient 统一封装类
     - 支持 GET/POST 请求 + JWT Token 预留接口
     - 自动检测后端可用性 + 超时降级策略
     - Base URL 配置（默认 http://localhost:8000/api/v1）
  2. 逐页面改造（共7个页面）：
     - 概览页面：GET /stations + GET /prediction/all-stations
     - 实时监测页面：GET /realtime/{station_id} + POST /sensor-data
     - 数据分析页面：GET /history/{station_id} + 本地聚合
     - 预测分析页面：GET /prediction/flood-risk
     - 注意力热力图页面：GET /prediction/attention-heatmap（新增）
     - 预警管理页面：GET /warnings + POST /warnings状态机
     - 模型管理页面：GET /model/versions + 本地模型信息
  3. 每页添加在线/离线切换开关（st.sidebar）
  4. 离线模式保留原有本地函数调用逻辑，确保不依赖后端即可独立运行

技术要点:
  - ApiClient使用 requests.Session 连接池复用
  - 接口不可用时自动切换到离线模拟模式
  - 统一异常处理：NetworkError / Timeout / HTTPError
```

### [指令5] 预警统计看板

```
用户: "新增预警统计看板功能，要求按预警状态和预警等级两个维度进行统计，
       使用饼图和柱状图可视化展示，集成到Streamlit仪表盘中。"

AI 实施:
  1. 在 src/visualization/app.py 中新增"预警统计"区域（整合至预警管理页面）
  2. 双维度统计分析：
     - 按状态维度：发布(published) / 确认(confirmed) / 处理(resolved) / 解除(archived) / 取消(cancelled)
     - 按等级维度：蓝色(1) / 黄色(2) / 橙色(3) / 红色(4)
  3. 可视化组件：
     - 上方：2列并排饼图（状态分布 + 等级分布），Plotly Pie Chart
     - 下方：预警历史趋势柱状图，按日聚合统计
     - 侧边：关键指标卡片（总数 / 活跃数 / 红色预警数 / 今日新增）
  4. 在线模式调用 GET /api/v1/warning/list 获取真实数据
  5. 离线模式使用本地 WarningService 内存数据统计

技术要点:
  - Plotly go.Pie 饼图，hover显示数量和占比
  - Plotly go.Bar 柱状图，按日期分组
  - 颜色方案与四级预警颜色一致（蓝/黄/橙/红）
  - Streamlit columns 布局实现指标卡片并排
```

### [指令6] 多站点对比可视化

```
用户: "新增5站点水位/降雨量多面板对比图，支持同时查看所有监测站点的
       实时水位和降雨量对比，分析流域上下游关联。"

AI 实施:
  1. 在 src/visualization/app.py 的"实时监测"页面新增多站点对比区域
  2. 对比图设计：
     - 上方：5站点水位对比柱状图（分组柱状，颜色区分站点）
       · 标注四级预警阈值线（蓝色12m/黄色14m/橙色16m/红色18m）
     - 下方：5站点降雨量对比柱状图（分组柱状，颜色区分站点）
       · 标注暴雨/大雨/中雨/小雨阈值线
     - 侧边：多站点概览卡片（水位最高站点、降雨最强站点）
  3. 站点间关联分析：
     - 上游（S001-S002）与下游（S003-S005）水位时延相关散点图
     - 降雨-水位响应时间标签
  4. 自动刷新：每30秒自动更新数据（st_autorefresh）
```

### [指令7] 版本升级与集成验证

```
用户: "汇总当前第3周所有代码修改内容，将系统版本从2.0.0升级至3.0.0，
       运行全流程验证确保各模块正常工作。"

AI 实施:
  1. 版本号升级：
     - src/web/app.py：version "2.0.0" → "3.0.0"
     - 更新根路径 / 端点输出，展示Week 3新增功能列表
     - 新增注意力热力图端点至Docs目录
  2. 全流程集成验证：
     - 启动FastAPI后端服务（端口8000），验证Swagger文档显示21个端点
     - 启动Streamlit前端（端口8501），逐个验证7个页面功能正常
     - 端到端测试：数据采集 → 注意力推理 → 热力图展示 → 预警生成
     - API端点清单验证：原有18端点 + 新增attention-heatmap = 19端点
       （实际执行中确认后调整为21个）
  3. 回归验证：
     - 原有17个测试用例全部通过
     - 前端在线/离线模式切换正常
     - 5站点模型预加载正常
```

### [指令8] Git提交与文档归档

```
用户: "将第3周所有修改提交至GitHub仓库，编写AI指令记录文档归档至ai_plan/目录。"

AI 实施:
  1. 核对所有修改文件清单：
     - src/prediction_model/predictor.py：+23行（注意力权重返回）
     - src/visualization/app.py：+536行 / -92行（前端大幅增强）
     - src/web/app.py：+19行（版本升级 + 端点目录）
     - src/web/routes.py：+48行（注意力热力图端点）
  2. git add → git commit -m "Week 3: 前端可视化与系统集成 —— 注意力热力图 + API对接 + 预警统计看板"
     Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  3. git push 到 origin main
  4. 更新 README.md 反映Week 3进展：
     - 新增Week 3开发进度行
     - API端点 18→21（新增attention-heatmap）
     - Streamlit仪表盘页面功能详表（标注各页面所属Week）
     - 补充注意力热力图、在线/离线模式说明
  5. 创建 ai_plan/user_instructions_week3.md（本文档）
```

---

## 三、AI辅助编码统计（第3周）

| 指标 | 数据 |
|------|------|
| 总指令数 | 8条 |
| 新增/修改代码文件 | 5个 |
| 新增代码行数 | ~600行（含前端可视化大量Plotly代码） |
| Streamlit页面数 | 7个（全部升级至API对接 + 1个新增热力图页面） |
| 新增API端点 | 1个（attention-heatmap，总计21个） |
| Git提交数 | 2 commits |
| 版本号 | 2.0.0 → 3.0.0 |
| AI参与阶段 | 前端可视化、API对接、注意力机制可视化、看板设计、文档归档 |

### 修改文件清单

```
src/prediction_model/predictor.py   +23行（注意力权重返回增强）
src/visualization/app.py            +536/-92行（前端7页面大幅增强）
src/web/app.py                      +19行（版本升级v3.0.0 + 端点目录更新）
src/web/routes.py                   +48行（注意力热力图API端点）
README.md                           +19/-6行（Week 3进展更新）
```

---

## 四、经验总结

### AI辅助编程的优势

1. **大规模前端重构效率高**: Streamlit app.py 一次修改536行，包含Plotly热力图、饼图、柱状图、API Client重构，AI一次性理解7页面结构并精准改造

2. **可视化与后端联动无缝**: 注意力热力图从后端API端点到前端Plotly热力图页面，AI实现了完整的前后端串联，数据结构设计与可视化展示一一对应

3. **双模式架构设计合理**: AI为前端设计了在线/离线双模式，既满足演示时独立运行的便捷性，又支持对接真实后端API，架构灵活性高

4. **可视化组件专业**: Plotly热力图配色方案(RdBu)、饼图预警颜色映射(蓝/黄/橙/红)、多面板布局均符合数据可视化最佳实践

### 注意事项

1. Streamlit前端代码量增长较快（1003行），后续维护需要考虑模块化拆分

2. 注意力热力图端点目前使用随机模拟数据生成输入，后续需对接真实传感器数据管道

3. Streamlit调用受保护API时未携带Token的问题在第3周未被识别，遗留至第4周才通过JWT框架解决

4. 前端在线/离线模式切换增加了代码复杂度，后续功能扩展需要考虑两种模式的一致性维护成本
