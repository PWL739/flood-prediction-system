"""数据验证与清洗模块 —— 范围校验、逻辑校验、时间戳校验、3σ异常值检测"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from src.config.settings import SENSOR_CONFIG


class OutlierDetector:
    """异常值检测器 —— 基于统计学方法检测异常数据"""

    @staticmethod
    def three_sigma(values: List[float], threshold: float = 3.0) -> List[bool]:
        """3σ异常值检测：标记偏离均值超过3倍标准差的值"""
        if len(values) < 3:
            return [False] * len(values)
        arr = np.array(values, dtype=np.float64)
        mean = np.mean(arr)
        std = np.std(arr)
        if std < 1e-10:
            return [False] * len(values)
        z_scores = np.abs((arr - mean) / std)
        return (z_scores > threshold).tolist()

    @staticmethod
    def iqr_outliers(values: List[float], multiplier: float = 1.5) -> List[bool]:
        """IQR异常值检测"""
        if len(values) < 4:
            return [False] * len(values)
        arr = np.array(values, dtype=np.float64)
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
        return ((arr < lower) | (arr > upper)).tolist()

    @staticmethod
    def detect_window_outliers(
        data: List[Dict], field: str, method: str = "3sigma"
    ) -> List[Dict]:
        """在时间窗口内检测异常值，为每条记录添加异常标记"""
        values = [d.get(field) for d in data]
        if method == "3sigma":
            flags = OutlierDetector.three_sigma(values)
        elif method == "iqr":
            flags = OutlierDetector.iqr_outliers(values)
        else:
            flags = [False] * len(values)

        for i, record in enumerate(data):
            record["_outlier"] = flags[i]
            if flags[i]:
                record["_quality"] = record.get("_quality", 1.0) - 0.4
        return data


class DataValidator:
    """数据验证器 —— 范围校验、逻辑校验、时间戳校验、3σ异常值检测"""

    @staticmethod
    def validate_range(data_type: str, value: float) -> Tuple[bool, str]:
        """范围校验：检查数据是否在合理范围内"""
        if data_type not in SENSOR_CONFIG:
            return False, f"未知数据类型: {data_type}"
        config = SENSOR_CONFIG[data_type]
        if value < config["min"] or value > config["max"]:
            return False, f"{data_type}值{value}超出范围[{config['min']}, {config['max']}]"
        return True, ""

    @staticmethod
    def validate_logical_consistency(
        water_level: float, rainfall: float
    ) -> Tuple[bool, str]:
        """逻辑校验：检查数据之间的逻辑一致性"""
        if rainfall > 50 and water_level < 1.0:
            return False, "降雨量较大但水位过低，数据不一致"
        return True, ""

    @staticmethod
    def validate_timestamp(
        timestamp: datetime, max_age_hours: int = 168
    ) -> Tuple[bool, str]:
        """时间戳校验：检查时间戳是否合法"""
        now = datetime.now()
        if timestamp > now:
            return False, "时间戳不能晚于当前时间"
        if (now - timestamp).total_seconds() > max_age_hours * 3600:
            return False, f"数据时间戳超过{max_age_hours}小时，已过期"
        return True, ""

    @staticmethod
    def validate_timestamp_sequence(timestamps: List[datetime]) -> Tuple[bool, str]:
        """时间序列校验：检查时间戳是否连续且有序"""
        for i in range(len(timestamps) - 1):
            if timestamps[i] >= timestamps[i + 1]:
                return False, f"时间戳顺序异常: 索引{i} >= {i+1}"
            delta = (timestamps[i + 1] - timestamps[i]).total_seconds()
            if delta > 86400:
                return False, f"时间间隔过大: 索引{i}到{i+1}间隔{delta/3600:.1f}小时"
        return True, ""

    def validate_water_data(self, record: Dict) -> Dict:
        """综合校验单条水文数据"""
        validation_result = {
            "record": record,
            "is_valid": True,
            "issues": [],
            "quality_score": 1.0,
        }

        if "water_level" in record and record["water_level"] is not None:
            valid, msg = self.validate_range("water_level", record["water_level"])
            if not valid:
                validation_result["is_valid"] = False
                validation_result["issues"].append(msg)
                validation_result["quality_score"] -= 0.3

        if "rainfall" in record and record["rainfall"] is not None:
            valid, msg = self.validate_range("rainfall", record["rainfall"])
            if not valid:
                validation_result["is_valid"] = False
                validation_result["issues"].append(msg)
                validation_result["quality_score"] -= 0.2

        if "temperature" in record and record["temperature"] is not None:
            valid, msg = self.validate_range("temperature", record["temperature"])
            if not valid:
                validation_result["is_valid"] = False
                validation_result["issues"].append(msg)
                validation_result["quality_score"] -= 0.2

        if "water_level" in record and "rainfall" in record:
            wl = record.get("water_level")
            rf = record.get("rainfall")
            if wl is not None and rf is not None:
                valid, msg = self.validate_logical_consistency(wl, rf)
                if not valid:
                    validation_result["is_valid"] = False
                    validation_result["issues"].append(msg)
                    validation_result["quality_score"] -= 0.3

        if "timestamp" in record and record["timestamp"] is not None:
            valid, msg = self.validate_timestamp(record["timestamp"])
            if not valid:
                validation_result["is_valid"] = False
                validation_result["issues"].append(msg)
                validation_result["quality_score"] -= 0.2

        validation_result["quality_score"] = max(0.0, validation_result["quality_score"])
        return validation_result

    def batch_validate(self, records: List[Dict]) -> List[Dict]:
        """批量校验"""
        return [self.validate_water_data(r) for r in records]

    def batch_validate_with_3sigma(
        self, records: List[Dict]
    ) -> List[Dict]:
        """批量校验 + 3σ异常值检测"""
        results = self.batch_validate(records)

        # 对数值字段执行3σ检测
        numeric_fields = ["water_level", "rainfall", "flow_rate", "temperature"]
        for field in numeric_fields:
            values = [
                r["record"].get(field)
                for r in results
                if r["record"].get(field) is not None
            ]
            if len(values) < 3:
                continue
            outliers = OutlierDetector.three_sigma(values)

            outlier_idx = 0
            for r in results:
                if r["record"].get(field) is not None:
                    if outlier_idx < len(outliers) and outliers[outlier_idx]:
                        r["is_valid"] = False
                        r["issues"].append(
                            f"{field}值{r['record'][field]}被3σ检测标记为异常"
                        )
                        r["quality_score"] = max(0.0, r["quality_score"] - 0.3)
                    outlier_idx += 1

        return results

    @staticmethod
    def filter_valid_data(validation_results: List[Dict]) -> List[Dict]:
        """筛选有效数据"""
        return [
            r["record"] for r in validation_results
            if r["is_valid"] and r["quality_score"] >= 0.6
        ]
