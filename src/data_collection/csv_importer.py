"""CSV 水文数据导入器 —— 灵活列映射 + 自动嗅探 + 清洗入库"""

import csv
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from src.data_processing.data_validator import DataValidator
from src.data_processing.batch_processor import BatchDataProcessor
from src.config.settings import CSV_IMPORT_CONFIG, MONITOR_STATIONS

logger = logging.getLogger(__name__)

# 系统标准字段
STANDARD_FIELDS = [
    "station_id", "timestamp", "water_level", "flow_rate",
    "rainfall", "temperature", "ph", "turbidity", "dissolved_oxygen",
]
REQUIRED_FIELDS = ["station_id", "timestamp", "water_level"]


class CsvImporter:
    """CSV 数据导入器 —— 支持灵活列映射、自动嗅探和单位转换"""

    UNIT_CONVERSIONS = {
        "cm_to_m": lambda x: x / 100.0,
        "mm_to_m": lambda x: x / 1000.0,
        "none": lambda x: x,
    }

    def __init__(self):
        self.validator = DataValidator()
        self.processor = BatchDataProcessor()
        self.import_history: List[dict] = []
        self._templates_dir = Path(CSV_IMPORT_CONFIG["templates_dir"])
        self._templates_dir.mkdir(parents=True, exist_ok=True)

    def sniff(self, filepath: str) -> dict:
        """自动检测 CSV 文件格式
        Returns:
            {"encoding": str, "delimiter": str, "has_header": bool, "headers": [...], "row_count": int}
        """
        result = {
            "encoding": "utf-8",
            "delimiter": ",",
            "has_header": True,
            "headers": [],
            "row_count": 0,
            "sample_rows": [],
        }

        # 尝试检测编码
        for enc in CSV_IMPORT_CONFIG["supported_encodings"]:
            try:
                with open(filepath, "r", encoding=enc) as f:
                    content = f.read(5000)
                result["encoding"] = enc
                break
            except (UnicodeDecodeError, LookupError):
                continue

        # 检测分隔符
        try:
            with open(filepath, "r", encoding=result["encoding"]) as f:
                sample = f.read(8192)
            sniffer = csv.Sniffer()
            result["delimiter"] = sniffer.sniff(sample).delimiter
            result["has_header"] = sniffer.has_header(sample)
        except Exception:
            pass  # 使用默认逗号分隔符

        # 读取表头和行数
        try:
            df = pd.read_csv(
                filepath,
                encoding=result["encoding"],
                sep=result["delimiter"],
                nrows=5,
            )
            result["headers"] = list(df.columns)
            result["sample_rows"] = df.head(3).to_dict("records")

            # 计数总行数
            with open(filepath, "r", encoding=result["encoding"]) as f:
                result["row_count"] = sum(1 for _ in f) - (1 if result["has_header"] else 0)
        except Exception as e:
            logger.error("CSV 读取失败: %s", e)
            result["error"] = str(e)

        return result

    def load_with_mapping(self, filepath: str, mapping: dict) -> Tuple[List[dict], dict]:
        """根据列映射加载 CSV 并转换为标准格式
        Args:
            filepath: CSV 文件路径
            mapping: 映射配置字典，包含 column_mapping, datetime_format, skip_rows 等
        Returns:
            (records, summary): 标准格式记录列表和摘要信息
        """
        column_mapping = mapping.get("column_mapping", {})
        datetime_format = mapping.get("datetime_format", None)
        skip_rows = mapping.get("skip_rows", 0)
        encoding = mapping.get("encoding", "utf-8")
        delimiter = mapping.get("delimiter", ",")
        unit_conversions = mapping.get("unit_conversions", {})
        station_id_mapping = mapping.get("station_id_mapping", {})

        # 反转映射：CSV列名 -> 标准字段名
        reverse_mapping = {v: k for k, v in column_mapping.items()}

        # 检查必选字段
        missing_required = [
            f for f in REQUIRED_FIELDS
            if f not in column_mapping
        ]
        if missing_required:
            raise ValueError(f"映射配置缺少必选字段: {missing_required}")

        # 读取 CSV
        df = pd.read_csv(
            filepath,
            encoding=encoding,
            sep=delimiter,
            skiprows=skip_rows,
        )

        summary = {
            "file": filepath,
            "total_rows": len(df),
            "mapped_columns": list(column_mapping.keys()),
            "warnings": [],
        }

        # 重命名列
        df.rename(columns=reverse_mapping, inplace=True)

        # 只保留标准字段
        keep_cols = [c for c in STANDARD_FIELDS if c in df.columns]
        df = df[keep_cols]

        # 站点ID映射
        if station_id_mapping:
            if "station_id" in df.columns:
                df["station_id"] = df["station_id"].map(
                    lambda x: station_id_mapping.get(str(x), x)
                )
                mapped_count = df["station_id"].isin(station_id_mapping.values()).sum()
                summary["station_id_mapped"] = int(mapped_count)

        # 时间戳解析
        if "timestamp" in df.columns:
            try:
                if datetime_format:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], format=datetime_format)
                else:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
            except Exception as e:
                summary["warnings"].append(f"时间戳解析部分失败: {e}")
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

            invalid_ts = df["timestamp"].isna().sum()
            if invalid_ts > 0:
                summary["warnings"].append(f"{invalid_ts} 行时间戳无效，已跳过")
            df = df.dropna(subset=["timestamp"])

        # 单位转换
        for field, conv_name in unit_conversions.items():
            if field in df.columns and conv_name in self.UNIT_CONVERSIONS:
                conv_func = self.UNIT_CONVERSIONS[conv_name]
                df[field] = pd.to_numeric(df[field], errors="coerce")
                df[field] = df[field].apply(conv_func)
                summary["warnings"].append(f"已对 '{field}' 执行单位转换: {conv_name}")

        summary["valid_rows"] = len(df)

        return df.to_dict("records"), summary

    def import_and_clean(self, filepath: str, mapping: dict) -> dict:
        """完整导入流程：加载 -> 清洗 -> 返回结果
        Args:
            filepath: CSV 文件路径
            mapping: 映射配置
        Returns:
            {"status": "success"/"error", "summary": {...}, "cleaned_count": int, ...}
        """
        # Step 1: 加载并映射
        try:
            records, load_summary = self.load_with_mapping(filepath, mapping)
        except Exception as e:
            return {
                "status": "error",
                "message": f"CSV加载失败: {e}",
                "summary": {},
            }

        if len(records) == 0:
            return {
                "status": "error",
                "message": "映射后无有效数据",
                "summary": load_summary,
            }

        # Step 2: 清洗（复用现有管道）
        try:
            clean_result = self.processor.process_pipeline(records)
        except Exception as e:
            logger.warning("自动清洗失败，返回原始数据: %s", e)
            clean_result = {"status": "partial", "message": str(e)}

        # Step 3: 记录导入历史
        history_entry = {
            "time": datetime.now().isoformat(),
            "file": filepath,
            "template": mapping.get("template_name", "unknown"),
            "total_rows": load_summary.get("total_rows", 0),
            "valid_rows": load_summary.get("valid_rows", 0),
            "status": clean_result.get("status", "unknown"),
        }
        self.import_history.append(history_entry)

        return {
            "status": clean_result.get("status", "success"),
            "load_summary": load_summary,
            "clean_summary": clean_result.get("clean_summary", {}),
            "feature_count": clean_result.get("feature_count", 0),
            "dataset_samples": clean_result.get("dataset_samples", 0),
        }

    # ---- 映射模板管理 ----

    def save_template(self, template: dict) -> str:
        """保存映射模板到文件"""
        name = template.get("template_name", "untitled")
        filename = f"{name}.json"
        filepath = self._templates_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        return str(filepath)

    def list_templates(self) -> List[dict]:
        """列出所有已保存的映射模板"""
        templates = []
        if self._templates_dir.exists():
            for f in self._templates_dir.glob("*.json"):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        templates.append(json.load(fp))
                except Exception:
                    continue
        return templates

    def get_import_history(self, limit: int = 50) -> List[dict]:
        """获取导入历史"""
        return self.import_history[-limit:]
