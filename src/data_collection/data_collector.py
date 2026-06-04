"""数据采集模块高级接口"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from src.data_collection.sensor_simulator import SensorDataCollector


class DataCollectionService:
    """数据采集服务 —— 提供高层采集接口"""

    def __init__(self):
        self.collector = SensorDataCollector()
        self.collection_history = []

    def collect_realtime_data(self) -> List[Dict]:
        """采集实时数据（所有站点）"""
        data = self.collector.collect_all_data()
        self.collection_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": "realtime",
            "stations_count": len(data),
        })
        return data

    def collect_station_realtime(self, station_id: str) -> Optional[Dict]:
        """采集指定站点的实时数据"""
        data = self.collector.collect_station_data(station_id)
        if data:
            self.collection_history.append({
                "timestamp": datetime.now().isoformat(),
                "type": "station_realtime",
                "station_id": station_id,
            })
        return data

    def get_collection_stats(self) -> Dict:
        """获取采集统计信息"""
        return {
            "total_collections": len(self.collection_history),
            "last_collection": self.collection_history[-1] if self.collection_history else None,
        }

    def export_to_json(self, data: List[Dict], filepath: str):
        """将采集数据导出为JSON文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def format_data_for_storage(self, data: List[Dict]) -> List[Dict]:
        """将采集数据格式化为数据库存储格式"""
        formatted = []
        for station_data in data:
            station_id = station_data["station_id"]
            for reading in station_data["readings"]:
                record = {
                    "location_id": station_id,
                    "timestamp": datetime.fromisoformat(reading["timestamp"]),
                    "data_quality": 2 if "error" in reading else 1,
                }
                if reading["data_type"] == "water_level":
                    record["water_level"] = reading["value"]
                elif reading["data_type"] == "rainfall":
                    record["rainfall"] = reading["value"]
                elif reading["data_type"] == "water_quality":
                    record["ph_value"] = reading["parameters"]["ph"]
                    record["turbidity"] = reading["parameters"]["turbidity"]
                    record["dissolved_oxygen"] = reading["parameters"]["dissolved_oxygen"]
                formatted.append(record)
        return formatted
