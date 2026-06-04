"""操作日志中间件 —— 自动记录所有非GET请求"""

import time
import logging
from collections import deque
from datetime import datetime
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.auth.jwt_handler import JWTHandler
from src.config.settings import LOG_CONFIG

logger = logging.getLogger(__name__)


class OperationLogMiddleware(BaseHTTPMiddleware):
    """记录所有 POST/PUT/DELETE 请求到内存缓冲区"""

    # 请求路径到操作摘要的映射
    PATH_SUMMARY_MAP = {
        "/sensor-data":            "传感器数据提交",
        "/data/process-batch":     "批量数据处理",
        "/data/import-csv":        "CSV数据导入",
        "/water-data/export":      "历史数据导出",
        "/warnings":               "预警操作",
        "/auth/login":             "用户登录",
        "/users":                  "用户管理",
    }

    def __init__(self, app, db_session_factory=None):
        super().__init__(app)
        self._buffer: deque = deque(maxlen=LOG_CONFIG["buffer_max_size"])
        self._db_session_factory = db_session_factory
        self._batch_size = LOG_CONFIG["db_flush_batch_size"]
        self._flush_interval = LOG_CONFIG["db_flush_interval_seconds"]
        self._last_flush = time.time()

    @staticmethod
    def _extract_user(authorization: Optional[str]) -> tuple:
        """从 Authorization header 提取用户信息"""
        token = JWTHandler.get_token_from_header(authorization)
        if token:
            payload = JWTHandler.decode_token(token)
            if payload:
                return payload.get("sub", "anonymous"), payload.get("role", "unknown")
        return "anonymous", None

    @staticmethod
    def _summarize(path: str) -> str:
        """根据请求路径生成操作摘要"""
        for prefix, summary in OperationLogMiddleware.PATH_SUMMARY_MAP.items():
            if prefix in path:
                return summary
        return path.split("/")[-1] if path else "未知操作"

    async def dispatch(self, request: Request, call_next):
        # 只记录写操作
        if request.method.upper() not in ("POST", "PUT", "DELETE", "PATCH"):
            return await call_next(request)

        start_time = time.time()
        user_id, role = self._extract_user(request.headers.get("authorization"))

        # 执行实际请求
        response: Response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)

        # 构建日志条目
        log_entry = {
            "timestamp": datetime.now(),
            "user_id": user_id,
            "role": role,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "ip_address": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "")[:500],
            "request_summary": self._summarize(request.url.path),
        }

        # 写入内存缓冲区
        self._buffer.append(log_entry)

        return response

    def get_recent_logs(self, limit: int = 100) -> list:
        """获取最近的操作日志（从内存缓冲区）"""
        items = list(self._buffer)
        return items[-limit:]

    def get_all_buffered_logs(self) -> list:
        """获取所有缓冲区日志"""
        return list(self._buffer)
