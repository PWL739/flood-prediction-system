"""批量数据处理工具 —— 历史数据清洗、特征生成、批量导入"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from src.data_processing.data_validator import DataValidator, OutlierDetector
from src.data_processing.data_preprocessor import DataPreprocessor


class BatchDataProcessor:
    """批量数据处理工具 —— 支持历史数据清洗与特征生成"""

    def __init__(self):
        self.validator = DataValidator()
        self.preprocessor = DataPreprocessor()
        self.processing_log = []

    def load_from_json(self, filepath: str) -> List[Dict]:
        """从JSON文件加载历史数据"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.processing_log.append({
            "action": "load", "file": filepath,
            "records": len(data) if isinstance(data, list) else "single",
            "time": datetime.now().isoformat(),
        })
        return data

    def load_from_csv(self, filepath: str) -> pd.DataFrame:
        """从CSV文件加载历史数据"""
        df = pd.read_csv(filepath, parse_dates=["timestamp"])
        self.processing_log.append({
            "action": "load_csv", "file": filepath,
            "rows": len(df), "time": datetime.now().isoformat(),
        })
        return df

    def clean_historical_data(
        self,
        records: List[Dict],
        remove_outliers: bool = True,
        fill_missing: bool = True,
    ) -> Tuple[List[Dict], Dict]:
        """
        清洗历史数据
        Returns:
            (cleaned_records, summary) 清洗后的数据和统计摘要
        """
        initial_count = len(records)

        # Step 1: 批量验证
        validation_results = self.validator.batch_validate_with_3sigma(records)
        valid_records = self.validator.filter_valid_data(validation_results)

        summary = {
            "initial_count": initial_count,
            "valid_count": len(valid_records),
            "removed_count": initial_count - len(valid_records),
            "issues_found": {},
        }

        for r in validation_results:
            for issue in r["issues"]:
                issue_type = issue.split(":")[0] if ":" in issue else issue
                summary["issues_found"][issue_type] = \
                    summary["issues_found"].get(issue_type, 0) + 1

        # Step 2: 转换为DataFrame处理缺失值
        if valid_records:
            df = pd.DataFrame(valid_records)
            if fill_missing and not df.empty:
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                df[numeric_cols] = df[numeric_cols].interpolate(
                    method="linear", limit_direction="both"
                )
                df = df.bfill().ffill()
                valid_records = df.to_dict("records")

        self.processing_log.append({
            "action": "clean",
            "initial": initial_count,
            "valid": len(valid_records),
            "time": datetime.now().isoformat(),
        })

        return valid_records, summary

    def generate_features_from_records(
        self, records: List[Dict]
    ) -> pd.DataFrame:
        """从记录列表生成特征"""
        df = pd.DataFrame(records)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")

        df = self.preprocessor.handle_missing_values(df, method="interpolate")
        df = self.preprocessor.generate_features(df)
        return df

    def prepare_ml_dataset(
        self,
        df: pd.DataFrame,
        target_col: str = "water_level",
        multi_step: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """准备机器学习数据集（72小时窗口）"""
        if multi_step:
            return self.preprocessor.prepare_multi_step_data(df, target_col)
        return self.preprocessor.prepare_training_data(df, target_col)

    def process_pipeline(
        self,
        records: List[Dict],
        target_col: str = "water_level",
    ) -> Dict:
        """
        完整处理流水线：清洗 → 特征工程 → 数据集构建
        """
        # 清洗
        cleaned, clean_summary = self.clean_historical_data(records)

        if len(cleaned) < 72:
            return {
                "status": "error",
                "message": f"清洗后数据不足（{len(cleaned)}条，需要≥72条）",
                "clean_summary": clean_summary,
            }

        # 特征工程
        feature_df = self.generate_features_from_records(cleaned)

        # 构建数据集
        try:
            X, y = self.prepare_ml_dataset(feature_df, target_col, multi_step=True)
            dataset_shape = {"X": X.shape, "y": y.shape}
        except Exception as e:
            X, y = self.prepare_ml_dataset(feature_df, target_col, multi_step=False)
            dataset_shape = {"X": X.shape, "y": y.shape}

        result = {
            "status": "success",
            "clean_summary": clean_summary,
            "feature_count": len(feature_df.columns),
            "dataset_samples": len(X),
            "dataset_shape": dataset_shape,
            "processing_log": self.processing_log,
        }

        return result

    def export_clean_data(self, records: List[Dict], filepath: str):
        """导出清洗后的数据"""
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2, default=str)
        self.processing_log.append({
            "action": "export", "file": str(output_path),
            "records": len(records), "time": datetime.now().isoformat(),
        })

    def get_processing_stats(self) -> Dict:
        """获取处理统计"""
        return {
            "total_actions": len(self.processing_log),
            "last_action": self.processing_log[-1] if self.processing_log else None,
        }
