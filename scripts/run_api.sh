#!/bin/bash
# 启动FastAPI后端服务

cd "$(dirname "$0")/.." || exit 1

echo "=========================================="
echo "  启动洪水预测与预警系统 - FastAPI"
echo "=========================================="
echo ""
echo "API地址: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"
echo "按 Ctrl+C 停止服务"
echo ""

uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload