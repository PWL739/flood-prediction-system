"""数据入库服务 —— 支持实时数据自动入库、历史数据批量导入、分层存储"""

import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db.models import (
    RawWaterData, CleanedWaterData, FeatureData,
    WaterMonitoringData, WaterQualityData,
)
from src.data_processing.data_validator import DataValidator
from src.data_processing.data_preprocessor import DataPreprocessor
from src.data_processing.batch_processor import BatchDataProcessor


class DataIngestionService:
    """数据入库服务 —— 分层存储管理"""

    def __init__(self, session: Session):
        self.session = session
        self.validator = DataValidator()
        self.preprocessor = DataPreprocessor()
        self.batch_processor = BatchDataProcessor()
        self.ingestion_log = []

    def ingest_raw_data(self, records: List[Dict]) -> int:
        """原始数据入库 (Tier 1)"""
        count = 0
        for record in records:
            try:
                raw = RawWaterData(
                    location_id=record.get("location_id") or record.get("station_id"),
                    timestamp=self._parse_timestamp(record.get("timestamp")),
                    water_level=record.get("water_level"),
                    flow_rate=record.get("flow_rate"),
                    rainfall=record.get("rainfall"),
                    temperature=record.get("temperature"),
                    ph_value=record.get("ph_value"),
                    turbidity=record.get("turbidity"),
                    dissolved_oxygen=record.get("dissolved_oxygen"),
                    data_quality=record.get("data_quality", 1),
                    raw_json=json.dumps(record, ensure_ascii=False, default=str),
                )
                self.session.add(raw)
                count += 1
            except Exception as e:
                self.ingestion_log.append({
                    "level": "error", "tier": "raw",
                    "record": str(record)[:200], "error": str(e),
                })

        self.session.commit()
        self.ingestion_log.append({
            "action": "ingest_raw", "count": count,
            "time": datetime.now().isoformat(),
        })
        return count

    def ingest_cleaned_data(self, records: List[Dict]) -> int:
        """清洗数据入库 (Tier 2)"""
        validation_results = self.validator.batch_validate_with_3sigma(records)
        valid_records = self.validator.filter_valid_data(validation_results)

        count = 0
        for vr in validation_results:
            record = vr["record"]
            try:
                cleaned = CleanedWaterData(
                    location_id=record.get("location_id") or record.get("station_id"),
                    timestamp=self._parse_timestamp(record.get("timestamp")),
                    water_level=record.get("water_level"),
                    flow_rate=record.get("flow_rate"),
                    rainfall=record.get("rainfall"),
                    temperature=record.get("temperature"),
                    ph_value=record.get("ph_value"),
                    turbidity=record.get("turbidity"),
                    dissolved_oxygen=record.get("dissolved_oxygen"),
                    quality_score=vr["quality_score"],
                    validation_passed=1 if vr["is_valid"] else 0,
                )
                self.session.add(cleaned)
                count += 1
            except Exception as e:
                self.ingestion_log.append({
                    "level": "error", "tier": "cleaned",
                    "error": str(e),
                })

        self.session.commit()
        self.ingestion_log.append({
            "action": "ingest_cleaned", "total": len(records),
            "valid": count, "time": datetime.now().isoformat(),
        })
        return count

    def ingest_feature_data(self, records: List[Dict]) -> int:
        """特征数据入库 (Tier 3)"""
        if len(records) < 72:
            return 0

        df = pd.DataFrame(records)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

        df = self.preprocessor.generate_features(df)
        count = 0

        for _, row in df.iterrows():
            try:
                feature = FeatureData(
                    location_id=row.get("location_id") or row.get("station_id"),
                    timestamp=self._parse_timestamp(row.get("timestamp")),
                    water_level=row.get("water_level"),
                    wl_rolling_mean_6h=row.get("wl_rolling_mean_6h"),
                    wl_rolling_std_6h=row.get("wl_rolling_std_6h"),
                    wl_diff_1h=row.get("wl_diff_1h"),
                    rf_cumsum_6h=row.get("rf_cumsum_6h"),
                    hour=row.get("hour"),
                    day_of_week=row.get("day_of_week"),
                    month=row.get("month"),
                )
                self.session.add(feature)
                count += 1
            except Exception as e:
                self.ingestion_log.append({
                    "level": "error", "tier": "feature", "error": str(e),
                })

        self.session.commit()
        self.ingestion_log.append({
            "action": "ingest_feature", "count": count,
            "time": datetime.now().isoformat(),
        })
        return count

    def ingest_all_tiers(self, records: List[Dict]) -> Dict:
        """完整分层入库"""
        result = {
            "raw": self.ingest_raw_data(records),
            "cleaned": self.ingest_cleaned_data(records),
            "feature": self.ingest_feature_data(records),
        }
        return result

    def batch_import_csv(self, filepath: str) -> Dict:
        """从CSV文件批量导入历史数据"""
        df = pd.read_csv(filepath, parse_dates=["timestamp"])
        if "timestamp" in df.columns:
            df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")
        records = df.to_dict("records")
        return self.ingest_all_tiers(records)

    def batch_import_json(self, filepath: str) -> Dict:
        """从JSON文件批量导入历史数据"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        records = []
        if isinstance(data, list):
            for item in data:
                if "readings" in item:
                    for reading in item["readings"]:
                        record = {"station_id": item.get("station_id")}
                        record.update(reading)
                        records.append(record)
                else:
                    records.append(item)
        return self.ingest_all_tiers(records)

    def query_raw_data(
        self, location_id: str = None, start_time: datetime = None,
        end_time: datetime = None, limit: int = 1000
    ) -> List[Dict]:
        """查询原始数据"""
        q = self.session.query(RawWaterData)
        if location_id:
            q = q.filter(RawWaterData.location_id == location_id)
        if start_time:
            q = q.filter(RawWaterData.timestamp >= start_time)
        if end_time:
            q = q.filter(RawWaterData.timestamp <= end_time)
        rows = q.order_by(RawWaterData.timestamp.desc()).limit(limit).all()
        return [self._row_to_dict(r) for r in rows]

    def query_cleaned_data(
        self, location_id: str = None, min_quality: float = 0.6,
        limit: int = 1000
    ) -> List[Dict]:
        """查询清洗后数据"""
        q = self.session.query(CleanedWaterData)
        if location_id:
            q = q.filter(CleanedWaterData.location_id == location_id)
        q = q.filter(CleanedWaterData.quality_score >= min_quality)
        rows = q.order_by(CleanedWaterData.timestamp.desc()).limit(limit).all()
        return [self._row_to_dict(r) for r in rows]

    def query_feature_data(
        self, location_id: str = None, limit: int = 1000
    ) -> List[Dict]:
        """查询特征数据"""
        q = self.session.query(FeatureData)
        if location_id:
            q = q.filter(FeatureData.location_id == location_id)
        rows = q.order_by(FeatureData.timestamp.desc()).limit(limit).all()
        return [self._row_to_dict(r) for r in rows]

    def get_data_stats(self) -> Dict:
        """获取各层数据统计"""
        stats = {}
        for name, model in [
            ("raw", RawWaterData), ("cleaned", CleanedWaterData),
            ("feature", FeatureData),
        ]:
            stats[name] = {
                "count": self.session.query(model).count(),
            }
            try:
                result = self.session.query(model).order_by(
                    model.timestamp.desc()
                ).first()
                stats[name]["latest_timestamp"] = \
                    result.timestamp.isoformat() if result and result.timestamp else None
            except Exception:
                stats[name]["latest_timestamp"] = None
        return stats

    def check_and_auto_ingest(self, records: List[Dict]) -> Dict:
        """实时数据自动检测并入库"""
        result = {"new_data": False, "ingested": {}}

        if not records:
            return result

        # 检查是否有新数据（基于时间戳去重）
        latest_ts = None
        for r in records:
            ts = self._parse_timestamp(r.get("timestamp"))
            if ts and (latest_ts is None or ts > latest_ts):
                latest_ts = ts

        if latest_ts:
            existing = self.session.query(RawWaterData).filter(
                RawWaterData.timestamp == latest_ts
            ).first()
            if not existing:
                result["new_data"] = True
                result["ingested"] = self.ingest_all_tiers(records)

        return result

    @staticmethod
    def _parse_timestamp(ts):
        """解析时间戳"""
        if ts is None:
            return datetime.now()
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, pd.Timestamp):
            return ts.to_pydatetime()
        try:
            return datetime.fromisoformat(str(ts))
        except (ValueError, TypeError):
            return datetime.now()

    @staticmethod
    def _row_to_dict(row):
        """将ORM行转为字典"""
        result = {}
        for col in row.__table__.columns:
            val = getattr(row, col.name)
            if isinstance(val, datetime):
                val = val.isoformat()
            result[col.name] = val
        return result
