"""数据聚合重采样模块 —— DataAggregator 独立类，支持日/小时级别聚合"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta


class DataAggregator:
    """数据聚合器 —— 时序数据重采样与统计聚合"""

    def __init__(self):
        self.aggregation_log = []

    def resample(
        self,
        df: pd.DataFrame,
        freq: str = "1H",
        agg_method: Union[str, Dict] = "mean",
    ) -> pd.DataFrame:
        """
        时间序列重采样
        Args:
            df: 包含timestamp列的DataFrame
            freq: 重采样频率 (1H=每小时, 6H=每6小时, D=每天, W=每周)
            agg_method: 聚合方式 mean/sum/max/min/first/last
        """
        df = df.copy()
        if "timestamp" not in df.columns:
            raise ValueError("DataFrame缺少timestamp列")

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if isinstance(agg_method, str):
            agg_dict = {col: agg_method for col in numeric_cols}
        else:
            agg_dict = agg_method

        resampled = df[numeric_cols].resample(freq).agg(agg_dict)
        resampled = resampled.interpolate(method="linear", limit_direction="both")
        resampled = resampled.bfill().ffill()

        self.aggregation_log.append({
            "action": "resample",
            "freq": freq,
            "input_rows": len(df),
            "output_rows": len(resampled),
            "time": datetime.now().isoformat(),
        })

        return resampled.reset_index()

    def hourly_aggregate(self, df: pd.DataFrame) -> pd.DataFrame:
        """小时级聚合（默认1小时）"""
        return self.resample(df, freq="1H", agg_method="mean")

    def daily_aggregate(self, df: pd.DataFrame) -> pd.DataFrame:
        """日级聚合"""
        daily_agg = {
            "water_level": "mean",
            "flow_rate": "mean",
            "rainfall": "sum",
            "temperature": ["mean", "max", "min"],
            "ph_value": "mean",
            "turbidity": "mean",
            "dissolved_oxygen": "mean",
        }
        result = self.resample(df, freq="D", agg_method=daily_agg)
        # 展平多级列
        if isinstance(result.columns, pd.MultiIndex):
            result.columns = [
                "_".join(c).strip("_") for c in result.columns.values
            ]
        return result

    def compute_statistics(
        self, df: pd.DataFrame, window_hours: int = 24
    ) -> Dict:
        """计算指定窗口内的统计特征"""
        df = df.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        recent = df[numeric_cols].tail(window_hours)

        stats = {}
        for col in numeric_cols:
            series = recent[col].dropna()
            if len(series) > 0:
                stats[col] = {
                    "mean": float(series.mean()),
                    "max": float(series.max()),
                    "min": float(series.min()),
                    "std": float(series.std()) if len(series) > 1 else 0,
                    "trend": float(series.iloc[-1] - series.iloc[0]) if len(series) > 1 else 0,
                }

        return stats

    def merge_station_data(
        self, data_dict: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """合并多站点数据，添加站点ID列"""
        frames = []
        for station_id, df in data_dict.items():
            df = df.copy()
            df["location_id"] = station_id
            frames.append(df)
        return pd.concat(frames, ignore_index=True)

    def compute_basin_features(
        self, df: pd.DataFrame, window_hours: int = 24
    ) -> Dict:
        """计算流域特征（用于basin_feature表）"""
        df = df.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
            recent = df.tail(window_hours)
        else:
            recent = df.tail(window_hours)

        features = {}

        if "water_level" in recent.columns:
            wl = recent["water_level"].dropna()
            if len(wl) > 0:
                features["avg_water_level_24h"] = float(wl.mean())
                features["max_water_level_24h"] = float(wl.max())
                features["min_water_level_24h"] = float(wl.min())
                if len(wl) > 1:
                    features["water_level_trend"] = float(wl.iloc[-1] - wl.iloc[0]) / max(len(wl) - 1, 1)

        if "rainfall" in recent.columns:
            rf = recent["rainfall"].dropna()
            if len(rf) > 0:
                features["total_rainfall_24h"] = float(rf.sum())
                features["avg_rainfall_24h"] = float(rf.mean())

        # 洪水风险指数（简易计算）
        if "avg_water_level_24h" in features and "total_rainfall_24h" in features:
            wl_factor = min(features["avg_water_level_24h"] / 30.0, 1.0)
            rf_factor = min(features["total_rainfall_24h"] / 200.0, 1.0)
            features["flood_risk_index"] = round(0.4 * wl_factor + 0.6 * rf_factor, 4)
        else:
            features["flood_risk_index"] = 0.0

        return features
