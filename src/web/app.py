"""Web应用入口 —— FastAPI 服务

启动: uvicorn src.web.app:app --reload
"""

from fastapi import FastAPI
from src.web.routes import router
from src.config.settings import API_CONFIG

app = FastAPI(
    title="基于LSTM-Attention的洪水预测与预警系统",
    description="智慧水利应用课程作业 —— 第3组",
    version="1.0.0",
)

app.include_router(router)


@app.get("/")
async def root():
    """根路径，返回API概述"""
    return {
        "name": "基于LSTM-Attention的洪水预测与预警系统",
        "version": "1.0.0",
        "group": "第3组",
        "endpoints": {
            "实时数据": "/api/v1/water-data/realtime",
            "提交传感器数据": "/api/v1/sensor-data",
            "洪水风险预测": "/api/v1/prediction/flood-risk",
            "预警管理": "/api/v1/warnings",
            "监测站点": "/api/v1/stations",
        },
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": "now"}


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
