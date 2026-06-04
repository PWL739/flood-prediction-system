"""数据处理流水线主脚本 —— 展示Week 2开发成果的端到端运行"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_collection.data_collector import DataCollectionService
from src.data_processing.data_validator import DataValidator, OutlierDetector
from src.data_processing.data_preprocessor import DataPreprocessor
from src.data_processing.batch_processor import BatchDataProcessor
from src.prediction_model.lstm_attention import build_model
from src.prediction_model.warning_service import WarningService


def run_data_collection_demo():
    """[Week 1] 数据采集演示"""
    print("=" * 60)
    print("[1/5] 水文数据采集演示")
    print("=" * 60)

    collector = DataCollectionService()
    raw_data = collector.collect_realtime_data()

    print(f"\n采集站点数: {len(raw_data)}")
    for station_data in raw_data:
        sid = station_data["station_id"]
        readings = station_data["readings"]
        print(f"  站点 {sid}: {len(readings)} 个传感器读数")
        for r in readings:
            if "value" in r:
                print(f"    - {r['data_type']}: {r['value']} {r.get('unit', '')}")
            elif "parameters" in r:
                params = r["parameters"]
                print(f"    - 水质: pH={params['ph']}, 浊度={params['turbidity']}")

    output_path = Path("data/collected_data.json")
    output_path.parent.mkdir(exist_ok=True)
    collector.export_to_json(raw_data, str(output_path))
    print(f"\n数据已导出至: {output_path}\n")
    return raw_data


def run_data_validation_demo(raw_data):
    """[Week 2] 数据验证增强：3σ异常检测"""
    print("=" * 60)
    print("[2/5] 数据验证与3σ异常值检测演示 (Week 2 新增)")
    print("=" * 60)

    validator = DataValidator()
    formatted_data = DataCollectionService().format_data_for_storage(raw_data)

    # 构造异常数据用于演示3σ检测
    from datetime import datetime as dt
    test_data = formatted_data + [
        {"location_id": "S001", "timestamp": dt.now(), "water_level": 999.99, "rainfall": 999.99},
        {"location_id": "S002", "timestamp": dt.now(), "water_level": 12.0, "rainfall": 5.0},
        {"location_id": "S003", "timestamp": dt.now(), "water_level": 11.5, "rainfall": 3.0},
        {"location_id": "S004", "timestamp": dt.now(), "water_level": 13.0, "rainfall": 8.0},
    ]

    # Week 2新增: 批量验证 + 3σ检测
    results = validator.batch_validate_with_3sigma(test_data)
    valid_data = validator.filter_valid_data(results)

    total = len(results)
    valid_count = len(valid_data)
    print(f"\n总数据条数: {total}")
    print(f"有效数据: {valid_count}")
    print(f"异常数据 (含3σ检测): {total - valid_count}")

    for r in results:
        if not r["is_valid"]:
            print(f"\n  异常记录 (质量评分: {r['quality_score']:.2f}):")
            for issue in r["issues"]:
                print(f"    - {issue}")

    print()
    return valid_data


def run_batch_processor_demo(raw_data):
    """[Week 2] 批量数据处理演示"""
    print("=" * 60)
    print("[3/5] 批量数据处理工具演示 (Week 2 新增)")
    print("=" * 60)

    processor = BatchDataProcessor()

    # 从采集数据构造多条历史记录用于演示
    formatted = DataCollectionService().format_data_for_storage(raw_data)

    # 模拟生成多时段数据
    from datetime import datetime as dt, timedelta
    historical_records = []
    for i in range(80):
        for record in formatted[:3]:
            r = record.copy()
            r["timestamp"] = dt.now() - timedelta(hours=80 - i)
            r["water_level"] = r.get("water_level", 10) or 10
            r["water_level"] += (i - 40) * 0.05  # 趋势
            historical_records.append(r)

    result = processor.process_pipeline(historical_records)

    print(f"\n处理状态: {result['status']}")
    if result['status'] == 'success':
        print(f"清洗前: {result['clean_summary']['initial_count']} 条")
        print(f"清洗后: {result['clean_summary']['valid_count']} 条")
        print(f"特征数: {result['feature_count']} 个")
        print(f"训练样本数: {result['dataset_samples']} 个")
        print(f"数据集形状: {result['dataset_shape']}")
    else:
        print(f"消息: {result.get('message')}")

    print()
    return result


def run_model_demo():
    """[Week 1] 模型定义演示"""
    print("=" * 60)
    print("[4/5] LSTM-Attention 模型定义演示")
    print("=" * 60)

    model = build_model()
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n总参数量: {total_params:,}")
    print(f"可训练参数量: {trainable_params:,}")

    import torch
    batch_size, seq_len, features = 2, 72, 7
    dummy_input = torch.randn(batch_size, seq_len, features)
    output = model(dummy_input)
    print(f"输入形状: {dummy_input.shape}")
    print(f"输出形状: {output.shape} (未来24小时水位预测)\n")


def run_warning_demo():
    """[Week 1] 预警服务演示"""
    print("=" * 60)
    print("[5/5] 预警服务演示")
    print("=" * 60)

    service = WarningService()

    prediction_result = {
        "station_name": "钱塘江中游站",
        "location_id": "S002",
        "max_predicted_water_level": 22.5,
        "risk_level": 3,
        "risk_name": "橙色预警",
    }

    warning = service.generate_flood_warning(prediction_result)
    if warning:
        print(f"\n生成预警: {warning['title']}")
        print(f"预警级别: {warning['warning_level']}")
        print(f"预警内容: {warning['content']}")

        result = service.send_warning(warning)
        print(f"\n发送结果:")
        for sr in result["sent_results"]:
            status = "OK" if sr["success"] else "FAIL"
            print(f"  - {sr['channel']}: {status}")

    print()


def main():
    """主函数：运行完整流水线"""
    print("\n")
    print("╔══════════════════════════════════════════════════╗")
    print("║    基于LSTM-Attention的洪水预测与预警系统       ║")
    print("║         Week 2 开发成果演示                      ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    raw_data = run_data_collection_demo()
    run_data_validation_demo(raw_data)
    run_batch_processor_demo(raw_data)
    run_model_demo()
    run_warning_demo()

    print("=" * 60)
    print("Week 2 开发成果总结")
    print("=" * 60)
    print("\n  Week 1 成果 (保留):")
    print("    [OK] 传感器模拟器 (水位、降雨、水质)")
    print("    [OK] 数据采集服务 (5站点)")
    print("    [OK] LSTM-Attention 模型定义")
    print("    [OK] 预警服务 (生成、多渠发送)")
    print("    [OK] RESTful API (FastAPI)")
    print("    [OK] 数据库 ORM 模型")
    print()
    print("  Week 2 新增成果:")
    print("    [OK] 3σ异常值检测 + IQR检测")
    print("    [OK] 批量数据处理工具 (清洗+特征工程+数据集构建)")
    print("    [OK] 数据分层存储模型 (raw/cleaned/feature)")
    print("    [OK] TimescaleDB 超表配置与压缩策略")
    print("    [OK] 数据入库服务 (实时+批量)")
    print("    [OK] Pydantic 请求/响应验证模型")
    print("    [OK] 历史数据查询与导出 (JSON/CSV)")
    print("    [OK] 增强API端点 (15+ 端点)")
    print("    [OK] 统一响应格式与异常处理")
    print()
    print("  启动API: uvicorn src.web.app:app --reload")
    print("  Swagger文档: http://localhost:8000/docs")
    print()


if __name__ == "__main__":
    main()
