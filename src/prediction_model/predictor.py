"""预测服务模块 —— 加载模型进行预测，并生成预警信息"""

import torch
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from src.config.settings import WARNING_THRESHOLDS, MODEL_CONFIG, MONITOR_STATIONS
from src.prediction_model.lstm_attention import LSTMAttentionModel


class FloodPredictor:
    """洪水预测服务"""

    def __init__(self, model: Optional[LSTMAttentionModel] = None):
        self.model = model or LSTMAttentionModel()
        self.model.eval()

    @torch.no_grad()
    def predict(self, input_sequence: np.ndarray) -> np.ndarray:
        """
        执行预测
        Args:
            input_sequence: 输入序列 [batch, seq_len, features]
        Returns:
            预测结果 [batch, output_size]
        """
        input_tensor = torch.FloatTensor(input_sequence)
        output = self.model(input_tensor)
        return output.numpy()

    def predict_flood_risk(
        self, recent_data: pd.DataFrame
    ) -> Dict:
        """
        预测洪水风险
        Args:
            recent_data: 最近72小时的水文数据
        Returns:
            risk_assessment: 风险评估结果
        """
        seq_length = MODEL_CONFIG["seq_length"]
        if len(recent_data) < seq_length:
            return {"error": f"数据不足，需要至少{seq_length}条记录"}

        # 提取特征
        feature_cols = ["water_level", "flow_rate", "rainfall", "temperature"]
        features = recent_data[feature_cols].values[-seq_length:]

        # 归一化
        mean = features.mean(axis=0, keepdims=True)
        std = features.std(axis=0, keepdims=True)
        std[std == 0] = 1
        features_norm = (features - mean) / std

        # 预测
        input_seq = features_norm.reshape(1, seq_length, -1)
        predictions = self.predict(input_seq)[0]

        # 去归一化(简化处理)
        predicted_levels = predictions * std[0, 0] + mean[0, 0]

        # 风险等级评估
        max_predicted_level = float(predicted_levels.max())
        risk_level = self._assess_risk_level(max_predicted_level)

        return {
            "predict_time": datetime.now().isoformat(),
            "location_id": recent_data.get("location_id", "unknown"),
            "max_predicted_water_level": round(max_predicted_level, 2),
            "hourly_predictions": [
                {"hour": i + 1, "level": round(float(l), 2)}
                for i, l in enumerate(predicted_levels[:24])
            ],
            "risk_level": risk_level["level"],
            "risk_name": risk_level["name"],
            "confidence": risk_level["confidence"],
        }

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

    def predict_all_stations(
        self, station_data: Dict[str, pd.DataFrame]
    ) -> List[Dict]:
        """预测所有站点的洪水风险"""
        results = []
        for station_id, data in station_data.items():
            if data is not None and len(data) >= MODEL_CONFIG["seq_length"]:
                result = self.predict_flood_risk(data)
                result["station_id"] = station_id
                result["station_name"] = self._get_station_name(station_id)
                results.append(result)
        return results

    @staticmethod
    def _get_station_name(station_id: str) -> str:
        """获取站点名称"""
        for station in MONITOR_STATIONS:
            if station["id"] == station_id:
                return station["name"]
        return station_id
