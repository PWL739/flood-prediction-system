"""数据预处理模块 —— 归一化、标准化、时序窗口化、特征工程"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from src.config.settings import MODEL_CONFIG, SENSOR_CONFIG


class DataPreprocessor:
    """数据预处理器 —— 将原始数据转换为模型可用的特征"""

    def __init__(self, seq_length: int = None, output_size: int = None):
        self.seq_length = seq_length or MODEL_CONFIG["seq_length"]
        self.output_size = output_size or MODEL_CONFIG["output_size"]
        self._feature_stats = {}  # 保存归一化参数，用于逆变换

    def normalize_data(self, data: np.ndarray) -> np.ndarray:
        """Min-Max归一化"""
        min_val = data.min(axis=0, keepdims=True)
        max_val = data.max(axis=0, keepdims=True)
        range_val = max_val - min_val
        range_val[range_val == 0] = 1
        return (data - min_val) / range_val

    def standardize_data(self, data: np.ndarray) -> np.ndarray:
        """Z-score标准化"""
        mean = data.mean(axis=0, keepdims=True)
        std = data.std(axis=0, keepdims=True)
        std[std == 0] = 1
        return (data - mean) / std

    def fit_standardize(self, data: np.ndarray) -> np.ndarray:
        """Z-score标准化并保存参数"""
        mean = data.mean(axis=0, keepdims=True)
        std = data.std(axis=0, keepdims=True)
        std[std == 0] = 1
        self._feature_stats["mean"] = mean
        self._feature_stats["std"] = std
        return (data - mean) / std

    def inverse_standardize(self, normalized: np.ndarray) -> np.ndarray:
        """Z-score逆变换"""
        mean = self._feature_stats.get("mean")
        std = self._feature_stats.get("std")
        if mean is None or std is None:
            raise ValueError("请先调用fit_standardize")
        return normalized * std + mean

    def create_sequences(
        self, data: np.ndarray, seq_length: Optional[int] = None
    ) -> np.ndarray:
        """创建时间序列样本（滑动窗口）"""
        if seq_length is None:
            seq_length = self.seq_length
        if len(data) <= seq_length:
            return np.array([])
        sequences = []
        for i in range(len(data) - seq_length):
            sequences.append(data[i : i + seq_length])
        return np.array(sequences)

    def create_sliding_windows(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        72小时滑动窗口构建特征和标签
        Returns:
            X: [n_samples, seq_length, n_features]
            y: [n_samples, output_size] (未来24小时)
        """
        if len(df) < self.seq_length + self.output_size:
            raise ValueError(
                f"数据不足：需要至少{self.seq_length + self.output_size}条，"
                f"当前{len(df)}条"
            )

        features = df[feature_cols].values.astype(np.float64)
        targets = df[target_col].values.astype(np.float64)

        X, y = [], []
        for i in range(len(df) - self.seq_length - self.output_size + 1):
            X.append(features[i : i + self.seq_length])
            y.append(targets[i + self.seq_length : i + self.seq_length + self.output_size])

        return np.array(X), np.array(y)

    def prepare_training_data(
        self, df: pd.DataFrame, target_col: str = "water_level"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """准备训练数据：生成特征矩阵和标签"""
        feature_cols = [
            c for c in df.columns
            if c != target_col and c != "timestamp" and c != "location_id"
            and c != "station_id" and df[c].dtype in ("float64", "float32", "int64")
        ]

        if not feature_cols:
            raise ValueError(f"未找到数值型特征列，数据列: {df.columns.tolist()}")

        features = df[feature_cols].values.astype(np.float64)
        targets = df[target_col].values.astype(np.float64)

        features_norm = self.standardize_data(features)
        targets_norm = self.standardize_data(targets.reshape(-1, 1)).flatten()

        X, y = [], []
        for i in range(len(features_norm) - self.seq_length):
            X.append(features_norm[i : i + self.seq_length])
            y.append(targets_norm[i + self.seq_length])

        return np.array(X), np.array(y)

    def prepare_multi_step_data(
        self, df: pd.DataFrame, target_col: str = "water_level"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """准备多步预测训练数据（预测未来24小时）"""
        feature_cols = [
            c for c in df.columns
            if c != target_col and c != "timestamp" and c != "location_id"
            and c != "station_id" and df[c].dtype in ("float64", "float32", "int64")
        ]
        features = df[feature_cols].values.astype(np.float64)
        targets = df[target_col].values.astype(np.float64)

        features_norm = self.fit_standardize(features)
        targets_norm = self.fit_standardize(targets.reshape(-1, 1)).flatten()

        X, y = [], []
        total = self.seq_length + self.output_size
        for i in range(len(features_norm) - total + 1):
            X.append(features_norm[i : i + self.seq_length])
            y.append(targets_norm[i + self.seq_length : i + total])

        return np.array(X), np.array(y)

    @staticmethod
    def handle_missing_values(
        df: pd.DataFrame, method: str = "interpolate"
    ) -> pd.DataFrame:
        """处理缺失值"""
        if method == "interpolate":
            return df.interpolate(method="linear", limit_direction="both")
        elif method == "ffill":
            return df.ffill().bfill()
        elif method == "drop":
            return df.dropna()
        return df

    @staticmethod
    def detect_anomalies(data: pd.Series, threshold: float = 3.0) -> pd.Series:
        """基于标准差检测异常值（3σ方法）"""
        mean = data.mean()
        std = data.std()
        if std < 1e-10:
            return pd.Series([False] * len(data), index=data.index)
        return (data - mean).abs() > threshold * std

    def resample_time_series(
        self, df: pd.DataFrame, interval: str = "1H"
    ) -> pd.DataFrame:
        """时间序列重采样"""
        df = df.copy()
        if "timestamp" not in df.columns:
            raise ValueError("DataFrame缺少timestamp列")
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        resampled = df[numeric_cols].resample(interval).mean()
        resampled = resampled.interpolate(method="linear")
        return resampled.reset_index()

    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """特征工程：生成统计特征"""
        df = df.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["hour"] = df["timestamp"].dt.hour
            df["day_of_week"] = df["timestamp"].dt.dayofweek
            df["month"] = df["timestamp"].dt.month

        if "water_level" in df.columns:
            df["wl_rolling_mean_6h"] = df["water_level"].rolling(6, min_periods=1).mean()
            df["wl_rolling_std_6h"] = df["water_level"].rolling(6, min_periods=1).std().fillna(0)
            df["wl_diff_1h"] = df["water_level"].diff().fillna(0)

        if "rainfall" in df.columns:
            df["rf_cumsum_6h"] = df["rainfall"].rolling(6, min_periods=1).sum()

        return df
