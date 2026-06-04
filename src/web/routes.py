"""API路由定义 —— Week 2增强版：统一响应格式、参数校验、历史数据导出"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from src.data_collection.data_collector import DataCollectionService
from src.prediction_model.predictor import FloodPredictor
from src.prediction_model.warning_service import WarningService
from src.web.schemas import (
    SensorDataSubmit, RealtimeDataQuery, HistoricalDataQuery,
    HistoricalDataExport, FloodRiskQuery,
    WarningCreate,
)

router = APIRouter(prefix="/api/v1")

# 服务实例
data_service = DataCollectionService()
predictor = FloodPredictor()
warning_service = WarningService()


# ==================== 统一响应工具 ====================

def success_response(data=None, message: str = "success") -> dict:
    return {"code": 200, "message": message, "data": data}


def error_response(code: int, message: str, detail: str = None) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={
            "code": code,
            "message": message,
            "data": None,
            "detail": detail,
        },
    )


# ==================== 监测站点 ====================

@router.get("/stations")
async def get_stations(
    station_id: Optional[str] = Query(None, description="站点ID过滤"),
    status: Optional[int] = Query(None, description="状态过滤"),
):
    """获取监测站点列表"""
    from src.config.settings import MONITOR_STATIONS
    stations = MONITOR_STATIONS
    if station_id:
        stations = [s for s in stations if s["id"] == station_id]
        if not stations:
            raise HTTPException(status_code=404, detail=f"站点 {station_id} 不存在")
    if status is not None:
        stations = [s for s in stations if s.get("status", 1) == status]
    return success_response(stations)


# ==================== 实时数据 ====================

@router.get("/water-data/realtime")
async def get_realtime_data(
    location_id: Optional[str] = Query(None, description="站点ID"),
    data_type: Optional[str] = Query(None, description="数据类型: water_level/rainfall/water_quality"),
):
    """获取实时水文数据"""
    if location_id:
        data = data_service.collect_station_realtime(location_id)
        if not data:
            raise HTTPException(status_code=404, detail=f"站点 {location_id} 不存在")
        result = data
        if data_type and "readings" in result:
            result["readings"] = [
                r for r in result["readings"]
                if r.get("data_type") == data_type
            ]
        return success_response(result)
    else:
        data = data_service.collect_realtime_data()
        return success_response(data)


@router.post("/sensor-data")
async def submit_sensor_data(data: SensorDataSubmit):
    """提交传感器数据（带Pydantic校验）"""
    import pandas as pd
    import numpy as np

    # 格式化为处理格式
    formatted = []
    for reading in data.readings:
        record = {"station_id": reading.station_id}
        if reading.value is not None:
            record[reading.data_type] = reading.value
        elif reading.parameters:
            record.update(reading.parameters)
        record["timestamp"] = reading.timestamp
        formatted.append(record)

    from src.data_processing.data_validator import DataValidator
    validator = DataValidator()
    validation_results = validator.batch_validate(formatted)
    valid_count = sum(1 for r in validation_results if r["is_valid"])
    quality_avg = sum(r["quality_score"] for r in validation_results) / max(len(validation_results), 1)

    return success_response({
        "status": "received",
        "total": len(formatted),
        "valid": valid_count,
        "average_quality": round(quality_avg, 2),
    })


# ==================== 历史数据导出 ====================

@router.get("/water-data/history")
async def get_historical_data(
    location_id: str = Query(..., description="站点ID"),
    start_time: Optional[str] = Query(None, description="起始时间 ISO 8601"),
    end_time: Optional[str] = Query(None, description="结束时间 ISO 8601"),
    limit: int = Query(1000, ge=1, le=10000, description="返回条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """查询历史水文数据"""
    from src.config.settings import DATA_DIR
    import json
    from pathlib import Path

    # 尝试从保存的数据中加载历史记录
    data_file = DATA_DIR / "collected_data.json"
    records = []

    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            stored = json.load(f)

        for station_data in stored:
            if location_id and station_data.get("station_id") != location_id:
                continue
            for reading in station_data.get("readings", []):
                ts = reading.get("timestamp")
                if start_time and ts < start_time:
                    continue
                if end_time and ts > end_time:
                    continue
                record = {"station_id": station_data["station_id"]}
                record.update(reading)
                records.append(record)

    total = len(records)
    paged = records[offset: offset + limit]

    return success_response({
        "total": total,
        "offset": offset,
        "limit": limit,
        "records": paged,
    })


@router.post("/water-data/export")
async def export_historical_data(query: HistoricalDataExport):
    """导出历史数据（JSON/CSV）"""
    from src.config.settings import DATA_DIR
    import json as json_module
    import csv
    import io
    from pathlib import Path

    data_file = DATA_DIR / "collected_data.json"
    records = []

    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            stored = json_module.load(f)

        for station_data in stored:
            if station_data.get("station_id") != query.location_id:
                continue
            for reading in station_data.get("readings", []):
                ts = reading.get("timestamp", "")
                if query.start_time and ts < query.start_time:
                    continue
                if query.end_time and ts > query.end_time:
                    continue
                record = {"station_id": station_data["station_id"]}
                record.update(reading)
                records.append(record)

    if query.format == "csv":
        if not records:
            raise HTTPException(status_code=404, detail="无匹配数据")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=export_{query.location_id}_{datetime.now().strftime('%Y%m%d')}.csv"
            },
        )

    return success_response({
        "export_time": datetime.now().isoformat(),
        "location_id": query.location_id,
        "total_records": len(records),
        "records": records,
    })


# ==================== 数据分层查询 ====================

@router.get("/data-stats")
async def get_data_statistics():
    """获取数据分层存储统计"""
    from src.config.settings import DATA_DIR, DATA_TIER_CONFIG
    import json

    stats = {"tiers": DATA_TIER_CONFIG, "current_data": {}}

    data_file = DATA_DIR / "collected_data.json"
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            stored = json.load(f)
        stats["current_data"]["file"] = str(data_file)
        stats["current_data"]["stations"] = len(stored)
        total_readings = sum(
            len(s.get("readings", [])) for s in stored
            if isinstance(s, dict)
        )
        stats["current_data"]["total_readings"] = total_readings

    return success_response(stats)


# ==================== 批量数据处理 ====================

@router.post("/data/process-batch")
async def process_batch_data(filepath: str = Query(..., description="数据文件路径")):
    """批量处理历史数据（清洗+特征工程+数据集构建）"""
    from pathlib import Path
    from src.data_processing.batch_processor import BatchDataProcessor

    path = Path(filepath)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {filepath}")

    processor = BatchDataProcessor()

    if path.suffix == ".json":
        records = processor.load_from_json(str(path))
    elif path.suffix == ".csv":
        df = processor.load_from_csv(str(path))
        records = df.to_dict("records")
    else:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {path.suffix}")

    # 扁平化嵌套数据（如果是采集格式）
    flat_records = []
    for item in records:
        if "readings" in item:
            for reading in item["readings"]:
                record = {"station_id": item.get("station_id")}
                _flatten_reading(reading, record)
                flat_records.append(record)
        else:
            flat_records.append(item)

    if not flat_records:
        flat_records = records

    result = processor.process_pipeline(flat_records)
    return success_response(result)


def _flatten_reading(reading: dict, record: dict):
    """展平传感器读数"""
    record["timestamp"] = reading.get("timestamp")
    record["data_type"] = reading.get("data_type")
    if "value" in reading:
        record[reading["data_type"]] = reading["value"]
    if "parameters" in reading:
        for k, v in reading["parameters"].items():
            record[k] = v
    if "unit" in reading:
        record["unit"] = reading["unit"]


# ==================== 预测相关 ====================

@router.get("/prediction/flood-risk")
async def get_flood_risk(location_id: str = Query(..., description="站点ID")):
    """获取洪水风险预测"""
    import pandas as pd
    import numpy as np

    raw_data = data_service.collect_station_realtime(location_id)
    if not raw_data:
        raise HTTPException(status_code=404, detail=f"站点 {location_id} 不存在或无数据")

    dates = pd.date_range(end=datetime.now(), periods=72, freq="h")
    sample_data = pd.DataFrame({
        "location_id": location_id,
        "timestamp": dates,
        "water_level": np.random.uniform(8, 18, 72),
        "flow_rate": np.random.uniform(100, 500, 72),
        "rainfall": np.random.uniform(0, 30, 72),
        "temperature": np.random.uniform(15, 35, 72),
        "ph": np.random.uniform(6.5, 7.5, 72),
        "turbidity": np.random.uniform(10, 20, 72),
        "dissolved_oxygen": np.random.uniform(6, 10, 72),
    })

    result = predictor.predict_flood_risk(sample_data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    warning = warning_service.generate_flood_warning(result)
    if warning:
        warning_service.send_warning(warning)
        result["warning"] = warning

    return success_response(result)


@router.get("/prediction/attention-heatmap")
async def get_attention_heatmap(location_id: str = Query(..., description="站点ID")):
    """获取注意力热力图数据（72h历史 × 24h预测权重矩阵）"""
    import pandas as pd
    import numpy as np

    raw_data = data_service.collect_station_realtime(location_id)
    if not raw_data:
        raise HTTPException(status_code=404, detail=f"站点 {location_id} 不存在或无数据")

    dates = pd.date_range(end=datetime.now(), periods=72, freq="h")
    sample_data = pd.DataFrame({
        "location_id": location_id,
        "timestamp": dates,
        "water_level": np.random.uniform(8, 18, 72),
        "flow_rate": np.random.uniform(100, 500, 72),
        "rainfall": np.random.uniform(0, 30, 72),
        "temperature": np.random.uniform(15, 35, 72),
        "ph": np.random.uniform(6.5, 7.5, 72),
        "turbidity": np.random.uniform(10, 20, 72),
        "dissolved_oxygen": np.random.uniform(6, 10, 72),
    })

    result = predictor.predict_flood_risk(sample_data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    attention_weights = result.get("attention_weights", [])
    predictions = [h["level"] for h in result.get("hourly_predictions", [])]

    feature_names = ["water_level", "flow_rate", "rainfall", "temperature", "ph", "turbidity", "dissolved_oxygen"]
    history_labels = [f"T-{72-i}h" for i in range(72)]
    prediction_labels = [f"T+{i+1}h" for i in range(24)]

    return success_response({
        "location_id": location_id,
        "station_name": result.get("station_name", location_id),
        "predict_time": result["predict_time"],
        "risk_level": result["risk_level"],
        "risk_name": result["risk_name"],
        "attention_weights": attention_weights,
        "predictions": predictions,
        "feature_names": feature_names,
        "history_labels": history_labels,
        "prediction_labels": prediction_labels,
    })


@router.get("/prediction/all-stations")
async def get_all_stations_risk():
    """获取所有站点的洪水风险预测"""
    import pandas as pd
    import numpy as np

    results = []
    for station_id in ["S001", "S002", "S003", "S004", "S005"]:
        dates = pd.date_range(end=datetime.now(), periods=72, freq="h")
        sample_data = pd.DataFrame({
            "location_id": station_id,
            "timestamp": dates,
            "water_level": np.random.uniform(8, 18, 72),
            "flow_rate": np.random.uniform(100, 500, 72),
            "rainfall": np.random.uniform(0, 30, 72),
            "temperature": np.random.uniform(15, 35, 72),
            "ph": np.random.uniform(6.5, 7.5, 72),
            "turbidity": np.random.uniform(10, 20, 72),
            "dissolved_oxygen": np.random.uniform(6, 10, 72),
        })
        result = predictor.predict_flood_risk(sample_data)
        if "error" not in result:
            results.append(result)

    return success_response(results)


# ==================== 预警管理 ====================

@router.post("/warnings")
async def create_warning(warning_data: WarningCreate):
    """创建预警信息（Pydantic校验）"""
    warning = warning_service.create_warning(
        warning_type=warning_data.warning_type,
        warning_level=warning_data.warning_level,
        title=warning_data.title,
        content=warning_data.content,
        affected_location=warning_data.affected_location,
        expire_hours=warning_data.expire_hours,
    )
    return success_response(warning, message="预警创建成功")


@router.get("/warnings/active")
async def get_active_warnings():
    """获取当前生效的预警"""
    warnings = warning_service.get_active_warnings()
    return success_response(warnings)


@router.get("/warning/list")
async def get_warning_list(
    status: Optional[int] = Query(None, description="状态过滤: 1-已发布, 2-已确认, 3-处理中, 4-已解除, 0-已取消"),
):
    """获取预警列表（Week 2 新增：支持按状态机状态过滤）"""
    warnings = warning_service.get_warning_list(status_filter=status)
    return success_response({
        "total": len(warnings),
        "warnings": warnings,
        "status_names": {
            0: "已取消", 1: "已发布", 2: "已确认",
            3: "处理中", 4: "已解除",
        },
    })


# ==================== 预警状态机 (Week 2 新增) ====================

@router.post("/warnings/{warning_id}/confirm")
async def confirm_warning(
    warning_id: str,
    confirmed_by: str = Query("system", description="确认人"),
):
    """确认预警: 已发布(1) → 已确认(2)"""
    ok = warning_service.confirm_warning(warning_id, confirmed_by)
    if not ok:
        raise HTTPException(status_code=400, detail="预警不存在或状态不允许确认(需为'已发布')")
    state = warning_service.get_warning_state(warning_id)
    return success_response(state, message="预警已确认")


@router.post("/warnings/{warning_id}/handle")
async def handle_warning(
    warning_id: str,
    handled_by: str = Query("system", description="处理人"),
):
    """处理预警: 已确认(2) → 处理中(3)"""
    ok = warning_service.handle_warning(warning_id, handled_by)
    if not ok:
        raise HTTPException(status_code=400, detail="预警不存在或状态不允许处理(需为'已确认')")
    state = warning_service.get_warning_state(warning_id)
    return success_response(state, message="预警处理中")


@router.post("/warnings/{warning_id}/resolve")
async def resolve_warning(
    warning_id: str,
    resolved_by: str = Query("system", description="解除人"),
):
    """解除预警: 处理中(3) → 已解除(4)"""
    ok = warning_service.resolve_warning(warning_id, resolved_by)
    if not ok:
        raise HTTPException(status_code=400, detail="预警不存在或状态不允许解除(需为'已确认'或'处理中')")
    state = warning_service.get_warning_state(warning_id)
    return success_response(state, message="预警已解除")


@router.post("/warnings/{warning_id}/escalate")
async def escalate_warning(warning_id: str):
    """升级预警: 提升一个等级"""
    result = warning_service.escalate_warning(warning_id)
    if not result:
        raise HTTPException(status_code=400, detail="预警不存在或已是最高级别")
    return success_response(result, message="预警已升级")


@router.get("/warnings/{warning_id}/state")
async def get_warning_state(warning_id: str):
    """查询预警状态机当前状态"""
    state = warning_service.get_warning_state(warning_id)
    if not state:
        raise HTTPException(status_code=404, detail="预警不存在")
    return success_response(state)


@router.post("/warnings/{warning_id}/cancel")
async def cancel_warning(warning_id: str):
    """取消预警"""
    success = warning_service.cancel_warning(warning_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"预警 {warning_id} 不存在")
    return success_response({"warning_id": warning_id, "status": "cancelled"}, message="预警已取消")


# ==================== 数据采集统计 ====================

@router.get("/collection/stats")
async def get_collection_stats():
    """获取数据采集统计"""
    stats = data_service.get_collection_stats()
    return success_response(stats)
