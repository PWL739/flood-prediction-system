# 第1周运行展示结果

## 1. 端到端流水线 (run_pipeline.py)

**命令:** `python scripts/run_pipeline.py`

[1/4] 数据采集演示
- 采集站数量: 5 (S001~S005)
- 每站3类传感器: 水位、降雨量、水质(pH/浊度/溶解氧)
- 数据已导出到 data/collected_data.json

[2/4] 数据验证与清洗演示
- 处理记录数: 16 | 有效: 15 | 异常: 1
- 异常检测：水位值999.99超出范围[0.0, 50.0]、降雨量999.99超出范围[0.0, 500.0]、时间戳超过7天

[3/4] LSTM-Attention 模型定义展示
- 模型结构: BiLSTM(7→128, 2层) + Attention + FC(512→128→24)
- 总参数量: 637,209
- 输入形状: [2, 72, 7] (72小时, 7维特征)
- 输出形状: [2, 24] (未来24小时水位预测)

[4/4] 预警演示
- 生成橙色预警(等级3): "钱塘江站未来24小时水位偏高"
- 多渠道发送: system_notification ✅ / app_push ✅ / sms ✅

## 2. 单元测试 (pytest tests/ -v)

**结果: 19 passed in 2.18s**

| 测试模块 | 测试用例 | 状态 |
|---------|---------|------|
| test_data_collection | 8 tests (传感器读取、数据采集、服务接口) | ✅ |
| test_data_processing | 7 tests (范围校验、逻辑校验、时间戳校验) | ✅ |
| test_prediction_model | 4 tests (模型创建、前向传播、Attention) | ✅ |

## 3. Web API / Swagger UI

**服务器:** `uvicorn src.web.app:app --host 127.0.0.1 --port 8000`
**Swagger UI:** http://127.0.0.1:8000/docs

### 可用端点测试结果

| 端点 | 方法 | 状态 | 说明 |
|------|------|------|------|
| /api/v1/stations | GET | ✅ 200 | 返回5个监测站点 |
| /api/v1/water-data/realtime | GET | ✅ 200 | 返回所有站点实时水文数据 |
| /api/v1/warnings/active | GET | ✅ 200 | 返回生效预警列表(当前为空) |
| /api/v1/prediction/flood-risk | GET | ⚠️ 500 | 需第2周模型训练完成后可用 |

### OpenAPI 文档截图替代
- 访问 `http://127.0.0.1:8000/docs` 可查看 Swagger UI 交互式文档
- 访问 `http://127.0.0.1:8000/redoc` 可查看 ReDoc 文档

## 4. 已知说明

- flood-risk 预测端点返回500是因为模型尚未训练（属于第2周任务）
- 当前使用模拟传感器数据，非真实水文数据
- 中文终端输出存在编码问题，但功能正常运行
