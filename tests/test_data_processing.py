"""数据处理模块单元测试 —— Week 2 增强版"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from src.data_processing.data_validator import DataValidator, OutlierDetector
from src.data_processing.data_preprocessor import DataPreprocessor


class TestOutlierDetector:
    """Week 2 新增: 3σ异常值检测测试"""

    def test_three_sigma_normal_data(self):
        values = [10.0, 10.5, 9.8, 10.2, 10.1, 9.9]
        flags = OutlierDetector.three_sigma(values)
        assert not any(flags), "正常数据不应有异常标记"

    def test_three_sigma_with_outlier(self):
        values = [10.0, 10.5, 9.8, 10.2, 10.1, 9.9, 10.3, 10.0, 10.2, 9.7,
                  10.4, 10.1, 9.9, 10.0, 10.2, 9.8, 10.3, 10.1, 9.9, 1000.0]
        flags = OutlierDetector.three_sigma(values)
        assert flags[19], "1000.0应该被标记为异常"

    def test_three_sigma_small_dataset(self):
        values = [10.0, 10.5]
        flags = OutlierDetector.three_sigma(values)
        assert not any(flags), "数据量不足时不应报异常"

    def test_iqr_outliers(self):
        values = [10.0, 10.5, 9.8, 10.2, 100.0, 9.9, 10.1, 10.3]
        flags = OutlierDetector.iqr_outliers(values)
        assert flags[4], "IQR应检测出100.0异常"

    def test_detect_window_outliers(self):
        data = [
            {"station_id": "S001", "water_level": 10.0},
            {"station_id": "S001", "water_level": 10.5},
            {"station_id": "S001", "water_level": 9.8},
            {"station_id": "S001", "water_level": 10.2},
            {"station_id": "S001", "water_level": 10.1},
            {"station_id": "S001", "water_level": 9.9},
            {"station_id": "S001", "water_level": 10.3},
            {"station_id": "S001", "water_level": 10.0},
            {"station_id": "S001", "water_level": 10.2},
            {"station_id": "S001", "water_level": 9.7},
            {"station_id": "S001", "water_level": 10.4},
            {"station_id": "S001", "water_level": 10.1},
            {"station_id": "S001", "water_level": 9.9},
            {"station_id": "S001", "water_level": 10.0},
            {"station_id": "S001", "water_level": 10.2},
            {"station_id": "S001", "water_level": 9.8},
            {"station_id": "S001", "water_level": 10.3},
            {"station_id": "S001", "water_level": 10.1},
            {"station_id": "S001", "water_level": 9.9},
            {"station_id": "S001", "water_level": 1000.0},
        ]
        result = OutlierDetector.detect_window_outliers(data, "water_level")
        assert result[19]["_outlier"], "1000.0应该被标记"


class TestDataValidator:
    def test_range_validation_valid(self):
        valid, msg = DataValidator.validate_range("water_level", 10.0)
        assert valid

    def test_range_validation_invalid(self):
        valid, msg = DataValidator.validate_range("water_level", 999.0)
        assert not valid

    def test_logical_consistency_ok(self):
        valid, msg = DataValidator.validate_logical_consistency(5.0, 10.0)
        assert valid

    def test_logical_consistency_fail(self):
        valid, msg = DataValidator.validate_logical_consistency(0.5, 80.0)
        assert not valid

    def test_timestamp_validation_future(self):
        future_time = datetime.now() + timedelta(days=1)
        valid, msg = DataValidator.validate_timestamp(future_time)
        assert not valid

    def test_timestamp_validation_old(self):
        old_time = datetime.now() - timedelta(days=30)
        valid, msg = DataValidator.validate_timestamp(old_time, max_age_hours=168)
        assert not valid

    def test_timestamp_sequence_valid(self):
        times = [
            datetime.now() - timedelta(hours=i) for i in range(5, 0, -1)
        ]
        valid, msg = DataValidator.validate_timestamp_sequence(times)
        assert valid

    def test_timestamp_sequence_invalid_order(self):
        times = [datetime.now(), datetime.now() - timedelta(hours=1)]
        valid, msg = DataValidator.validate_timestamp_sequence(times)
        assert not valid

    def test_comprehensive_validation(self):
        validator = DataValidator()
        record = {
            "water_level": 15.0, "rainfall": 20.0,
            "temperature": 25.0, "timestamp": datetime.now(),
        }
        result = validator.validate_water_data(record)
        assert result["is_valid"]

    def test_validation_rejects_outliers(self):
        validator = DataValidator()
        record = {
            "water_level": 999.0, "rainfall": 999.0,
            "timestamp": datetime.now(),
        }
        result = validator.validate_water_data(record)
        assert not result["is_valid"]

    def test_batch_validate_with_3sigma(self):
        """Week 2 新增: 批量3σ验证测试"""
        validator = DataValidator()
        records = [
            {"water_level": 10.0, "timestamp": datetime.now()},
            {"water_level": 10.5, "timestamp": datetime.now()},
            {"water_level": 9.8, "timestamp": datetime.now()},
            {"water_level": 10.2, "timestamp": datetime.now()},
            {"water_level": 999.0, "timestamp": datetime.now()},
        ]
        results = validator.batch_validate_with_3sigma(records)
        assert not results[4]["is_valid"], "异常值应被3σ检测拦截"


class TestDataPreprocessor:
    def test_standardize(self):
        preprocessor = DataPreprocessor()
        data = np.array([[10.0], [20.0], [30.0]], dtype=np.float64)
        result = preprocessor.standardize_data(data)
        assert abs(result.mean()) < 1e-6

    def test_normalize(self):
        preprocessor = DataPreprocessor()
        data = np.array([[10.0], [20.0], [30.0]], dtype=np.float64)
        result = preprocessor.normalize_data(data)
        assert result.min() >= 0
        assert result.max() <= 1

    def test_create_sequences(self):
        preprocessor = DataPreprocessor(seq_length=5)
        data = np.arange(20, dtype=np.float64).reshape(-1, 1)
        sequences = preprocessor.create_sequences(data)
        assert sequences.shape == (15, 5, 1)

    def test_handle_missing_values(self):
        import pandas as pd
        preprocessor = DataPreprocessor()
        df = pd.DataFrame({
            "water_level": [10.0, None, 12.0, None, 11.0],
            "rainfall": [1.0, 2.0, None, 3.0, 2.0],
        })
        result = preprocessor.handle_missing_values(df, method="interpolate")
        assert result["water_level"].isnull().sum() == 0

    def test_detect_anomalies(self):
        import pandas as pd
        preprocessor = DataPreprocessor()
        data = pd.Series([10.0, 10.5, 9.8, 10.2, 10.1, 9.9, 10.3, 10.0, 10.2, 9.7,
                          10.4, 10.1, 9.9, 10.0, 10.2, 9.8, 10.3, 10.1, 9.9, 1000.0])
        anomalies = preprocessor.detect_anomalies(data, threshold=3.0)
        assert anomalies.iloc[19], "1000.0应被标记为异常"

    def test_create_sliding_windows(self):
        """Week 2 新增: 72小时滑动窗口测试"""
        import pandas as pd
        preprocessor = DataPreprocessor(seq_length=10, output_size=5)
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=50, freq="h"),
            "water_level": np.random.uniform(8, 15, 50),
            "rainfall": np.random.uniform(0, 10, 50),
        })
        X, y = preprocessor.create_sliding_windows(
            df, ["water_level", "rainfall"], "water_level"
        )
        assert X.shape[1:] == (10, 2), f"X形状错误: {X.shape}"
        assert y.shape[1] == 5, f"y形状错误: {y.shape}"

    def test_generate_features(self):
        """Week 2 新增: 特征工程测试"""
        import pandas as pd
        preprocessor = DataPreprocessor()
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=20, freq="h"),
            "water_level": np.random.uniform(8, 15, 20),
            "rainfall": np.random.uniform(0, 10, 20),
        })
        result = preprocessor.generate_features(df)
        assert "wl_rolling_mean_6h" in result.columns
        assert "wl_diff_1h" in result.columns
        assert "rf_cumsum_6h" in result.columns
