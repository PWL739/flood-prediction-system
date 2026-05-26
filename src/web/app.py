"""Web应用入口 —— FastAPI 服务

启动: uvicorn src.web.app:app --reload
文档: http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.web.routes import router
from src.config.settings import API_CONFIG

app = FastAPI(
    title="基于LSTM-Attention的洪水预测与预警系统",
    description="智慧水利应用课程作业 —— 第3组 | Week 2 增强版",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    """根路径，返回API概述"""
    return {
        "name": "基于LSTM-Attention的洪水预测与预警系统",
        "version": "2.0.0",
        "group": "第3组",
        "week": "Week 2",
        "endpoints": {
            "监测站点": {
                "GET /api/v1/stations": "获取站点列表（支持过滤）",
            },
            "实时数据": {
                "GET /api/v1/water-data/realtime": "获取实时水文数据",
                "POST /api/v1/sensor-data": "提交传感器数据（带校验）",
            },
            "历史数据": {
                "GET /api/v1/water-data/history": "查询历史数据（分页）",
                "POST /api/v1/water-data/export": "导出历史数据（JSON/CSV）",
            },
            "数据统计": {
                "GET /api/v1/data-stats": "数据分层存储统计",
                "POST /api/v1/data/process-batch": "批量数据处理",
            },
            "预测": {
                "GET /api/v1/prediction/flood-risk": "洪水风险预测",
                "GET /api/v1/prediction/all-stations": "所有站点风险预测",
            },
            "预警管理": {
                "POST /api/v1/warnings": "创建预警",
                "GET /api/v1/warnings/active": "生效预警列表",
                "POST /api/v1/warnings/{id}/cancel": "取消预警",
            },
            "采集统计": {
                "GET /api/v1/collection/stats": "数据采集统计",
            },
        },
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    from datetime import datetime
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
    }


def start():
    """启动服务"""
    import uvicorn
    uvicorn.run(
        "src.web.app:app",
        host=API_CONFIG["host"],
        port=API_CONFIG["port"],
        reload=API_CONFIG["debug"],
    )


if __name__ == "__main__":
    start()
