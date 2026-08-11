import pandas as pd
import numpy as np
from typing import Any


def _to_python(value: Any):
    """将 numpy 类型转换为 Python 原生类型，便于 JSON 序列化。"""
    if pd.isna(value):
        return None

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, np.bool_):
        return bool(value)

    return value


def _round_value(value: Any, digits: int = 6):
    """对数值进行四舍五入。"""
    value = _to_python(value)

    if isinstance(value, float):
        return round(value, digits)

    return value


def _is_numeric(series: pd.Series) -> bool:
    """判断字段是否为数值型。"""
    return pd.api.types.is_numeric_dtype(series)


def _calculate_numeric_statistics(
    series: pd.Series,
    include_percentiles: bool
) -> dict:
    """计算数值型变量的描述性统计。"""

    valid = series.dropna()

    result = {
        "type": "numeric",
        "count": int(valid.count()),
        "mean": None,
        "std": None,
        "min": None,
        "q1": None,
        "median": None,
        "q3": None,
        "max": None,
        "unique": None,
        "mode": None,
        "mode_frequency": None
    }

    if len(valid) == 0:
        return result

    result["mean"] = _round_value(valid.mean())
    result["std"] = _round_value(valid.std())
    result["min"] = _round_value(valid.min())
    result["median"] = _round_value(valid.median())
    result["max"] = _round_value(valid.max())

    if include_percentiles:
        result["q1"] = _round_value(valid.quantile(0.25))
        result["q3"] = _round_value(valid.quantile(0.75))

    return result


def _calculate_categorical_statistics(series: pd.Series) -> dict:
    """计算分类变量的描述性统计。"""

    valid = series.dropna()

    result = {
        "type": "categorical",
        "count": int(valid.count()),
        "mean": None,
        "std": None,
        "min": None,
        "q1": None,
        "median": None,
        "q3": None,
        "max": None,
        "unique": int(valid.nunique()),
        "mode": None,
        "mode_frequency": None
    }

    if len(valid) == 0:
        return result

    value_counts = valid.value_counts()

    if len(value_counts) > 0:
        result["mode"] = _to_python(value_counts.index[0])
        result["mode_frequency"] = int(value_counts.iloc[0])

    return result


def _calculate_statistics(
    series: pd.Series,
    include_percentiles: bool
) -> dict:
    """根据字段类型选择统计方法。"""

    if _is_numeric(series):
        return _calculate_numeric_statistics(
            series,
            include_percentiles
        )

    return _calculate_categorical_statistics(series)


def run(request: dict) -> dict:
    """
    对 CSV 文件中的指定字段进行描述性统计。

    输入格式：
    {
        "data_path": "outputs/uploads/task_xxx/cleaned.csv",
        "params": {
            "columns": ["yield", "temperature", "fertilizer"],
            "include_percentiles": true
        }
    }

    输出格式：
    {
        "tables": [
            {
                "name": "descriptive_statistics",
                "title": "描述性统计结果",
                "columns": [...],
                "rows": [...]
            }
        ]
    }
    """

    # ============================================================
    # 1. 检查输入
    # ============================================================

    if not isinstance(request, dict):
        raise TypeError("request 必须是 dict")

    data_path = request.get("data_path")

    if not data_path:
        raise ValueError("缺少 data_path")

    params = request.get("params", {})

    if not isinstance(params, dict):
        raise TypeError("params 必须是 dict")

    columns = params.get("columns")

    if not columns:
        raise ValueError("params.columns 不能为空")

    if not isinstance(columns, list):
        raise TypeError("params.columns 必须是 array[string]")

    if not all(isinstance(column, str) for column in columns):
        raise TypeError("params.columns 中的元素必须都是 string")

    include_percentiles = params.get(
        "include_percentiles",
        True
    )

    if not isinstance(include_percentiles, bool):
        raise TypeError("include_percentiles 必须是 boolean")

    # ============================================================
    # 2. 读取 CSV
    # ============================================================

    try:
        df = pd.read_csv(data_path)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"找不到数据文件: {data_path}"
        )
    except Exception as e:
        raise ValueError(
            f"读取 CSV 文件失败: {str(e)}"
        )

    # ============================================================
    # 3. 检查字段是否存在
    # ============================================================

    missing_columns = [
        column
        for column in columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"以下字段不存在于 CSV 文件中: {missing_columns}"
        )

    # ============================================================
    # 4. 定义输出字段
    # ============================================================

    output_columns = [
        "variable",
        "type",
        "count",
        "mean",
        "std",
        "min",
        "q1",
        "median",
        "q3",
        "max",
        "unique",
        "mode",
        "mode_frequency"
    ]

    rows = []

    # ============================================================
    # 5. 逐字段统计
    # ============================================================

    for column in columns:

        stats = _calculate_statistics(
            df[column],
            include_percentiles
        )

        row = {
            "variable": column,
            **stats
        }

        # 确保输出字段顺序和 columns 定义一致
        normalized_row = {}

        for field in output_columns:
            normalized_row[field] = _to_python(
                row.get(field)
            )

        rows.append(normalized_row)

    # ============================================================
    # 6. 构造最终输出
    # ============================================================

    return {
        "tables": [
            {
                "name": "descriptive_statistics",
                "title": "描述性统计结果",
                "columns": output_columns,
                "rows": rows
            }
        ]
    }