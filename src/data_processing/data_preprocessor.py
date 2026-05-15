"""数据预处理模块 —— 数据聚合、重采样、特征工程"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from src.config.settings import MODEL_CONFIG


class DataPreprocessor:
    """数据预处理器 —— 将原始数据转换为模型可用的特征"""

    @staticmethod
    def normalize_data(data: np.ndarray) -> np.ndarray:
        """数据归一化（Min-Max）"""
        min_val = data.min(axis=0, keepdims=True)
        max_val = data.max(axis=0, keepdims=True)
        # 防止除零
        range_val = max_val - min_val
        range_val[range_val == 0] = 1
        return (data - min_val) / range_val

    @staticmethod
    def standardize_data(data: np.ndarray) -> np.ndarray:
        """数据标准化（Z-score）"""
        mean = data.mean(axis=0, keepdims=True)
        std = data.std(axis=0, keepdims=True)
        std[std == 0] = 1
        return (data - mean) / std

    def create_sequences(
        self, data: np.ndarray, seq_length: Optional[int] = None
    ) -> np.ndarray:
        """创建时间序列样本"""
        if seq_length is None:
            seq_length = MODEL_CONFIG["seq_length"]

        sequences = []
        for i in range(len(data) - seq_length):
            sequences.append(data[i : i + seq_length])
        return np.array(sequences)

    def prepare_training_data(
        self, df: pd.DataFrame, target_col: str = "water_level"
    ) -> tuple:
        """准备训练数据：生成特征矩阵和标签"""
        seq_length = MODEL_CONFIG["seq_length"]

        feature_cols = [c for c in df.columns if c != target_col and c != "timestamp"]
        features = df[feature_cols].values
        targets = df[target_col].values

        # 归一化
        features_normalized = self.standardize_data(features)
        targets_normalized = self.standardize_data(targets.reshape(-1, 1)).flatten()

        # 创建序列
        X, y = [], []
        for i in range(len(features_normalized) - seq_length):
            X.append(features_normalized[i : i + seq_length])
            y.append(targets_normalized[i + seq_length])

        return np.array(X), np.array(y)

    @staticmethod
    def handle_missing_values(
        df: pd.DataFrame, method: str = "interpolate"
    ) -> pd.DataFrame:
        """处理缺失值"""
        if method == "interpolate":
            return df.interpolate(method="linear", limit_direction="both")
        elif method == "ffill":
            return df.ffill()
        elif method == "drop":
            return df.dropna()
        return df

    @staticmethod
    def detect_anomalies(
        data: pd.Series, threshold: float = 3.0
    ) -> pd.Series:
        """基于标准差检测异常值"""
        mean = data.mean()
        std = data.std()
        return (data - mean).abs() > threshold * std

    def resample_time_series(
        self, df: pd.DataFrame, interval: str = "1H"
    ) -> pd.DataFrame:
        """时间序列重采样"""
        df = df.set_index("timestamp")
        resampled = df.resample(interval).mean()
        resampled = resampled.interpolate(method="linear")
        return resampled.reset_index()
