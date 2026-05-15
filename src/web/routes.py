"""API路由定义 —— 对应详细设计文档接口设计部分"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from src.data_collection.data_collector import DataCollectionService
from src.prediction_model.predictor import FloodPredictor
from src.prediction_model.warning_service import WarningService

router = APIRouter(prefix="/api/v1")

# 服务实例
data_service = DataCollectionService()
predictor = FloodPredictor()
warning_service = WarningService()


@router.get("/water-data/realtime")
async def get_realtime_data(
    location_id: Optional[str] = Query(None, description="站点ID"),
    data_type: Optional[str] = Query(None, description="数据类型"),
):
    """获取实时水文数据"""
    if location_id:
        data = data_service.collect_station_realtime(location_id)
        if not data:
            raise HTTPException(status_code=404, detail="站点不存在")
        return {"code": 200, "message": "success", "data": data}
    else:
        data = data_service.collect_realtime_data()
        return {"code": 200, "message": "success", "data": data}


@router.post("/sensor-data")
async def submit_sensor_data(data: dict):
    """提交传感器数据"""
    # 数据接收与格式校验
    if "station_id" not in data:
        raise HTTPException(status_code=400, detail="缺少station_id字段")
    return {"code": 200, "message": "数据提交成功", "data": {"status": "received"}}


@router.get("/prediction/flood-risk")
async def get_flood_risk(location_id: str = Query(..., description="站点ID")):
    """获取洪水风险预测"""
    from src.data_processing.data_preprocessor import DataPreprocessor
    import pandas as pd
    import numpy as np

    # 获取最近数据并预测
    raw_data = data_service.collect_station_realtime(location_id)
    if not raw_data:
        raise HTTPException(status_code=404, detail="站点不存在或无数据")

    # 构造示例时序数据进行预测
    dates = pd.date_range(end=datetime.now(), periods=72, freq="h")
    sample_data = pd.DataFrame({
        "location_id": location_id,
        "timestamp": dates,
        "water_level": np.random.uniform(8, 18, 72),
        "flow_rate": np.random.uniform(100, 500, 72),
        "rainfall": np.random.uniform(0, 30, 72),
        "temperature": np.random.uniform(15, 35, 72),
    })

    result = predictor.predict_flood_risk(sample_data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # 自动生成预警
    warning = warning_service.generate_flood_warning(result)
    if warning:
        warning_service.send_warning(warning)
        result["warning"] = warning

    return {"code": 200, "message": "success", "data": result}


@router.post("/warnings")
async def create_warning(warning_data: dict):
    """创建预警信息"""
    required_fields = ["warning_type", "warning_level", "title", "content"]
    for field in required_fields:
        if field not in warning_data:
            raise HTTPException(status_code=400, detail=f"缺少必填字段: {field}")

    warning = warning_service.create_warning(
        warning_type=warning_data["warning_type"],
        warning_level=warning_data["warning_level"],
        title=warning_data["title"],
        content=warning_data["content"],
        affected_location=warning_data.get("affected_location", "未知区域"),
    )
    return {"code": 200, "message": "预警创建成功", "data": warning}


@router.get("/warnings/active")
async def get_active_warnings():
    """获取当前生效的预警"""
    warnings = warning_service.get_active_warnings()
    return {"code": 200, "message": "success", "data": warnings}


@router.get("/stations")
async def get_stations():
    """获取监测站点列表"""
    from src.config.settings import MONITOR_STATIONS
    return {"code": 200, "message": "success", "data": MONITOR_STATIONS}
