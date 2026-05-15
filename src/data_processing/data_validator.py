"""数据验证与清洗模块 —— 对应详细设计文档中的数据校验逻辑"""

from datetime import datetime
from typing import Dict, List, Tuple
from src.config.settings import SENSOR_CONFIG


class DataValidator:
    """数据验证器 —— 执行范围校验、逻辑校验、完整性校验"""

    @staticmethod
    def validate_range(data_type: str, value: float) -> Tuple[bool, str]:
        """范围校验：检查数据是否在合理范围内"""
        if data_type not in SENSOR_CONFIG:
            return False, f"未知数据类型: {data_type}"

        config = SENSOR_CONFIG[data_type]
        if value < config["min"] or value > config["max"]:
            return (
                False,
                f"{data_type}值{value}超出范围[{config['min']}, {config['max']}]"
            )
        return True, ""

    @staticmethod
    def validate_logical_consistency(
        water_level: float, rainfall: float
    ) -> Tuple[bool, str]:
        """逻辑校验：检查数据之间的逻辑一致性"""
        # 如果降雨量很大但水位很低，可能存在数据异常
        if rainfall > 50 and water_level < 1.0:
            return False, "降雨量较大但水位过低，数据不一致"
        return True, ""

    @staticmethod
    def validate_timestamp(timestamp: datetime) -> Tuple[bool, str]:
        """时间戳校验"""
        now = datetime.now()
        if timestamp > now:
            return False, "时间戳不能早于当前时间"
        if (now - timestamp).days > 7:
            return False, "数据时间戳超过7天，已过期"
        return True, ""

    def validate_water_data(self, record: Dict) -> Dict:
        """综合校验单条水文数据"""
        validation_result = {
            "record": record,
            "is_valid": True,
            "issues": [],
            "quality_score": 1.0,
        }

        # 范围校验
        if "water_level" in record:
            valid, msg = self.validate_range("water_level", record["water_level"])
            if not valid:
                validation_result["is_valid"] = False
                validation_result["issues"].append(msg)
                validation_result["quality_score"] -= 0.3

        if "rainfall" in record:
            valid, msg = self.validate_range("rainfall", record["rainfall"])
            if not valid:
                validation_result["is_valid"] = False
                validation_result["issues"].append(msg)
                validation_result["quality_score"] -= 0.2

        if "temperature" in record:
            valid, msg = self.validate_range("temperature", record["temperature"])
            if not valid:
                validation_result["is_valid"] = False
                validation_result["issues"].append(msg)
                validation_result["quality_score"] -= 0.2

        # 逻辑校验
        if "water_level" in record and "rainfall" in record:
            valid, msg = self.validate_logical_consistency(
                record["water_level"], record["rainfall"]
            )
            if not valid:
                validation_result["is_valid"] = False
                validation_result["issues"].append(msg)
                validation_result["quality_score"] -= 0.3

        # 时间戳校验
        if "timestamp" in record:
            valid, msg = self.validate_timestamp(record["timestamp"])
            if not valid:
                validation_result["is_valid"] = False
                validation_result["issues"].append(msg)
                validation_result["quality_score"] -= 0.2

        validation_result["quality_score"] = max(0.0, validation_result["quality_score"])
        return validation_result

    def batch_validate(self, records: List[Dict]) -> List[Dict]:
        """批量校验多条数据"""
        return [self.validate_water_data(r) for r in records]

    @staticmethod
    def filter_valid_data(validation_results: List[Dict]) -> List[Dict]:
        """筛选有效数据"""
        return [
            r["record"] for r in validation_results
            if r["is_valid"] and r["quality_score"] >= 0.6
        ]
