"""Pydantic数据模型 —— API请求/响应验证"""

from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, field_validator


# ==================== 通用响应模型 ====================

class APIResponse(BaseModel):
    """统一API响应格式"""
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="响应消息")
    data: Any = Field(default=None, description="响应数据")

    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "message": "success",
                "data": {"key": "value"},
            }
        }


class PaginatedResponse(APIResponse):
    """分页响应"""
    data: Any = None
    pagination: Optional[Dict] = Field(default=None, description="分页信息")


# ==================== 站点相关模型 ====================

class StationInfo(BaseModel):
    """站点信息"""
    id: str = Field(..., description="站点ID")
    name: str = Field(..., description="站点名称")
    lat: float = Field(..., description="纬度")
    lng: float = Field(..., description="经度")
    status: Optional[int] = Field(default=1, description="状态: 1-正常, 0-停用")


class StationQuery(BaseModel):
    """站点查询参数"""
    station_id: Optional[str] = Field(default=None, description="站点ID")
    status: Optional[int] = Field(default=None, description="状态过滤")


# ==================== 传感器数据模型 ====================

class SensorReading(BaseModel):
    """传感器读数"""
    station_id: str = Field(..., description="站点ID")
    data_type: str = Field(..., description="数据类型: water_level/rainfall/water_quality")
    value: Optional[float] = Field(default=None, description="数值")
    unit: Optional[str] = Field(default=None, description="单位")
    parameters: Optional[Dict[str, float]] = Field(default=None, description="复合参数")
    timestamp: str = Field(..., description="时间戳 (ISO 8601)")


class SensorDataSubmit(BaseModel):
    """传感器数据提交"""
    station_id: str = Field(..., min_length=1, description="站点ID")
    readings: List[SensorReading] = Field(..., min_length=1, description="传感器读数列表")

    @field_validator("station_id")
    @classmethod
    def validate_station_id(cls, v):
        valid_ids = {"S001", "S002", "S003", "S004", "S005"}
        if v not in valid_ids:
            raise ValueError(f"无效站点ID: {v}，有效值为: {valid_ids}")
        return v


class RealtimeDataQuery(BaseModel):
    """实时数据查询参数"""
    location_id: Optional[str] = Field(default=None, description="站点ID")
    data_type: Optional[str] = Field(default=None, description="数据类型")


# ==================== 历史数据模型 ====================

class HistoricalDataQuery(BaseModel):
    """历史数据查询参数"""
    location_id: str = Field(..., min_length=1, description="站点ID")
    start_time: Optional[str] = Field(default=None, description="起始时间 (ISO 8601)")
    end_time: Optional[str] = Field(default=None, description="结束时间 (ISO 8601)")
    data_tier: str = Field(default="cleaned", description="数据层级: raw/cleaned/feature")
    limit: int = Field(default=1000, ge=1, le=10000, description="返回条数限制")
    offset: int = Field(default=0, ge=0, description="偏移量")


class HistoricalDataExport(BaseModel):
    """历史数据导出请求"""
    location_id: str = Field(..., min_length=1, description="站点ID")
    start_time: str = Field(..., description="起始时间 (ISO 8601)")
    end_time: str = Field(..., description="结束时间 (ISO 8601)")
    format: str = Field(default="json", description="导出格式: json/csv")
    data_tier: str = Field(default="cleaned", description="数据层级")


# ==================== 预测相关模型 ====================

class FloodRiskQuery(BaseModel):
    """洪水风险预测查询"""
    location_id: str = Field(..., min_length=1, description="站点ID")


class PredictionResult(BaseModel):
    """预测结果"""
    predict_time: str = Field(..., description="预测时间")
    location_id: str = Field(..., description="站点ID")
    max_predicted_water_level: float = Field(..., description="预测最高水位")
    hourly_predictions: List[Dict] = Field(default_factory=list, description="逐小时预测")
    risk_level: int = Field(..., ge=0, le=4, description="风险等级: 0-4")
    risk_name: str = Field(..., description="风险名称")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")


# ==================== 预警相关模型 ====================

class WarningCreate(BaseModel):
    """创建预警"""
    warning_type: int = Field(..., ge=1, le=3, description="预警类型: 1-洪水, 2-干旱, 3-污染")
    warning_level: int = Field(..., ge=1, le=4, description="预警等级: 1-4")
    title: str = Field(..., min_length=1, max_length=200, description="预警标题")
    content: str = Field(..., min_length=1, description="预警内容")
    affected_location: str = Field(default="未知区域", description="影响区域")
    expire_hours: int = Field(default=24, ge=1, le=168, description="过期小时数")


class WarningInfo(BaseModel):
    """预警信息"""
    id: str
    warning_type: int
    warning_level: int
    title: str
    content: str
    affected_location: str
    publish_time: str
    expire_time: str
    status: int


# ==================== 数据入库模型 ====================

class DataImportRequest(BaseModel):
    """数据导入请求"""
    source: str = Field(..., description="数据来源: csv/json")
    filepath: str = Field(..., description="文件路径")
    auto_clean: bool = Field(default=True, description="是否自动清洗")


class DataStatsResponse(BaseModel):
    """数据统计"""
    raw: Dict
    cleaned: Dict
    feature: Dict
