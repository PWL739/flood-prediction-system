"""Streamlit Web可视化 —— 主页面

启动方式:
    streamlit run src/visualization/app.py

或在项目根目录运行:
    streamlit run src/visualization/app.py --server.port 8501
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.config.settings import MONITOR_STATIONS, WARNING_THRESHOLDS
from src.data_collection.data_collector import DataCollectionService
from src.prediction_model.predictor import FloodPredictor
from src.prediction_model.warning_service import WarningService

# 页面配置 - 蓝色主题
st.set_page_config(
    page_title="洪水预测与预警系统",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义蓝色主题CSS
st.markdown("""
<style>
    /* 主色调 - 蓝色 */
    :root {
        --primary: #1E88E5;
        --primary-dark: #1565C0;
        --primary-light: #42A5F5;
        --secondary: #0D47A1;
    }

    /* 侧边栏样式 */
    [data-testid="stSidebar"] {
        background-color: #0D47A1 !important;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: white;
    }

    /* 侧边栏导航按钮 */
    .st-emotion-cache-1kyxreq {
        background-color: rgba(255, 255, 255, 0.1);
        border-radius: 8px;
    }

    /* 侧边栏标题 */
    [data-testid="stSidebar"] h1 {
        color: white !important;
    }

    /* 主页面标题 */
    h1 {
        color: #1565C0 !important;
    }

    /* 指标卡片 */
    [data-testid="stMetricValue"] {
        color: #1E88E5 !important;
    }

    /* 成功/警告/错误消息 */
    .stSuccess {
        background-color: #E3F2FD;
    }

    /* 按钮样式 */
    .stButton > button {
        background-color: #1E88E5;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
    }

    .stButton > button:hover {
        background-color: #1565C0;
    }

    /* 卡片样式 */
    .stat-card {
        background-color: #E3F2FD;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #1E88E5;
    }

    /* 预警卡片 */
    .warning-blue {
        border-left-color: #2196F3;
        background-color: #E3F2FD;
    }
    .warning-yellow {
        border-left-color: #FFC107;
        background-color: #FFF8E1;
    }
    .warning-orange {
        border-left-color: #FF9800;
        background-color: #FFF3E0;
    }
    .warning-red {
        border-left-color: #F44336;
        background-color: #FFEBEE;
    }

    /* 数据表格 */
    [data-testid="stDataFrame"] {
        border: 1px solid #E3F2FD;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ============ 初始化服务 ============
@st.cache_resource
def get_services():
    data_service = DataCollectionService()
    predictor = FloodPredictor()
    warning_service = WarningService()
    return data_service, predictor, warning_service

data_service, predictor, warning_service = get_services()

# ============ 侧边栏导航 ============
st.sidebar.markdown("<h1 style='text-align: center; color: white;'>🌊 洪水预警系统</h1>", unsafe_allow_html=True)
st.sidebar.markdown("<hr style='border-color: rgba(255,255,255,0.3)'>", unsafe_allow_html=True)

# 导航菜单 - 页面选择
page = st.sidebar.selectbox(
    "📋 功能导航",
    [
        "🏠 系统概览",
        "📊 实时监测",
        "📈 预测分析",
        "⚠️ 预警管理"
    ],
    index=0
)

st.sidebar.markdown("<hr style='border-color: rgba(255,255,255,0.3)'>", unsafe_allow_html=True)

# 侧边栏 - 系统状态
st.sidebar.markdown("<h3 style='color: white;'>📊 系统状态</h3>", unsafe_allow_html=True)
st.sidebar.markdown(f"""
<div style='color: white; font-size: 0.9em;'>
    <p>🟢 系统状态: 运行中</p>
    <p>📡 监测站点: {len(MONITOR_STATIONS)}个</p>
    <p>⚠️ 活跃预警: {len(warning_service.get_active_warnings())}个</p>
    <p>🕐 更新时间: {datetime.now().strftime('%H:%M:%S')}</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("<hr style='border-color: rgba(255,255,255,0.3)'>", unsafe_allow_html=True)

# 侧边栏 - 监测站点快速选择
st.sidebar.markdown("<h3 style='color: white;'>📍 监测站点</h3>", unsafe_allow_html=True)
station_names = {s["id"]: s["name"] for s in MONITOR_STATIONS}
for station in MONITOR_STATIONS:
    st.sidebar.markdown(f"""
    <div style='color: white; font-size: 0.85em; padding: 5px 0;'>
        <span style='background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 4px;'>
            {station['id']}
        </span>
        {station['name']}
    </div>
    """, unsafe_allow_html=True)

# ============ 系统概览页面 ============
if page == "🏠 系统概览":
    st.header("系统概览")
    st.markdown("欢迎使用基于LSTM-Attention的洪水预测与预警系统")

    # 统计指标
    col1, col2, col3, col4 = st.columns(4)

    stations_count = len(MONITOR_STATIONS)
    active_warnings = warning_service.get_active_warnings()
    active_warning_count = len(active_warnings)

    col1.metric("监测站点", f"{stations_count}")
    col2.metric("活跃预警", f"{active_warning_count}")
    col3.metric("传感器数量", f"{stations_count * 3}")
    col4.metric("系统状态", "🟢 运行中")

    st.divider()

    # 监测站点分布
    st.subheader("监测站点分布")
    stations_df = pd.DataFrame(MONITOR_STATIONS)
    st.dataframe(stations_df, use_container_width=True, hide_index=True)

    st.divider()

    # 预警等级说明
    st.subheader("预警等级说明")
    warning_cols = st.columns(4)
    levels = [
        ("蓝色预警", "🌐", "#2196F3", "水位 > 15m"),
        ("黄色预警", "🟡", "#FFC107", "水位 > 20m"),
        ("橙色预警", "🟠", "#FF9800", "水位 > 25m"),
        ("红色预警", "🔴", "#F44336", "水位 > 30m"),
    ]
    for i, (name, icon, color, desc) in enumerate(levels):
        with warning_cols[i]:
            st.markdown(f"""
            <div style="padding: 15px; background-color: {color}15; border-radius: 10px; 
                        text-align: center; border: 1px solid {color}40;">
                <h3 style="color: {color};">{icon} {name}</h3>
                <p style="color: #666;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)

# ============ 实时监测页面 ============
elif page == "📊 实时监测":
    st.header("实时监测数据")

    # 刷新按钮
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 刷新数据", type="primary"):
            st.rerun()

    # 获取实时数据
    realtime_data = data_service.collect_realtime_data()

    # 站点选择
    station_ids = [s["id"] for s in MONITOR_STATIONS]
    selected_station = st.selectbox("选择监测站点", station_ids)

    # 查找选中站点的数据
    station_data = next((s for s in realtime_data if s["station_id"] == selected_station), None)

    if station_data:
        # 站点信息
        station_info = next((s for s in MONITOR_STATIONS if s["id"] == selected_station), {})
        st.markdown(f"**站点名称:** {station_info.get('name', '未知')} | **位置:** ({station_info.get('lat', '-')}, {station_info.get('lng', '-')})")

        st.divider()

        # 各传感器数据展示
        readings = station_data.get("readings", [])

        for reading in readings:
            data_type = reading.get("data_type", "unknown")

            if data_type == "water_level":
                value = reading.get("value", 0)
                unit = reading.get("unit", "m")
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric(f"💧 水位", f"{value} {unit}")
                    if value > 25:
                        st.error("⚠️ 水位过高!")
                    elif value > 20:
                        st.warning("⚡ 水位偏高")
                    else:
                        st.success("✅ 水位正常")

            elif data_type == "rainfall":
                value = reading.get("value", 0)
                unit = reading.get("unit", "mm")
                st.metric(f"🌧️ 降雨量", f"{value} {unit}")

            elif data_type == "water_quality":
                params = reading.get("parameters", {})
                st.metric("🔬 水质参数",
                    f"pH: {params.get('ph', '-')} | 浊度: {params.get('turbidity', '-')} NTU")

    st.divider()

    # 所有站点实时数据概览表格
    st.subheader("所有站点实时数据概览")

    all_stations_data = []
    for station_id in station_ids:
        s_data = next((s for s in realtime_data if s["station_id"] == station_id), {})
        readings = s_data.get("readings", [])

        water_level = next((r.get("value") for r in readings if r.get("data_type") == "water_level"), "-")
        rainfall = next((r.get("value") for r in readings if r.get("data_type") == "rainfall"), "-")

        station_name = next((s.get("name", "未知") for s in MONITOR_STATIONS if s.get("id") == station_id), "未知")

        all_stations_data.append({
            "站点ID": station_id,
            "站点名称": station_name,
            "水位(m)": water_level,
            "降雨量(mm)": rainfall,
            "更新时间": datetime.now().strftime("%H:%M:%S")
        })

    df = pd.DataFrame(all_stations_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

# ============ 预测分析页面 ============
elif page == "📈 预测分析":
    st.header("洪水风险预测")

    # 站点选择
    station_ids = [s["id"] for s in MONITOR_STATIONS]
    selected_station = st.selectbox("选择预测站点", station_ids, key="pred_station")

    # 预测按钮
    if st.button("🔮 执行预测", type="primary"):
        with st.spinner("正在进行洪水风险预测..."):
            # 构造模拟历史数据
            dates = pd.date_range(end=datetime.now(), periods=72, freq="h")
            import numpy as np
            sample_data = pd.DataFrame({
                "location_id": selected_station,
                "timestamp": dates,
                "water_level": np.random.uniform(8, 18, 72),
                "flow_rate": np.random.uniform(100, 500, 72),
                "rainfall": np.random.uniform(0, 30, 72),
                "temperature": np.random.uniform(15, 35, 72),
            })

            # 执行预测
            result = predictor.predict_flood_risk(sample_data)

            if "error" not in result:
                st.success("预测完成!")

                # 预测结果展示
                col1, col2, col3, col4 = st.columns(4)

                risk_level = result.get("risk_level", 0)
                risk_name = result.get("risk_name", "未知")
                max_level = result.get("max_predicted_water_level", 0)
                predict_time = result.get("predict_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                col1.metric("风险等级", risk_name)
                col2.metric("最高预测水位", f"{max_level:.2f} m")
                col3.metric("预测时间", predict_time)
                col4.metric("预测站点", selected_station)

                # 自动生成预警
                if risk_level > 0:
                    warning = warning_service.generate_flood_warning(result)
                    if warning:
                        st.warning(f"⚠️ {warning.get('title', '预警生成')}")

                st.divider()

                # 预测水位时序图
                st.subheader("预测水位变化趋势")

                pred_hours = list(range(1, 25))
                base_level = max_level * 0.7
                pred_levels = [base_level + (max_level - base_level) * (1 - abs(h - 12)/12) + np.random.uniform(-0.5, 0.5) for h in pred_hours]

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=pred_hours,
                    y=pred_levels,
                    mode="lines+markers",
                    name="预测水位",
                    line=dict(color="#1E88E5", width=2),
                    marker=dict(size=6)
                ))

                fig.add_hline(y=20, line_dash="dot", line_color="orange", annotation_text="警戒水位 20m")
                fig.add_hline(y=25, line_dash="dot", line_color="red", annotation_text="危险水位 25m")

                fig.update_layout(
                    title="未来24小时水位预测",
                    xaxis_title="预测小时",
                    yaxis_title="水位 (m)",
                    template="plotly_white",
                    height=400
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error(result.get("error", "预测失败"))

# ============ 预警管理页面 ============
elif page == "⚠️ 预警管理":
    st.header("预警信息管理")

    # 当前预警
    active_warnings = warning_service.get_active_warnings()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("当前活跃预警", len(active_warnings))
    with col2:
        if st.button("🔄 刷新预警"):
            st.rerun()

    st.divider()

    if active_warnings:
        st.subheader("活跃预警列表")

        for warning in active_warnings:
            level = warning.get("warning_level", 0)
            level_names = {4: "🔴 红色", 3: "🟠 橙色", 2: "🟡 黄色", 1: "🌐 蓝色"}
            level_name = level_names.get(level, "❓ 未知")

            colors = {4: "#FFEBEE", 3: "#FFF3E0", 2: "#FFF8E1", 1: "#E3F2FD"}
            border_colors = {4: "#F44336", 3: "#FF9800", 2: "#FFC107", 1: "#2196F3"}
            bg_color = colors.get(level, "#F5F5F5")
            border_color = border_colors.get(level, "#9E9E9E")

            with st.container():
                st.markdown(f"""
                <div style="padding: 15px; border-left: 5px solid {border_color}; 
                            background-color: {bg_color}; border-radius: 5px; margin: 10px 0;">
                    <h4>{level_name} - {warning.get('title', '预警')}</h4>
                    <p>{warning.get('content', '')}</p>
                    <p style="color: #666; font-size: 0.85em;">
                        影响区域: {warning.get('affected_location', '未知')} |
                        发布时间: {warning.get('publish_time', '-')} |
                        过期时间: {warning.get('expire_time', '-')}
                    </p>
                </div>
                """, unsafe_allow_html=True)

                if st.button(f"解除预警", key=f"cancel_{warning.get('id')}"):
                    warning_service.cancel_warning(warning.get('id'))
                    st.success("预警已解除")
                    st.rerun()
    else:
        st.info("当前没有活跃预警 ✓")

    st.divider()

    # 创建新预警
    st.subheader("创建预警")

    with st.form("create_warning_form"):
        warning_type = st.selectbox("预警类型", [(1, "洪水"), (2, "干旱"), (3, "污染")], format_func=lambda x: x[1])
        warning_level = st.select_slider("预警等级", [1, 2, 3, 4], value=2)
        title = st.text_input("预警标题", placeholder="请输入预警标题")
        content = st.text_area("预警内容", placeholder="请输入预警详情")
        location = st.text_input("影响区域", placeholder="请输入影响区域")

        if st.form_submit_button("发布预警", type="primary"):
            if title and content:
                new_warning = warning_service.create_warning(
                    warning_type=warning_type[0],
                    warning_level=warning_level,
                    title=title,
                    content=content,
                    affected_location=location or "未知区域"
                )
                warning_service.send_warning(new_warning)
                st.success(f"预警发布成功! ID: {new_warning.get('id')}")
                st.rerun()
            else:
                st.error("请填写标题和内容")

# 页脚
st.divider()
st.markdown("""
<div style="text-align: center; color: #666;">
    <p>基于LSTM-Attention的洪水预测与预警系统 | 第3组 | 智慧水利应用课程作业</p>
    <p>技术栈: Streamlit + FastAPI + PyTorch</p>
</div>
""", unsafe_allow_html=True)