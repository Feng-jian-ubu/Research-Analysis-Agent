#!/usr/bin/env python3
"""
resourceselector.py — 运算资源选择器

功能:
  在 methodselector 之后运行，读取数据文件元信息 + 方法推荐结果，
  判定当前分析应该在本地还是 HPC（交大鲲鹏集群）上执行。
  输出 resource_decision.json 供下游脚本决策分叉。

用法:
  python3 resourceselector.py <数据CSV> [选项]

示例:
  python3 resourceselector.py experiment_data_final.csv
  python3 resourceselector.py experiment_data_final.csv -y score -x age gender -m regression
  python3 resourceselector.py experiment_data_final.csv --no-check

输出:
  resource_decision.json  — 包含决策结果和分叉所需的全部参数
"""

import sys
import os
import json
import argparse
import textwrap

import pandas as pd
import numpy as np


# ===================================================================
# 类型识别（与 dataloader / methodselector / statisticsexecutor 一致）
# ===================================================================

def infer_variable_type(series: pd.Series, cat_threshold: float = 0.05,
                        cat_max_unique: int = 30) -> str:
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


def build_type_map(df: pd.DataFrame) -> dict:
    return {col: infer_variable_type(df[col]) for col in df.columns}


def auto_detect_method(df: pd.DataFrame, type_map: dict,
                       y_col: str, x_vars: list) -> tuple:
    """从数据中自动判断推荐方法. 返回 (method_name, description)."""
    y_type = type_map.get(y_col, "numeric")
    cat_x = [c for c in x_vars if type_map.get(c) == "categorical"]
    num_x = [c for c in x_vars if type_map.get(c) == "numeric"]

    if y_type == "numeric":
        if len(cat_x) == 1 and len(num_x) == 0:
            n_grp = df[cat_x[0]].nunique()
            if n_grp == 2:
                return ("ttest", "独立样本 t 检验")
            elif n_grp >= 3:
                return ("anova", "单因素 ANOVA")
        if len(num_x) >= 1 and len(cat_x) == 0:
            return ("regression", "简单线性回归")
        if len(num_x) + len(cat_x) > 1:
            return ("regression", "多元线性回归")
    elif y_type == "categorical":
        n_y = df[y_col].nunique()
        if n_y == 2:
            return ("logistic", "逻辑回归")
        else:
            return ("logistic", "逻辑回归 (多分类)")

    return ("describe", "描述统计")


# ===================================================================
# 决策引擎
# ===================================================================

# HPC 推荐阈值
HPC_THRESHOLDS = {
    "row_count": 50000,       # 行数 > 5 万 → HPC
    "file_size_mb": 100,      # 文件大小 > 100 MB → HPC
    "feature_count": 20,      # X 列数 > 20 → HPC
    "num_x_count": 10,        # 数值型 X > 10 → HPC
    "cat_levels": 50,         # 某分类列的类别数 > 50 → HPC
}

# 必须用 HPC 的方法
HPC_METHODS = {
    "random_forest", "randomforest", "rf",
    "xgboost", "xgb",
    "svm",
    "neural_network", "nn", "deep_learning",
    "gradient_boosting", "gbm",
}


def _check_hpc_method(method: str) -> bool:
    """根据方法名判断是否需要 HPC."""
    if not method:
        return False
    ml = method.lower().strip()
    return ml in HPC_METHODS


def _check_hpc_data_size(df: pd.DataFrame, input_path: str) -> (bool, list):
    """根据数据规模判断."""
    reasons = []
    n_rows, n_cols = df.shape

    if n_rows > HPC_THRESHOLDS["row_count"]:
        reasons.append(f"数据行数 {n_rows} > {HPC_THRESHOLDS['row_count']}")

    if input_path and os.path.exists(input_path):
        size_mb = os.path.getsize(input_path) / (1024 * 1024)
        if size_mb > HPC_THRESHOLDS["file_size_mb"]:
            reasons.append(f"文件大小 {size_mb:.1f} MB > {HPC_THRESHOLDS['file_size_mb']} MB")

    return bool(reasons), reasons


def _check_hpc_features(type_map: dict, x_vars: list) -> (bool, list):
    """根据特征复杂度判断."""
    reasons = []
    if len(x_vars) > HPC_THRESHOLDS["feature_count"]:
        reasons.append(f"特征数 {len(x_vars)} > {HPC_THRESHOLDS['feature_count']}")

    num_x = [c for c in x_vars if type_map.get(c) == "numeric"]
    if len(num_x) > HPC_THRESHOLDS["num_x_count"]:
        reasons.append(f"数值型特征 {len(num_x)} > {HPC_THRESHOLDS['num_x_count']}")

    cat_x = [c for c in x_vars if type_map.get(c) == "categorical"]
    for c in cat_x:
        # 计算哑变量展开后的维度
        n_levels = 0
        if c in type_map:
            pass  # 具体值需在 decide 中传入 df
    return bool(reasons), reasons


# ===================================================================
# 主决策函数
# ===================================================================

def decide(df: pd.DataFrame, input_path: str,
           type_map: dict, method: str, y_col: str, x_vars: list) -> dict:
    """
    综合判断使用本地还是 HPC.

    返回:
      决策字典, 包含:
        recommendation: "local" | "hpc"
        reason: str
        details: dict   # 各维度评分详情
    """
    reasons_hpc = []
    reasons_local = []

    # 1. 方法维度
    if _check_hpc_method(method):
        reasons_hpc.append(f"方法 '{method}' 计算量大，适合 HPC")

    # 2. 数据规模
    size_hpc, size_reasons = _check_hpc_data_size(df, input_path)
    reasons_hpc.extend(size_reasons)

    # 3. 特征复杂度
    feat_hpc, feat_reasons = _check_hpc_features(type_map, x_vars)
    reasons_hpc.extend(feat_reasons)

    # 4. 分类变量哑变量展开后的维度（额外检查）
    cat_x = [c for c in x_vars if type_map.get(c) == "categorical"]
    for c in cat_x:
        n_levels = df[c].nunique()
        if n_levels > HPC_THRESHOLDS["cat_levels"]:
            reasons_hpc.append(
                f"分类列 '{c}' 有 {n_levels} 个类别，哑变量展开后维度剧增")

    # 5. 中小数据量的本地偏好
    n_rows = len(df)
    if not reasons_hpc:
        if n_rows < 10000:
            reasons_local.append(f"数据量适中 ({n_rows} 行)，本地即可快速处理")
        elif n_rows < 50000:
            reasons_local.append(f"数据量中等 ({n_rows} 行)，本地可处理")

    # 决策
    if reasons_hpc:
        recommendation = "hpc"
        reason = "; ".join(reasons_hpc[:3])
        if len(reasons_hpc) > 3:
            reason += f" (等 {len(reasons_hpc)} 项原因)"
    else:
        recommendation = "local"
        reason = "; ".join(reasons_local) if reasons_local else "数据量和复杂度均适合本地运行"

    return {
        "recommendation": recommendation,
        "reason": reason,
        "details": {
            "n_rows": n_rows,
            "n_cols": df.shape[1],
            "file_size_mb": round(os.path.getsize(input_path) / (1024 * 1024), 2)
                if input_path and os.path.exists(input_path) else None,
            "n_features": len(x_vars),
            "n_cat_features": len(cat_x),
            "n_num_features": len([c for c in x_vars if type_map.get(c) == "numeric"]),
            "method": method,
            "y_col": y_col,
            "x_vars": x_vars,
            "type_map": type_map,
            "hpc_reasons": reasons_hpc,
            "local_reasons": reasons_local,
        },
        "pipeline": {
            "data_csv": os.path.abspath(input_path) if input_path else "",
            "method": method,
            "y_col": y_col,
            "x_vars": x_vars,
            "output_prefix": (
                os.path.splitext(os.path.basename(input_path))[0] + "_result"
                if input_path else "result"
            ),
        },
    }


# ===================================================================
# CLI
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="🧪 ResourceSelector — 运算资源选择器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            示例:
              %(prog)s data_final.csv
              %(prog)s data_final.csv -y score -x age gender -m regression
              %(prog)s data_final.csv --no-check
        """)
    )
    parser.add_argument("input", help="清洗后的 CSV 文件路径")
    parser.add_argument("--target", "-y", default=None,
                        help="目标变量 (Y) 列名")
    parser.add_argument("--xvar", "-x", nargs="*", default=None,
                        help="自变量 (X) 列名, 用空格分隔")
    parser.add_argument("--method", "-m", default=None,
                        help="统计方法 (如 ttest / anova / regression / "
                             "logistic / random_forest / xgboost)")
    parser.add_argument("--no-check", action="store_true",
                        help="跳过假设前提检查 (传递给 methodselector 用)")
    parser.add_argument("--encoding", default="utf-8",
                        help="文件编码 (默认 utf-8)")
    parser.add_argument("--output", "-o", default="resource_decision.json",
                        help="输出 JSON 路径 (默认 resource_decision.json)")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    # 读取数据
    df = pd.read_csv(args.input, encoding=args.encoding)
    n_rows, n_cols = df.shape
    input_path = args.input

    print(f"📖 已加载: {args.input} ({n_rows} 行 × {n_cols} 列)")
    type_map = build_type_map(df)

    # 确定 Y
    y_col = args.target
    if not y_col and n_cols >= 2:
        # 简化的自动猜测: 取最后一列
        y_col = df.columns[-1]
        print(f"🎯 自动猜测 Y = '{y_col}' ({type_map.get(y_col, '?')})")

    # 确定 X
    x_vars = args.xvar
    if not x_vars and y_col:
        x_vars = [c for c in df.columns if c != y_col]

    # 确定方法
    method = args.method
    if not method and y_col and x_vars:
        method, desc = auto_detect_method(df, type_map, y_col, x_vars)
        print(f"🎯 自动检测方法: {method} ({desc})")

    # 执行决策
    print(f"\n🔍 正在分析资源需求...")
    decision = decide(df, input_path, type_map, method, y_col, x_vars)

    # 输出
    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(decision, f, ensure_ascii=False, indent=2)

    rec = decision["recommendation"]
    icon = "🖥️" if rec == "hpc" else "💻"
    print(f"\n{icon} 推荐运行环境: {rec.upper()}")
    print(f"   📋 原因: {decision['reason']}")

    # 展示详细统计
    d = decision["details"]
    print(f"\n   📊 数据详情:")
    print(f"      行数: {d['n_rows']:,}")
    if d['file_size_mb']:
        print(f"      文件大小: {d['file_size_mb']:.1f} MB")
    print(f"      特征数 (X): {d['n_features']}")
    print(f"      其中数值型: {d['n_num_features']}  分类型: {d['n_cat_features']}")
    print(f"      方法: {d['method']}")
    print(f"      Y: {d['y_col']}")

    print(f"\n   ✅ 决策已保存到: {os.path.abspath(output_path)}")

    # 提示下游命令
    pipe = decision["pipeline"]
    if rec == "local":
        print(f"\n💡 建议后续命令:")
        print(f"   python3 statisticsexecutor.py {pipe['data_csv']} "
              f"-m {pipe['method']} -y {pipe['y_col']} "
              f"-x {' '.join(pipe['x_vars'])}")
        print(f"   python3 figuregenerator.py {pipe['data_csv']} "
              f"{pipe['output_prefix']}.json --png -t all")
    else:
        print(f"\n💡 建议后续命令:")
        print(f"   python3 hpcsubmit.py {pipe['data_csv']} {args.output}")

    return decision


if __name__ == "__main__":
    main()
