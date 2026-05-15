"""项目配置文件"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 数据配置
DATA_DIR = BASE_DIR / "data"

# 传感器配置
SENSOR_CONFIG = {
    "water_level": {"min": 0.0, "max": 50.0, "unit": "m"},
    "flow_rate": {"min": 0.0, "max": 5000.0, "unit": "m³/s"},
    "rainfall": {"min": 0.0, "max": 500.0, "unit": "mm"},
    "temperature": {"min": -10.0, "max": 45.0, "unit": "°C"},
    "ph": {"min": 0.0, "max": 14.0, "unit": ""},
    "turbidity": {"min": 0.0, "max": 1000.0, "unit": "NTU"},
    "dissolved_oxygen": {"min": 0.0, "max": 20.0, "unit": "mg/L"},
}

# 采样间隔（分钟）
SAMPLING_INTERVAL = 60

# 预警等级阈值
WARNING_THRESHOLDS = {
    "level_1": {"name": "蓝色预警", "water_level": 15.0},
    "level_2": {"name": "黄色预警", "water_level": 20.0},
    "level_3": {"name": "橙色预警", "water_level": 25.0},
    "level_4": {"name": "红色预警", "water_level": 30.0},
}

# 监测站点配置
MONITOR_STATIONS = [
    {"id": "S001", "name": "钱塘江上游站", "lat": 30.05, "lng": 120.10},
    {"id": "S002", "name": "钱塘江中游站", "lat": 30.15, "lng": 120.30},
    {"id": "S003", "name": "钱塘江下游站", "lat": 30.25, "lng": 120.50},
    {"id": "S004", "name": "新安江水库站", "lat": 29.50, "lng": 119.20},
    {"id": "S005", "name": "富春江站", "lat": 30.05, "lng": 119.95},
]

# 数据库配置
DATABASE_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "flood_prediction"),
}

# Redis配置
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": int(os.getenv("REDIS_DB", "0")),
    "password": os.getenv("REDIS_PASSWORD", ""),
}

# 模型配置
MODEL_CONFIG = {
    "input_size": 7,           # 输入特征维度
    "hidden_size": 128,        # LSTM隐藏层大小
    "num_layers": 2,           # LSTM层数
    "output_size": 24,         # 预测未来24小时
    "seq_length": 72,          # 使用过去72小时数据
    "dropout": 0.2,
    "learning_rate": 0.001,
    "batch_size": 32,
    "num_epochs": 100,
    "attention_size": 64,      # Attention层大小
}

# API配置
API_CONFIG = {
    "host": os.getenv("API_HOST", "0.0.0.0"),
    "port": int(os.getenv("API_PORT", "8000")),
    "debug": os.getenv("API_DEBUG", "True").lower() == "true",
}
