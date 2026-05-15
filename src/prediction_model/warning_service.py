"""预警服务模块 —— 预警信息生成与发送"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from src.config.settings import WARNING_THRESHOLDS


class WarningService:
    """预警服务 —— 预警级别判定、信息生成与发送"""

    def __init__(self):
        self.warning_history = []
        self.current_warnings = {}
        self.channels = ["system_notification", "app_push", "sms"]

    def create_warning(
        self,
        warning_type: int,
        warning_level: int,
        title: str,
        content: str,
        affected_location: str,
        expire_hours: int = 24,
    ) -> Dict:
        """创建预警信息"""
        warning = {
            "id": f"WARN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{hash(title) % 1000:03d}",
            "warning_type": warning_type,
            "warning_level": warning_level,
            "title": title,
            "content": content,
            "affected_location": affected_location,
            "publish_time": datetime.now().isoformat(),
            "expire_time": (datetime.now() + timedelta(hours=expire_hours)).isoformat(),
            "status": 1,
        }
        self.warning_history.append(warning)
        self.current_warnings[warning["id"]] = warning
        return warning

    def send_warning(self, warning: Dict, channels: Optional[List[str]] = None):
        """发送预警信息到指定渠道"""
        if channels is None:
            channels = self.channels

        sent_results = []
        for channel in channels:
            result = self._send_to_channel(warning, channel)
            sent_results.append({"channel": channel, "success": result})

        return {"warning_id": warning["id"], "sent_results": sent_results}

    def _send_to_channel(self, warning: Dict, channel: str) -> bool:
        """模拟向特定渠道发送预警"""
        print(
            f"[{channel}] 发送预警: {warning['title']} | "
            f"等级: {warning['warning_level']} | "
            f"区域: {warning['affected_location']}"
        )
        return True

    def generate_flood_warning(
        self, prediction_result: Dict
    ) -> Optional[Dict]:
        """根据预测结果自动生成洪水预警"""
        risk_level = prediction_result.get("risk_level", 0)
        if risk_level <= 0:
            return None

        station_name = prediction_result.get("station_name", "未知站点")
        max_level = prediction_result.get("max_predicted_water_level", 0)
        risk_name = prediction_result.get("risk_name", "未知")

        title_map = {
            4: f"【红色预警】{station_name}即将发生严重洪水灾害",
            3: f"【橙色预警】{station_name}洪水风险较高",
            2: f"【黄色预警】{station_name}存在洪水风险",
            1: f"【蓝色预警】{station_name}水位偏高，注意防范",
        }

        content_map = {
            4: f"预计{station_name}水位将达{max_level}m，超过警戒线，"
               f"可能引发严重洪涝灾害。请立即组织人员撤离，启动最高级别应急响应。",
            3: f"预计{station_name}水位将达{max_level}m，接近警戒线，"
               f"存在较高洪水风险。请做好防洪准备，密切关注水位变化。",
            2: f"预计{station_name}水位将达{max_level}m，"
               f"存在一定洪水风险。请留意后续预警信息。",
            1: f"预计{station_name}水位将达{max_level}m，水位偏高，"
               f"请保持关注。",
        }

        title = title_map.get(risk_level, f"{station_name}洪水预警")
        content = content_map.get(risk_level, f"{station_name}当前水位{max_level}m")

        warning = self.create_warning(
            warning_type=1,
            warning_level=risk_level,
            title=title,
            content=content,
            affected_location=prediction_result.get("location_id", station_name),
        )
        return warning

    def cancel_warning(self, warning_id: str) -> bool:
        """取消预警"""
        if warning_id in self.current_warnings:
            self.current_warnings[warning_id]["status"] = 0
            return True
        return False

    def get_active_warnings(self) -> List[Dict]:
        """获取当前生效的预警"""
        now = datetime.now()
        active = []
        for wid, warning in self.current_warnings.items():
            expire_time = datetime.fromisoformat(warning["expire_time"])
            if warning["status"] == 1 and expire_time > now:
                active.append(warning)
        return active
