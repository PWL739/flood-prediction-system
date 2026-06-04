"""预测服务模块 —— 加载模型进行预测，并生成预警信息
Week 4: 集成两级缓存、向量化预处理、模型预加载
"""

import torch
import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from src.config.settings import WARNING_THRESHOLDS, MODEL_CONFIG, MONITOR_STATIONS
from src.prediction_model.lstm_attention import LSTMAttentionModel
from src.prediction_model.prediction_cache import PredictionCache

logger = logging.getLogger(__name__)


class FloodPredictor:
    """洪水预测服务 —— 支持多站点模型预加载 + 两级缓存"""

    FEATURE_COLS = ["water_level", "flow_rate", "rainfall", "temperature", "ph", "turbidity", "dissolved_oxygen"]

    def __init__(self, model: Optional[LSTMAttentionModel] = None, models_dir: Optional[str] = None):
        self._default_model = model or LSTMAttentionModel()
        self._default_model.eval()
        self.model_registry: Dict[str, LSTMAttentionModel] = {}
        self.cache = PredictionCache()
        self._models_dir = Path(models_dir) if models_dir else Path(__file__).parent.parent.parent / "models"
        self._preload_models()

    def _preload_models(self):
        """启动时预加载所有站点模型"""
        for station in MONITOR_STATIONS:
            sid = station["id"]
            model_path = self._models_dir / f"lstm_attention_{sid}.pt"
            if model_path.exists():
                try:
                    model = LSTMAttentionModel()
                    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
                    model.eval()
                    self.model_registry[sid] = model
                    logger.info("模型加载成功: %s", model_path)
                except Exception as e:
                    logger.warning("模型加载失败 %s: %s", model_path, e)
        if not self.model_registry:
            logger.info("未找到预训练模型，使用默认模型（随机权重）")

    def _get_model(self, station_id: str) -> LSTMAttentionModel:
        """获取站点对应模型，未预加载则使用默认模型"""
        return self.model_registry.get(station_id, self._default_model)

    @torch.no_grad()
    def predict(self, input_sequence: np.ndarray, station_id: str = "default") -> np.ndarray:
        """执行预测（纯 NumPy 输入 -> NumPy 输出）"""
        model = self._get_model(station_id)
        input_tensor = torch.FloatTensor(input_sequence)
        output = model(input_tensor)
        return output.numpy()

    @torch.no_grad()
    def predict_with_attention_weights(self, input_sequence: np.ndarray, station_id: str = "default") -> dict:
        """执行预测并返回注意力权重"""
        model = self._get_model(station_id)
        input_tensor = torch.FloatTensor(input_sequence)
        result = model.predict_with_attention(input_tensor)
        return {
            "prediction": result["prediction"].numpy(),
            "attention_weights": result["attention_weights"].numpy(),
        }

    def predict_flood_risk(self, recent_data: pd.DataFrame) -> Dict:
        """预测洪水风险 —— 集成两级缓存"""
        seq_length = MODEL_CONFIG["seq_length"]
        if len(recent_data) < seq_length:
            return {"error": f"数据不足，需要至少{seq_length}条记录"}

        station_id = (
            recent_data["location_id"].iloc[0]
            if "location_id" in recent_data.columns
            else "unknown"
        )

        # 提取特征并转换为 NumPy（向量化）
        features = np.zeros((len(recent_data), len(self.FEATURE_COLS)), dtype=np.float32)
        for i, col in enumerate(self.FEATURE_COLS):
            if col in recent_data.columns:
                features[:, i] = recent_data[col].values.astype(np.float32)

        features = features[-seq_length:]  # 取最后 72 行

        # 归一化（纯 NumPy）
        mean = features.mean(axis=0, keepdims=True)
        std = features.std(axis=0, keepdims=True)
        std[std == 0] = 1.0
        features_norm = (features - mean) / std

        # 计算输入哈希，查询缓存
        input_hash = PredictionCache.compute_hash(features_norm)
        cached = self.cache.get(station_id, input_hash)
        if cached is not None:
            return cached

        # 执行推理
        input_seq = features_norm.reshape(1, seq_length, -1)
        att_result = self.predict_with_attention_weights(input_seq, station_id)
        predictions = att_result["prediction"][0]
        attention_weights = att_result["attention_weights"][0].tolist()

        # 去归一化
        predicted_levels = predictions * std[0, 0] + mean[0, 0]

        # 风险等级评估
        max_predicted_level = float(predicted_levels.max())
        risk_level = self._assess_risk_level(max_predicted_level)

        station_name = self._get_station_name(station_id)

        result = {
            "predict_time": datetime.now().isoformat(),
            "station_name": station_name,
            "location_id": station_id,
            "max_predicted_water_level": round(max_predicted_level, 2),
            "hourly_predictions": [
                {"hour": i + 1, "level": round(float(l), 2)}
                for i, l in enumerate(predicted_levels[:24])
            ],
            "risk_level": risk_level["level"],
            "risk_name": risk_level["name"],
            "confidence": risk_level["confidence"],
            "attention_weights": attention_weights,
        }

        # 写入缓存
        self.cache.set(station_id, input_hash, result)

        return result

    def _assess_risk_level(self, water_level: float) -> Dict:
        """评估风险等级"""
        if water_level >= WARNING_THRESHOLDS["level_4"]["water_level"]:
            return {"level": 4, "name": "红色预警", "confidence": 0.85}
        elif water_level >= WARNING_THRESHOLDS["level_3"]["water_level"]:
            return {"level": 3, "name": "橙色预警", "confidence": 0.88}
        elif water_level >= WARNING_THRESHOLDS["level_2"]["water_level"]:
            return {"level": 2, "name": "黄色预警", "confidence": 0.92}
        elif water_level >= WARNING_THRESHOLDS["level_1"]["water_level"]:
            return {"level": 1, "name": "蓝色预警", "confidence": 0.95}
        return {"level": 0, "name": "正常", "confidence": 0.98}

    def predict_all_stations(self, station_data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """预测所有站点的洪水风险"""
        results = []
        for station_id, data in station_data.items():
            if data is not None and len(data) >= MODEL_CONFIG["seq_length"]:
                result = self.predict_flood_risk(data)
                result["station_id"] = station_id
                result["station_name"] = self._get_station_name(station_id)
                results.append(result)
        return results

    def invalidate_station_cache(self, station_id: str):
        """外部接口：清除指定站点预测缓存"""
        self.cache.invalidate_station(station_id)

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        return self.cache.stats()

    @staticmethod
    def _get_station_name(station_id: str) -> str:
        """获取站点名称"""
        for station in MONITOR_STATIONS:
            if station["id"] == station_id:
                return station["name"]
        return station_id
