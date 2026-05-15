"""数据处理模块单元测试"""

import pytest
from datetime import datetime
from src.data_processing.data_validator import DataValidator


class TestDataValidator:
    def test_range_validation_valid(self):
        valid, msg = DataValidator.validate_range("water_level", 10.0)
        assert valid

    def test_range_validation_invalid(self):
        valid, msg = DataValidator.validate_range("water_level", 999.0)
        assert not valid
        assert "超出范围" in msg

    def test_logical_consistency_ok(self):
        valid, msg = DataValidator.validate_logical_consistency(5.0, 10.0)
        assert valid

    def test_logical_consistency_fail(self):
        valid, msg = DataValidator.validate_logical_consistency(0.5, 80.0)
        assert not valid

    def test_timestamp_validation_future(self):
        from datetime import timedelta
        future_time = datetime.now() + timedelta(days=1)
        valid, msg = DataValidator.validate_timestamp(future_time)
        assert not valid

    def test_comprehensive_validation(self):
        validator = DataValidator()
        record = {
            "water_level": 15.0,
            "rainfall": 20.0,
            "temperature": 25.0,
            "timestamp": datetime.now(),
        }
        result = validator.validate_water_data(record)
        assert result["is_valid"]
        assert result["quality_score"] == 1.0

    def test_validation_rejects_outliers(self):
        validator = DataValidator()
        record = {
            "water_level": 999.0,
            "rainfall": 999.0,
            "timestamp": datetime.now(),
        }
        result = validator.validate_water_data(record)
        assert not result["is_valid"]
