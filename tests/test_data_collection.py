"""数据采集模块单元测试"""

import pytest
from src.data_collection.sensor_simulator import (
    WaterLevelSensor, RainfallSensor, WaterQualitySensor, SensorDataCollector
)
from src.data_collection.data_collector import DataCollectionService


class TestWaterLevelSensor:
    def test_read_data_returns_valid_structure(self):
        sensor = WaterLevelSensor("S001")
        data = sensor.read_data()
        assert "station_id" in data
        assert "value" in data
        assert "unit" in data
        assert data["unit"] == "m"

    def test_read_data_returns_positive_value(self):
        sensor = WaterLevelSensor("S001", base_level=10.0)
        data = sensor.read_data()
        assert data["value"] > 0


class TestRainfallSensor:
    def test_read_data_returns_non_negative(self):
        sensor = RainfallSensor("S001")
        for _ in range(100):
            data = sensor.read_data()
            assert data["value"] >= 0

    def test_data_type_is_rainfall(self):
        sensor = RainfallSensor("S001")
        data = sensor.read_data()
        assert data["data_type"] == "rainfall"


class TestSensorDataCollector:
    def test_collect_all_data_returns_all_stations(self):
        collector = SensorDataCollector()
        data = collector.collect_all_data()
        assert len(data) == 5  # 配置了5个站点

    def test_collect_station_data_valid(self):
        collector = SensorDataCollector()
        data = collector.collect_station_data("S001")
        assert data is not None
        assert data["station_id"] == "S001"

    def test_collect_station_data_invalid(self):
        collector = SensorDataCollector()
        data = collector.collect_station_data("INVALID")
        assert data is None


class TestDataCollectionService:
    def test_collection_stats(self):
        service = DataCollectionService()
        service.collect_realtime_data()
        stats = service.get_collection_stats()
        assert stats["total_collections"] == 1
