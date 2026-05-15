"""数据库模型定义 —— 对应详细设计文档中数据库设计部分"""

from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, String, DateTime, Decimal,
    Text, SmallInteger, Float, create_engine, Index
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MonitorStation(Base):
    """监测站点信息表"""
    __tablename__ = "monitor_station"

    id = Column(String(50), primary_key=True, comment="站点ID")
    name = Column(String(100), nullable=False, comment="站点名称")
    latitude = Column(Decimal(10, 6), comment="纬度")
    longitude = Column(Decimal(10, 6), comment="经度")
    river_system = Column(String(100), comment="所属水系")
    status = Column(SmallInteger, default=1, comment="状态: 1-正常, 0-停用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        Index("idx_station_status", "status"),
    )


class WaterMonitoringData(Base):
    """水文监测数据表 —— 存储水位、流量、降雨等核心时序数据"""
    __tablename__ = "water_monitoring_data"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(50), nullable=False, comment="站点ID")
    timestamp = Column(DateTime, nullable=False, comment="数据时间戳")
    water_level = Column(Decimal(8, 2), comment="水位(m)")
    flow_rate = Column(Decimal(10, 2), comment="流量(m³/s)")
    rainfall = Column(Decimal(6, 2), comment="降雨量(mm)")
    temperature = Column(Decimal(5, 2), comment="温度(°C)")
    data_quality = Column(SmallInteger, default=1, comment="数据质量: 1-正常, 2-异常, 3-缺失")
    status = Column(SmallInteger, default=1, comment="记录状态")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        Index("idx_location_time", "location_id", "timestamp"),
        Index("idx_timestamp", "timestamp"),
        Index("idx_status", "status"),
    )


class WaterQualityData(Base):
    """水质监测数据表"""
    __tablename__ = "water_quality_data"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(50), nullable=False, comment="站点ID")
    timestamp = Column(DateTime, nullable=False, comment="数据时间戳")
    ph_value = Column(Decimal(3, 2), comment="pH值")
    turbidity = Column(Decimal(6, 2), comment="浊度(NTU)")
    dissolved_oxygen = Column(Decimal(5, 2), comment="溶解氧(mg/L)")
    ammonia_nitrogen = Column(Decimal(6, 3), comment="氨氮(mg/L)")
    chemical_oxygen_demand = Column(Decimal(6, 2), comment="化学需氧量(mg/L)")
    water_quality_level = Column(SmallInteger, comment="水质等级: 1-5类")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_quality_location_time", "location_id", "timestamp"),
        Index("idx_quality_level", "water_quality_level"),
    )


class FloodPredictionRecord(Base):
    """洪水预测记录表"""
    __tablename__ = "flood_prediction_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(String(50), nullable=False, comment="站点ID")
    predict_time = Column(DateTime, nullable=False, comment="预测时间")
    predict_hour = Column(SmallInteger, comment="预测未来第N小时")
    predicted_water_level = Column(Decimal(8, 2), comment="预测水位(m)")
    confidence_score = Column(Decimal(5, 4), comment="置信度")
    risk_level = Column(SmallInteger, comment="风险等级: 1-4")
    model_version = Column(String(50), comment="模型版本号")
    input_data_summary = Column(Text, comment="输入数据摘要(JSON)")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_pred_location_time", "location_id", "predict_time"),
        Index("idx_pred_risk_level", "risk_level"),
    )


class WarningInfo(Base):
    """预警信息表"""
    __tablename__ = "warning_info"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    warning_type = Column(SmallInteger, nullable=False, comment="预警类型: 1-洪水, 2-干旱, 3-污染")
    warning_level = Column(SmallInteger, nullable=False, comment="预警等级: 1-4")
    title = Column(String(200), nullable=False, comment="预警标题")
    content = Column(Text, comment="预警内容")
    affected_location = Column(String(200), comment="影响区域")
    publish_time = Column(DateTime, nullable=False, comment="发布时间")
    expire_time = Column(DateTime, comment="过期时间")
    status = Column(SmallInteger, default=1, comment="状态: 1-生效, 0-取消")
    created_by = Column(String(50), comment="创建人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_warning_type_level", "warning_type", "warning_level"),
        Index("idx_warning_publish_time", "publish_time"),
        Index("idx_warning_status", "status"),
    )


class ModelVersion(Base):
    """模型版本记录表"""
    __tablename__ = "model_version"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    version = Column(String(50), nullable=False, comment="版本号")
    description = Column(Text, comment="版本描述")
    accuracy = Column(Decimal(5, 4), comment="准确率")
    parameters_summary = Column(Text, comment="参数摘要(JSON)")
    training_data_range = Column(String(200), comment="训练数据时间范围")
    status = Column(SmallInteger, default=1, comment="状态: 1-已部署, 0-未部署")
    deployed_by = Column(String(50), comment="部署人")
    deployed_at = Column(DateTime, comment="部署时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("idx_model_version", "version"),
        Index("idx_model_status", "status"),
    )
