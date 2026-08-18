#!/usr/bin/env python3
"""
datacleaner.py — 数据清洗工具

清洗规则:
  1. 数值型: 非数值置空、去空格、全角数字转半角
  2. 分类型: 去空格、全角字符转半角、统一空白值为 None
  3. IQR 异常值检测 (仅标记，不删除)
  4. 重复行检测 (仅标记，不删除)
  5. 缺失值统计报告
  6. 所有异常记录到 anomalies.csv

用法:
  python datacleaner.py <输入 CSV> [输出 CSV]

示例:
  python datacleaner.py data_cleaned.csv
  python datacleaner.py data_cleaned.csv final.csv
"""

import sys
import os
import argparse
import csv
import json
from datetime import datetime

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# 全角/半角工具函数
# ---------------------------------------------------------------------------

FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
FULLWIDTH_ALPHA = str.maketrans(
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz",
)
FULLWIDTH_PUNCT = str.maketrans("，。！？（）【】“”‘’；：、～", ",.!?()[]\"\"'';:,~")
FULLWIDTH_SPACE = str.maketrans("　", " ")


def to_halfwidth(text: str) -> str:
    """全角 → 半角 (数字、字母、标点、空格)."""
    if not isinstance(text, str):
        return text
    text = text.translate(FULLWIDTH_DIGITS)
    text = text.translate(FULLWIDTH_ALPHA)
    text = text.translate(FULLWIDTH_PUNCT)
    text = text.translate(FULLWIDTH_SPACE)
    return text


# ---------------------------------------------------------------------------
# 类型识别 (与 dataloader.py 保持一致)
# ---------------------------------------------------------------------------

def infer_variable_type(series: pd.Series, cat_threshold: float = 0.05,
                        cat_max_unique: int = 30) -> str:
    """判断 Series 是 'numeric' 还是 'categorical'."""
    n = len(series)
    if n == 0:
        return "categorical"

    clean = series.dropna()
    if len(clean) == 0:
        return "categorical"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    if pd.api.types.is_bool_dtype(series):
        return "categorical"

    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        numeric_count = pd.to_numeric(clean, errors='coerce').notna().sum()
        ratio_numeric = numeric_count / len(clean)
        if ratio_numeric >= 0.9:
            numeric_series = pd.to_numeric(clean, errors='coerce')
            return _decide_numeric_or_cat(numeric_series, n, cat_threshold)
        return "categorical"

    if pd.api.types.is_numeric_dtype(series):
        return _decide_numeric_or_cat(clean, n, cat_threshold, cat_max_unique)

    return "categorical"


def _decide_numeric_or_cat(series: pd.Series, total_n: int,
                           cat_threshold: float,
                           cat_max_unique: int = 30) -> str:
    if len(series) == 0:
        return "categorical"
    n_unique = series.nunique()
    ratio_unique = n_unique / total_n
    if n_unique <= 1:
        return "categorical"
    if n_unique == 2:
        return "categorical"
    if ratio_unique <= cat_threshold:
        return "categorical"
    if n_unique > cat_max_unique:
        return "numeric"
    small_cutoff = max(3, total_n * 0.5)
    if total_n <= 50 and n_unique >= small_cutoff:
        return "numeric"
    if n_unique > 10 and ratio_unique > cat_threshold:
        return "numeric"
    return "categorical"


# ---------------------------------------------------------------------------
# 异常记录器
# ---------------------------------------------------------------------------

class AnomalyLogger:
    """收集所有清洗异常，最终写出到 CSV."""

    def __init__(self):
        self.records = []  # list[dict]

    def add(self, row_idx: int, column: str, issue: str,
            original: str, cleaned: str, detail: str = ""):
        self.records.append({
            "row_index": row_idx,
            "column": column,
            "issue": issue,
            "original_value": str(original),
            "cleaned_value": str(cleaned),
            "detail": detail,
        })

    def write(self, path: str):
        if not self.records:
            # 写一个空的报头
            pd.DataFrame(columns=[
                "row_index", "column", "issue",
                "original_value", "cleaned_value", "detail"
            ]).to_csv(path, index=False, encoding="utf-8-sig")
            print(f"  ✅ 无任何异常，仍已生成: {path} (空表头)")
            return
        df = pd.DataFrame(self.records)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  📝 异常日志已写入: {path} ({len(self.records)} 条)")


# ---------------------------------------------------------------------------
# 清洗引擎
# ---------------------------------------------------------------------------

def _reclassify_numeric_overrides(df: pd.DataFrame,
                                   type_map: dict) -> dict:
    """二次判断：分类列中如果 ≥70% 的值可转数字，重新分类为 numeric.
    
    dataloader 在原始脏数据上做类型推断，混杂了非数值的数值列可能
    被误判为分类。此处先用 strip + to_halfwidth 做基础清洗，然后
    检查可转数字的比例。
    """
    override = dict(type_map)
    for col, t in type_map.items():
        if t != "categorical":
            continue
        series = df[col].dropna()
        if len(series) < 4:
            continue
        # 先做基础清洗（去空格、全角转半角）再判断
        cleaned = series.astype(str).str.strip().apply(to_halfwidth)
        numeric_clean = pd.to_numeric(cleaned, errors='coerce')
        ratio = numeric_clean.notna().sum() / len(series)
        if ratio >= 0.7:
            override[col] = "numeric"
    return override


def clean_dataframe(df: pd.DataFrame, anomaly_logger: AnomalyLogger,
                    outlier_iqr_mult: float = 1.5,
                    verbose: bool = True) -> pd.DataFrame:
    """对 DataFrame 执行全部清洗，返回清洗后的副本。"""

    # 推断类型
    type_map = {}
    for col in df.columns:
        type_map[col] = infer_variable_type(df[col])

    # 二次判断：误判的数值列纠正
    type_map = _reclassify_numeric_overrides(df, type_map)

    numeric_cols = [c for c, t in type_map.items() if t == "numeric"]
    cat_cols = [c for c, t in type_map.items() if t == "categorical"]
    dt_cols = [c for c, t in type_map.items() if t == "datetime"]

    if verbose:
        print(f"\n{'='*60}")
        print(f" 🔍 变量类型 (含二次矫正): 数值 {len(numeric_cols)} 列"
              f" | 分类 {len(cat_cols)} 列"
              f" | 日期 {len(dt_cols)} 列")
        reclassified = [c for c in numeric_cols if type_map[c] == "numeric"
                        and infer_variable_type(df[c]) != "numeric"]
        if reclassified:
            print(f"     ⚡ 二次矫正: {reclassified}")
        print(f"{'='*60}")

    df = df.copy()

    # ── Step 1: 缺失统计 ──
    if verbose:
        missing_counts = df.isna().sum()
        missing_cols = missing_counts[missing_counts > 0]
        if len(missing_cols) > 0:
            print(f"\n  ⚠️  缺失值统计:")
            for col, cnt in missing_cols.items():
                pct = cnt / len(df) * 100
                print(f"     {col:<20}  {cnt:>5} 行缺失 ({pct:.1f}%)")
                anomaly_logger.add(
                    row_idx=-1, column=col, issue="missing_value",
                    original="", cleaned="", detail=f"共 {cnt} 行缺失 ({pct:.1f}%)"
                )
        else:
            print(f"\n  ✅ 无缺失值")

    # ── Step 2: 数值型列清洗 ──
    if verbose and numeric_cols:
        print(f"\n  🔢 数值型列清洗:")

    for col in numeric_cols:
        col_anomalies = 0
        for i in range(len(df)):
            raw = df.at[i, col]

            # 已经是 NaN 的跳过 (但记录缺失 — 已在 Step 1 中统一记录)
            if pd.isna(raw):
                continue

            raw_str = str(raw)

            # 2a. 去空格
            stripped = raw_str.strip()

            # 2b. 全角数字转半角
            half = to_halfwidth(stripped)

            # 2c. 尝试转数值
            try:
                val = float(half)
                if half != raw_str:
                    col_anomalies += 1
                    anomaly_logger.add(
                        row_idx=i, column=col, issue="numeric_format_fixed",
                        original=raw_str, cleaned=half,
                        detail="去空格/全角转半角后数值不变"
                    )
                df.at[i, col] = val
            except (ValueError, TypeError):
                # 不是合法数值 → 置空
                col_anomalies += 1
                anomaly_logger.add(
                    row_idx=i, column=col, issue="non_numeric_emptied",
                    original=raw_str, cleaned="",
                    detail="非数值内容，已置空"
                )
                df.at[i, col] = np.nan

        if col_anomalies > 0 and verbose:
            print(f"     {col:<20}  修复 {col_anomalies} 处")

    # ── Step 2b: IQR 异常值检测 (仅标记，不修改) ──
    if numeric_cols:
        if verbose:
            print(f"\n  📊 IQR 异常值检测 (系数={outlier_iqr_mult}):")
        any_outliers = False
        for col in numeric_cols:
            vals = df[col].dropna()
            if len(vals) < 4:
                continue
            q1 = vals.quantile(0.25)
            q3 = vals.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - outlier_iqr_mult * iqr
            upper = q3 + outlier_iqr_mult * iqr
            outlier_mask = (vals < lower) | (vals > upper)
            outlier_count = outlier_mask.sum()
            if outlier_count > 0:
                any_outliers = True
                outlier_indices = outlier_mask[outlier_mask].index.tolist()
                if verbose:
                    print(f"     {col:<20}  发现 {outlier_count} 个异常值"
                          f" (范围 [{lower:.2f}, {upper:.2f}])")
                for idx in outlier_indices[:20]:  # 最多记录 20 个
                    original_val = str(df.at[idx, col])
                    anomaly_logger.add(
                        row_idx=idx, column=col, issue="outlier_iqr",
                        original=original_val, cleaned=original_val,
                        detail=f"IQR 范围 [{lower:.2f}, {upper:.2f}], "
                               f"系数={outlier_iqr_mult} (仅标记，未修改)"
                    )
                if len(outlier_indices) > 20:
                    anomaly_logger.add(
                        row_idx=-1, column=col, issue="outlier_iqr_more",
                        original="", cleaned="",
                        detail=f"还有 {len(outlier_indices) - 20} 个异常值未逐条列出"
                    )
        if not any_outliers and verbose:
            print(f"     (无异常值)")

    # ── Step 3: 分类型列清洗 ──
    if verbose and cat_cols:
        print(f"\n  🏷️  分类型列清洗:")

    for col in cat_cols:
        col_anomalies = 0
        for i in range(len(df)):
            raw = df.at[i, col]

            if pd.isna(raw):
                continue

            raw_str = str(raw)
            cleaned_str = raw_str.strip()
            cleaned_str = to_halfwidth(cleaned_str)

            # 去除空格后如果是空字符串 → 转 NaN
            if cleaned_str == "":
                col_anomalies += 1
                anomaly_logger.add(
                    row_idx=i, column=col, issue="blank_emptied",
                    original=repr(raw_str), cleaned="",
                    detail="空值字符串已转为 NaN"
                )
                df.at[i, col] = np.nan
                continue

            if cleaned_str != raw_str:
                col_anomalies += 1
                anomaly_logger.add(
                    row_idx=i, column=col, issue="category_format_fixed",
                    original=raw_str, cleaned=cleaned_str,
                    detail="去除空格/全角转半角"
                )
                df.at[i, col] = cleaned_str

        if col_anomalies > 0 and verbose:
            print(f"     {col:<20}  修复 {col_anomalies} 处")

    # ── Step 4: 重复行检测 ──
    if verbose:
        print(f"\n  🔁 重复行检测:")
    dup_mask = df.duplicated(keep='first')
    dup_count = dup_mask.sum()
    if dup_count > 0:
        dup_indices = dup_mask[dup_mask].index.tolist()
        if verbose:
            print(f"     ⚠️ 发现 {dup_count} 个重复行 (保留首次出现，仅标记)")
        for idx in dup_indices[:20]:
            anomaly_logger.add(
                row_idx=idx, column="(整行)", issue="duplicate_row",
                original="", cleaned="",
                detail=f"与前面行完全重复 (仅标记，未删除)"
            )
        if len(dup_indices) > 20:
            anomaly_logger.add(
                row_idx=-1, column="(整行)", issue="duplicate_row_more",
                original="", cleaned="",
                detail=f"还有 {len(dup_indices) - 20} 个重复行未逐条列出"
            )
    else:
        if verbose:
            print(f"     ✅ 无重复行")

    # ── Step 5: 最终统计 ──
    if verbose:
        orig_missing = df.isna().sum().sum()
        print(f"\n{'='*60}")
        print(f" ✅ 清洗完成 — 当前缺失值总计: {orig_missing} 个")
        print(f"{'='*60}\n")

    return df


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="数据清洗工具 — 数值格式修复、分类统一、异常检测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s data_cleaned.csv                    读取清洗, 输出 data_final.csv
  %(prog)s data_cleaned.csv final.csv          指定输出路径
  %(prog)s data.csv --outlier 2.0              自定义 IQR 倍数 (默认 1.5)
  %(prog)s data.csv --quiet                    静默模式 (不打印逐列详情)
        """,
    )
    parser.add_argument("input", help="输入 CSV 文件路径")
    parser.add_argument("output", nargs="?", default=None,
                        help="输出 CSV 路径 (默认: <输入名>_final.csv)")
    parser.add_argument("--anomalies", default=None,
                        help="异常日志路径 (默认: <输入目录>/anomalies.csv)")
    parser.add_argument("--outlier", type=float, default=1.5,
                        help="IQR 倍数 (默认 1.5, 越大越宽松)")
    parser.add_argument("--encoding", default="utf-8",
                        help="输入/输出编码 (默认 utf-8)")
    parser.add_argument("--quiet", action="store_true",
                        help="静默模式，不打印逐列详情")
    args = parser.parse_args()

    # 输入校验
    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    # 自动路径
    output_path = args.output or (
        os.path.splitext(args.input)[0] + "_final.csv"
    )
    anomalies_path = args.anomalies or os.path.join(
        os.path.dirname(args.input) or ".", "anomalies.csv"
    )

    # 1. 读取
    print(f"📖 正在读取: {args.input}")
    df = pd.read_csv(args.input, encoding=args.encoding)
    print(f"✅ 加载完成: {df.shape[0]} 行 × {df.shape[1]} 列")

    # 2. 清洗
    logger = AnomalyLogger()
    df_clean = clean_dataframe(df, logger, outlier_iqr_mult=args.outlier,
                                verbose=not args.quiet)

    # 3. 写出
    df_clean.to_csv(output_path, index=False, encoding=args.encoding)
    print(f"💾 清洗后数据: {output_path} ({df_clean.shape[0]} 行 × {df_clean.shape[1]} 列)")

    # 4. 写出异常日志
    logger.write(anomalies_path)

    return df_clean, logger


if __name__ == "__main__":
    main()
