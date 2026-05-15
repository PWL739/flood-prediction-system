"""传感器模拟器 —— 模拟水文传感器数据采集"""

import math
import random
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
from src.config.settings import SENSOR_CONFIG, MONITOR_STATIONS


class WaterLevelSensor:
    """水位传感器模拟器"""

    def __init__(self, station_id: str, base_level: float = 8.0):
        self.station_id = station_id
        self.base_level = base_level
        self.current_level = base_level
        self.last_update_time = None

    def read_data(self) -> Dict:
        """读取水位数据，模拟实际传感器读数"""
        # 模拟水位波动：基础水位 + 日周期波动 + 随机噪声 + 趋势偏移
        hour = datetime.now().hour
        diurnal_variation = 1.5 * math.sin(2 * math.pi * (hour - 6) / 24)
        noise = random.gauss(0, 0.2)
        trend = random.uniform(-0.05, 0.05)

        self.current_level = max(0, self.base_level + diurnal_variation + noise + trend)
        self.last_update_time = datetime.now()

        return {
            "station_id": self.station_id,
            "data_type": "water_level",
            "value": round(self.current_level, 2),
            "unit": "m",
            "timestamp": self.last_update_time.isoformat(),
        }


class RainfallSensor:
    """降雨量传感器模拟器"""

    def __init__(self, station_id: str):
        self.station_id = station_id
        self.is_raining = False
        self.rain_intensity = 0.0

    def read_data(self) -> Dict:
        """读取降雨量数据"""
        # 模拟降雨事件
        if not self.is_raining and random.random() < 0.15:
            self.is_raining = True
            self.rain_intensity = random.uniform(1.0, 25.0)

        if self.is_raining:
            self.rain_intensity = max(0, self.rain_intensity + random.gauss(0, 2.0))
            if self.rain_intensity < 0.5 or random.random() < 0.1:
                self.is_raining = False
                self.rain_intensity = 0.0

        noise = random.gauss(0, 0.1)
        value = max(0, self.rain_intensity + noise)

        return {
            "station_id": self.station_id,
            "data_type": "rainfall",
            "value": round(value, 2),
            "unit": "mm",
            "timestamp": datetime.now().isoformat(),
        }


class WaterQualitySensor:
    """水质传感器模拟器"""

    def __init__(self, station_id: str):
        self.station_id = station_id
        self.base_ph = 7.0
        self.base_turbidity = 15.0
        self.base_oxygen = 8.0

    def read_data(self) -> Dict:
        """读取水质数据"""
        return {
            "station_id": self.station_id,
            "data_type": "water_quality",
            "parameters": {
                "ph": round(random.gauss(self.base_ph, 0.3), 2),
                "turbidity": round(max(0, random.gauss(self.base_turbidity, 3.0)), 2),
                "dissolved_oxygen": round(max(0, random.gauss(self.base_oxygen, 1.0)), 2),
            },
            "timestamp": datetime.now().isoformat(),
        }


class SensorDataCollector:
    """传感器数据采集器 —— 管理多个传感器并采集数据"""

    def __init__(self):
        self.sensors = {}
        self._init_sensors()

    def _init_sensors(self):
        """初始化所有监测站点的传感器"""
        for station in MONITOR_STATIONS:
            sid = station["id"]
            self.sensors[sid] = {
                "water_level": WaterLevelSensor(sid, base_level=random.uniform(5, 15)),
                "rainfall": RainfallSensor(sid),
                "water_quality": WaterQualitySensor(sid),
            }

    def collect_all_data(self) -> list:
        """采集所有站点所有传感器数据"""
        all_data = []
        for station_id, sensor_group in self.sensors.items():
            station_data = {"station_id": station_id, "readings": []}
            for sensor_type, sensor in sensor_group.items():
                try:
                    reading = sensor.read_data()
                    station_data["readings"].append(reading)
                except Exception as e:
                    station_data["readings"].append({
                        "station_id": station_id,
                        "data_type": sensor_type,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    })
            all_data.append(station_data)
        return all_data

    def collect_station_data(self, station_id: str) -> Optional[Dict]:
        """采集指定站点的数据"""
        if station_id not in self.sensors:
            return None
        station_data = {"station_id": station_id, "readings": []}
        for sensor_type, sensor in self.sensors[station_id].items():
            try:
                reading = sensor.read_data()
                station_data["readings"].append(reading)
            except Exception as e:
                station_data["readings"].append({
                    "station_id": station_id,
                    "data_type": sensor_type,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                })
        return station_data
