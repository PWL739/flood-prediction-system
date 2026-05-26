"""LSTM-Attention 模型训练脚本 —— 生成5站点×30天×24小时模拟数据并完成首轮训练"""

import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import MODEL_CONFIG, MONITOR_STATIONS
from src.data_collection.sensor_simulator import WaterLevelSensor, RainfallSensor
from src.data_processing.data_preprocessor import DataPreprocessor
from src.prediction_model.lstm_attention import LSTMAttentionModel
from src.prediction_model.trainer import ModelTrainer


def generate_training_data(days: int = 30) -> pd.DataFrame:
    """生成5站点×30天×24小时的模拟训练数据"""
    print(f"生成训练数据: {len(MONITOR_STATIONS)}站点 × {days}天 × 24小时")
    all_records = []

    for station in MONITOR_STATIONS:
        sid = station["id"]
        wl_sensor = WaterLevelSensor(sid, base_level=np.random.uniform(8, 15))
        rf_sensor = RainfallSensor(sid)

        for day in range(days):
            for hour in range(24):
                ts = datetime.now() - timedelta(days=days - day, hours=24 - hour)
                wl_reading = wl_sensor.read_data()
                rf_reading = rf_sensor.read_data()

                record = {
                    "location_id": sid,
                    "timestamp": ts.isoformat(),
                    "water_level": wl_reading["value"],
                    "flow_rate": np.random.uniform(100, 500),
                    "rainfall": rf_reading["value"],
                    "temperature": np.random.uniform(15, 35),
                    "ph": np.random.uniform(6.5, 7.5),
                    "turbidity": np.random.uniform(10, 20),
                    "dissolved_oxygen": np.random.uniform(6, 10),
                }
                all_records.append(record)

    df = pd.DataFrame(all_records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["location_id", "timestamp"]).reset_index(drop=True)

    total = len(df)
    print(f"生成数据总量: {total} 条")
    print(f"  站点数: {df['location_id'].nunique()}")
    print(f"  时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    return df


def train_per_station(df: pd.DataFrame, station_id: str):
    """针对单个站点训练模型"""
    station_df = df[df["location_id"] == station_id].copy()
    print(f"\n{'='*50}")
    print(f"训练站点: {station_id} ({len(station_df)}条数据)")
    print(f"{'='*50}")

    preprocessor = DataPreprocessor()
    station_df = preprocessor.handle_missing_values(station_df)

    # 使用MODEL_CONFIG指定的7个特征
    feature_cols = [
        "water_level", "flow_rate", "rainfall", "temperature",
        "ph", "turbidity", "dissolved_oxygen",
    ]
    target_col = "water_level"

    try:
        X, y = preprocessor.create_sliding_windows(station_df, feature_cols, target_col)
    except ValueError as e:
        print(f"  数据量不足，跳过: {e}")
        return None

    print(f"  训练样本: {X.shape}, 标签: {y.shape}")

    # 划分训练/验证集
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    # 构建模型
    model = LSTMAttentionModel()

    # 训练
    trainer = ModelTrainer(model)
    trainer.fit(
        X_train, y_train,
        X_val, y_val,
        batch_size=16,
        num_epochs=30,
    )

    # 保存模型
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    model_path = model_dir / f"lstm_attention_{station_id}.pt"
    trainer.save_model(str(model_path))

    return {
        "station_id": station_id,
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "final_train_loss": trainer.train_losses[-1] if trainer.train_losses else None,
        "final_val_loss": trainer.val_losses[-1] if trainer.val_losses else None,
        "model_path": str(model_path),
    }


def main():
    print("\n")
    print("=" * 60)
    print("  LSTM-Attention 洪水预测模型训练")
    print("  第2周: 模型训练完善")
    print("=" * 60)
    print()

    # Step 1: 生成训练数据
    df = generate_training_data(days=30)
    data_path = Path("data/training_data.csv")
    data_path.parent.mkdir(exist_ok=True)
    df.to_csv(data_path, index=False)
    print(f"\n训练数据已保存: {data_path}")
    print(f"  文件大小: {data_path.stat().st_size / 1024:.1f} KB")

    # Step 2: 全局数据预处理
    print(f"\n{'='*50}")
    print("全局数据预处理")
    print(f"{'='*50}")
    preprocessor = DataPreprocessor()
    df = preprocessor.handle_missing_values(df)

    # 统计
    stats = df.groupby("location_id").agg(
        record_count=("water_level", "count"),
        avg_water_level=("water_level", "mean"),
        max_water_level=("water_level", "max"),
        total_rainfall=("rainfall", "sum"),
    )
    print("\n各站点数据统计:")
    for sid, row in stats.iterrows():
        print(
            f"  {sid}: {int(row['record_count']):4d}条 | "
            f"平均水位={row['avg_water_level']:.2f}m | "
            f"最高水位={row['max_water_level']:.2f}m | "
            f"累计降雨={row['total_rainfall']:.1f}mm"
        )

    # Step 3: 逐站点训练
    print(f"\n{'='*50}")
    print("逐站点模型训练")
    print(f"{'='*50}")

    results = []
    for station in MONITOR_STATIONS:
        result = train_per_station(df, station["id"])
        if result:
            results.append(result)

    # Step 4: 汇总
    print(f"\n{'='*60}")
    print("训练完成！结果汇总")
    print(f"{'='*60}")
    success = 0
    for r in results:
        status = "OK" if r["final_train_loss"] is not None else "FAIL"
        print(f"  {r['station_id']}: {status} | "
              f"TrainLoss={r['final_train_loss']:.6f} | "
              f"ValLoss={r['final_val_loss']:.6f} | "
              f"模型: {r['model_path']}")
        if r["final_train_loss"] is not None:
            success += 1

    print(f"\n成功训练: {success}/{len(results)} 个站点模型")

    # 保存训练结果摘要
    summary_path = Path("models/training_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"训练摘要已保存: {summary_path}")

    print("\n可运行: uv run python3 scripts/train_model.py")
    return results


if __name__ == "__main__":
    main()
