#!/usr/bin/env python3
"""
dataloader.py — 通用数据加载与变量类型识别工具

功能:
  1. 读取 CSV 或 XLSX 文件
  2. 自动识别每列为「数值型」或「分类型」
  3. 输出清洗后的 CSV 文件
  4. 打印变量类型报告

用法:
  python dataloader.py <输入文件> [输出文件]

示例:
  python dataloader.py data.csv
  python dataloader.py data.xlsx cleaned.csv
"""

import sys
import os
import argparse

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# 类型识别逻辑
# ---------------------------------------------------------------------------

def infer_variable_type(series: pd.Series, cat_threshold: float = 0.05,
                        cat_max_unique: int = 30) -> str:
    """判断一个 Series 是 'numeric' 还是 'categorical'.

    规则 (优先级由高到低):
      1. 完全缺失 → 视为 categorical (无法判断)
      2. 显式 object/dtype 且内容不能转为数值 → categorical
      3. 纯数值 dtype (int/float) 且 唯一值占比 > cat_threshold 且 {唯一值数 > 2} → numeric
      4. 纯数值 dtype 但唯一值占比 ≤ cat_threshold — 即少量离散整数 → categorical (如 0/1 编码)
      5. 布尔类型 → categorical
      6. 日期时间 → 特殊标记为 datetime (归类为 categorical 便于后续处理)
    """

    n = len(series)
    if n == 0:
        return "categorical"

    # 排除缺失后分析
    clean = series.dropna()

    if len(clean) == 0:
        return "categorical"

    # 1. 日期时间
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"  # 视为分类

    # 2. 布尔
    if pd.api.types.is_bool_dtype(series):
        return "categorical"

    # 3. 尝试转换 object 类型
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        # 看看 string 能不能转数值
        numeric_count = pd.to_numeric(clean, errors='coerce').notna().sum()
        ratio_numeric = numeric_count / len(clean)
        if ratio_numeric >= 0.9:
            # 大部分是数字 → 视为数值型（转成 float 后再判断离散度）
            numeric_series = pd.to_numeric(clean, errors='coerce')
            return _decide_numeric_or_cat(numeric_series, n, cat_threshold)
        else:
            return "categorical"

    # 4. 数值 dtype
    if pd.api.types.is_numeric_dtype(series):
        return _decide_numeric_or_cat(clean, n, cat_threshold, cat_max_unique)

    # 5. 兜底
    return "categorical"


def _decide_numeric_or_cat(series: pd.Series, total_n: int,
                           cat_threshold: float,
                           cat_max_unique: int = 30) -> str:
    """已确定是数值的 series, 进一步判断是真正连续值还是离散编码."""
    if len(series) == 0:
        return "categorical"

    n_unique = series.nunique()
    ratio_unique = n_unique / total_n

    # 只有 1 个唯一值 → 常量，归为分类
    if n_unique <= 1:
        return "categorical"

    # 恰好 2 个唯一值 → 典型的二分类编码 (0/1, -1/1 等)
    if n_unique == 2:
        return "categorical"

    # 唯一值占比低于阈值 → 离散整数编码 (如 0-5 的评分但样本很多)
    if ratio_unique <= cat_threshold:
        return "categorical"

    # 唯一值总数超过上限 → 大概率是连续值
    if n_unique > cat_max_unique:
        return "numeric"

    # 对于较小数据集: 唯一值数 ≥ max(3, total_n * 0.5) 即为连续
    small_sample_cutoff = max(3, total_n * 0.5)
    if total_n <= 50 and n_unique >= small_sample_cutoff:
        return "numeric"

    # 大样本: 唯一值数 > 10 且 占比 > 阈值 → 连续值
    if n_unique > 10 and ratio_unique > cat_threshold:
        return "numeric"

    # 兜底: 少量整数编码
    return "categorical"


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def load_file(path: str) -> pd.DataFrame:
    """根据扩展名自动选择读取方式."""
    ext = os.path.splitext(path)[1].lower()

    if ext == ".csv":
        return pd.read_csv(path)
    elif ext in (".xls", ".xlsx"):
        return pd.read_excel(path, engine="openpyxl")
    else:
        raise ValueError(f"不支持的文件格式: {ext}，仅支持 .csv / .xlsx")


def build_report(df: pd.DataFrame) -> dict:
    """返回 {列名: 类型} 字典."""
    report = {}
    for col in df.columns:
        report[col] = infer_variable_type(df[col])
    return report


def print_report(report: dict, df: pd.DataFrame):
    """打印漂亮的类型报告."""
    max_name_len = max(len(n) for n in report.keys()) + 2

    print(f"\n{'='*60}")
    print(f" 📋 变量类型报告 (共 {len(report)} 列, {len(df)} 行)")
    print(f"{'='*60}")

    numeric_cols = [c for c, t in report.items() if t == "numeric"]
    cat_cols = [c for c, t in report.items() if t == "categorical"]
    dt_cols = [c for c, t in report.items() if t == "datetime"]

    for col in df.columns:
        typ = report[col]
        # 符号
        if typ == "numeric":
            icon = "🔢"
        elif typ == "categorical":
            icon = "🏷️"
        elif typ == "datetime":
            icon = "📅"
        else:
            icon = "❓"

        dtype_str = str(df[col].dtype)
        n_missing = df[col].isna().sum()
        n_unique = df[col].nunique()

        sample_vals = df[col].dropna().unique()[:5]
        sample_str = ", ".join(str(v) for v in sample_vals)
        if len(df[col].dropna().unique()) > 5:
            sample_str += ", ..."

        print(f"  {icon} {col:<{max_name_len}}  dtype={dtype_str:<10}"
              f"  unique={n_unique:<5}  missing={n_missing:<4}")
        print(f"     {'':>{max_name_len}}  值示例: [{sample_str}]")

    print(f"\n  📊 汇总: 数值型 {len(numeric_cols)} 列"
          f" | 分类型 {len(cat_cols)} 列"
          f" | 日期型 {len(dt_cols)} 列")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="数据加载 & 变量类型识别工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s data.csv                  读取 CSV, 打印报告, 输出 data_cleaned.csv
  %(prog)s data.xlsx out.csv         读取 Excel, 输出 out.csv
  %(prog)s data.csv --no-output      仅打印报告, 不输出文件
  %(prog)s data.csv --thresh 0.03    调低分类阈值 (更倾向识别为数值型)
        """)
    parser.add_argument("input", help="输入文件路径 (.csv / .xlsx)")
    parser.add_argument("output", nargs="?", default=None,
                        help="输出 CSV 路径 (默认: <输入文件名>_cleaned.csv)")
    parser.add_argument("--no-output", action="store_true",
                        help="不输出 CSV, 仅打印类型报告")
    parser.add_argument("--thresh", type=float, default=0.05,
                        help="分类判定阈值 (唯一值/总行数 ≤ 此值为分类, 默认 0.05)")
    parser.add_argument("--encoding", default="utf-8",
                        help="输出 CSV 编码 (默认 utf-8)")

    args = parser.parse_args()

    # 1. 读取
    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    print(f"📖 正在读取: {args.input}")
    df = load_file(args.input)
    print(f"✅ 成功加载: {df.shape[0]} 行 × {df.shape[1]} 列")

    # 2. 推断类型
    report = build_report(df)

    # 3. 打印报告
    print_report(report, df)

    # 4. 输出 CSV
    if not args.no_output:
        output_path = args.output or (
            os.path.splitext(args.input)[0] + "_cleaned.csv"
        )
        df.to_csv(output_path, index=False, encoding=args.encoding)
        print(f"💾 已输出: {output_path}")
    else:
        print("⏭️  跳过输出 (--no-output)")

    # 5. 返回类型字典 (可供其他 Python 脚本 import 使用)
    return df, report


if __name__ == "__main__":
    main()
