"""数据处理流水线主脚本 —— 展示第1周开发成果的端到端运行"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_collection.data_collector import DataCollectionService
from src.data_processing.data_validator import DataValidator
from src.data_processing.data_preprocessor import DataPreprocessor
from src.prediction_model.lstm_attention import build_model
from src.prediction_model.warning_service import WarningService


def run_data_collection_demo():
    """数据采集演示"""
    print("=" * 60)
    print("[1/4] 水文数据采集演示")
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

    # 导出数据
    output_path = Path("data/collected_data.json")
    output_path.parent.mkdir(exist_ok=True)
    collector.export_to_json(raw_data, str(output_path))
    print(f"\n数据已导出至: {output_path}\n")
    return raw_data


def run_data_validation_demo(raw_data):
    """数据验证演示"""
    print("=" * 60)
    print("[2/4] 数据验证与清洗演示")
    print("=" * 60)

    validator = DataValidator()
    formatted_data = DataCollectionService().format_data_for_storage(raw_data)

    # 构造一条异常数据用于演示
    from datetime import datetime as dt
    test_data = formatted_data + [{
        "location_id": "S001",
        "timestamp": dt(2024, 1, 1),
        "water_level": 999.99,
        "rainfall": 999.99,
    }]

    results = validator.batch_validate(test_data)
    valid_data = validator.filter_valid_data(results)

    total = len(results)
    valid_count = len(valid_data)
    print(f"\n总数据条数: {total}")
    print(f"有效数据: {valid_count}")
    print(f"异常数据: {total - valid_count}")

    for r in results:
        if not r["is_valid"]:
            print(f"\n  异常记录 (质量评分: {r['quality_score']:.2f}):")
            for issue in r["issues"]:
                print(f"    - {issue}")

    print()
    return valid_data


def run_model_demo():
    """模型定义演示"""
    print("=" * 60)
    print("[3/4] LSTM-Attention 模型定义演示")
    print("=" * 60)

    model = build_model()
    print(f"\n模型结构:")
    print(model)

    # 统计参数量
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n总参数量: {total_params:,}")
    print(f"可训练参数量: {trainable_params:,}")

    # 前向传播测试
    import torch
    batch_size, seq_len, features = 2, 72, 7
    dummy_input = torch.randn(batch_size, seq_len, features)
    output = model(dummy_input)
    print(f"输入形状: {dummy_input.shape}")
    print(f"输出形状: {output.shape} (未来24小时水位预测)\n")


def run_warning_demo():
    """预警服务演示"""
    print("=" * 60)
    print("[4/4] 预警服务演示")
    print("=" * 60)

    service = WarningService()

    # 模拟预测结果
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

        # 发送预警
        result = service.send_warning(warning)
        print(f"\n发送结果:")
        for sr in result["sent_results"]:
            status = "OK" if sr["success"] else "FAIL"
            print(f"  - {sr['channel']}: {status}")

    print()
    return warning


def main():
    """主函数：运行完整流水线"""
    print("\n")
    print("╔══════════════════════════════════════════════════╗")
    print("║    基于LSTM-Attention的洪水预测与预警系统       ║")
    print("║         第1周开发成果演示                        ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    raw_data = run_data_collection_demo()
    run_data_validation_demo(raw_data)
    run_model_demo()
    run_warning_demo()

    print("=" * 60)
    print("演示完成！")
    print("=" * 60)
    print("\n第1周开发成果总结:")
    print("  [OK] 传感器模拟器 (水位、降雨、水质)")
    print("  [OK] 数据采集服务")
    print("  [OK] 数据验证与清洗 (范围校验、逻辑校验)")
    print("  [OK] 数据预处理 (归一化、序列化)")
    print("  [OK] LSTM-Attention 模型定义")
    print("  [OK] 预警服务 (生成、发送)")
    print("  [OK] RESTful API (FastAPI)")
    print("  [OK] 数据库模型定义 (8张表)")


if __name__ == "__main__":
    main()
