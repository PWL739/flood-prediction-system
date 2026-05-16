#!/bin/bash
# 启动Streamlit可视化界面

cd "$(dirname "$0")/.." || exit 1

echo "=========================================="
echo "  启动洪水预测与预警系统 - Streamlit"
echo "=========================================="
echo ""
echo "访问地址: http://localhost:8501"
echo "按 Ctrl+C 停止服务"
echo ""

streamlit run src/visualization/app.py --server.port 8501 --server.address 0.0.0.0