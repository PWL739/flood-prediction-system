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
    description="智慧水利应用课程作业 —— 第3组 | Week 4 增强版",
    version="4.0.0",
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

# 操作日志中间件
from src.middleware.operation_log import OperationLogMiddleware
log_middleware = OperationLogMiddleware(app)
app.state.log_middleware = log_middleware

app.include_router(router)


@app.get("/")
async def root():
    """根路径，返回API概述"""
    return {
        "name": "基于LSTM-Attention的洪水预测与预警系统",
        "version": "4.0.0",
        "group": "第3组",
        "week": "Week 4",
        "features": {
            "auth": "JWT 认证 + 四角色权限",
            "cache": "两级预测缓存 (L1内存 + L2 Redis)",
            "import": "CSV 灵活导入 + 自动清洗",
            "logging": "操作日志中间件",
        },
        "endpoints": {
            "认证": {
                "POST /api/v1/auth/login": "用户登录",
                "GET /api/v1/auth/me": "当前用户信息",
            },
            "用户管理": {
                "POST /api/v1/users": "创建用户 (管理员)",
                "GET /api/v1/users": "用户列表 (管理员)",
                "DELETE /api/v1/users/{id}": "删除用户 (管理员)",
                "PUT /api/v1/users/{id}/password": "重置密码 (管理员)",
            },
            "监测站点": {
                "GET /api/v1/stations": "获取站点列表",
            },
            "实时数据": {
                "GET /api/v1/water-data/realtime": "获取实时水文数据",
                "POST /api/v1/sensor-data": "提交传感器数据 (需认证)",
            },
            "历史数据": {
                "GET /api/v1/water-data/history": "查询历史数据",
                "POST /api/v1/water-data/export": "导出历史数据 (需认证)",
            },
            "数据导入": {
                "POST /api/v1/data/import-csv": "导入CSV数据 (需认证)",
                "GET /api/v1/data/csv-sniff": "检测CSV格式 (需认证)",
                "GET /api/v1/data/import-templates": "映射模板列表 (需认证)",
                "POST /api/v1/data/import-templates": "保存映射模板 (需认证)",
                "GET /api/v1/data/import-history": "导入历史 (需认证)",
            },
            "预测": {
                "GET /api/v1/prediction/flood-risk": "洪水风险预测",
                "GET /api/v1/prediction/all-stations": "所有站点预测",
                "GET /api/v1/prediction/attention-heatmap": "注意力热力图",
            },
            "预警管理": {
                "POST /api/v1/warnings": "创建预警 (需认证)",
                "GET /api/v1/warnings/active": "生效预警列表",
                "GET /api/v1/warning/list": "预警列表",
                "POST /api/v1/warnings/{id}/confirm": "确认预警 (需认证)",
                "POST /api/v1/warnings/{id}/handle": "处理预警 (需认证)",
                "POST /api/v1/warnings/{id}/resolve": "解除预警 (需认证)",
                "POST /api/v1/warnings/{id}/escalate": "升级预警 (需认证)",
                "POST /api/v1/warnings/{id}/cancel": "取消预警 (需认证)",
                "GET /api/v1/warnings/{id}/state": "预警状态查询",
            },
            "操作日志": {
                "GET /api/v1/logs": "操作日志查询 (管理员/指挥)",
            },
            "系统": {
                "GET /health": "健康检查",
                "GET /api/v1/collection/stats": "采集统计",
                "GET /api/v1/data-stats": "数据统计",
                "POST /api/v1/data/process-batch": "批量处理 (需认证)",
            },
        },
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    from datetime import datetime
    from src.db.redis_client import redis_client
    return {
        "status": "healthy",
        "version": "4.0.0",
        "timestamp": datetime.now().isoformat(),
        "redis": "connected" if redis_client.health_check() else "degraded",
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
