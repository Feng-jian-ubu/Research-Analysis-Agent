import pandas as pd
import numpy as np


def _to_python(value):
    """
    将 numpy 类型转换成 Python 原生类型，
    方便后续 JSON 序列化。
    """
    if pd.isna(value):
        return None

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, np.bool_):
        return bool(value)

    return value


def _calculate_correlation(x, y, method):
    """
    计算两个变量之间的相关系数。

    method:
        pearson
        spearman
        kendall
    """

    if method == "pearson":
        return x.corr(y, method="pearson")

    elif method == "spearman":
        return x.corr(y, method="spearman")

    elif method == "kendall":
        return x.corr(y, method="kendall")

    else:
        raise ValueError(
            f"不支持的相关性计算方法: {method}"
        )


def run(request: dict) -> dict:
    """
    计算 CSV 文件中指定变量之间的相关性。

    输入格式：

    {
        "data_path": "outputs/uploads/task_xxx/cleaned.csv",
        "params": {
            "columns": ["temperature", "yield"],
            "method": "pearson",
            "alpha": 0.05,
            "missing": "pairwise",
            "min_periods": 3
        }
    }

    输出格式：

    {
        "summary": {
            "method": "pearson",
            "alpha": 0.05,
            "variable_count": 2
        },
        "tables": [
            {
                "name": "correlation_matrix",
                "title": "相关系数矩阵",
                "columns": [
                    "variable",
                    "temperature",
                    "yield"
                ],
                "rows": [
                    {
                        "variable": "temperature",
                        "temperature": 1.0,
                        "yield": 0.85
                    },
                    {
                        "variable": "yield",
                        "temperature": 0.85,
                        "yield": 1.0
                    }
                ]
            }
        ]
    }
    """

    # ============================================================
    # 1. 检查 request
    # ============================================================

    if not isinstance(request, dict):
        raise TypeError("request 必须是 dict")

    data_path = request.get("data_path")

    if not data_path:
        raise ValueError("缺少 data_path")

    params = request.get("params", {})

    if not isinstance(params, dict):
        raise TypeError("params 必须是 dict")

    # ============================================================
    # 2. 获取参数
    # ============================================================

    columns = params.get("columns")

    if not columns:
        raise ValueError("params.columns 不能为空")

    if not isinstance(columns, list):
        raise TypeError(
            "params.columns 必须是 array[string]"
        )

    if not all(isinstance(column, str) for column in columns):
        raise TypeError(
            "params.columns 中的元素必须都是 string"
        )

    # 检查变量是否重复
    if len(columns) != len(set(columns)):
        raise ValueError(
            "params.columns 中不能包含重复字段"
        )

    method = params.get("method", "pearson")

    if method not in ["pearson", "spearman", "kendall"]:
        raise ValueError(
            "method 必须是 pearson、spearman 或 kendall"
        )

    alpha = params.get("alpha", 0.05)

    if not isinstance(alpha, (int, float)):
        raise TypeError(
            "alpha 必须是数字"
        )

    if alpha <= 0 or alpha >= 1:
        raise ValueError(
            "alpha 必须位于 0 和 1 之间"
        )

    missing = params.get("missing", "pairwise")

    if missing != "pairwise":
        raise ValueError(
            "目前只支持 missing='pairwise'"
        )

    min_periods = params.get("min_periods", 3)

    if not isinstance(min_periods, int):
        raise TypeError(
            "min_periods 必须是整数"
        )

    if min_periods < 1:
        raise ValueError(
            "min_periods 必须大于等于 1"
        )

    # ============================================================
    # 3. 读取 CSV
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
    # 4. 检查字段
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
    # 5. 检查变量是否为数值型
    # ============================================================

    non_numeric_columns = [
        column
        for column in columns
        if not pd.api.types.is_numeric_dtype(df[column])
    ]

    if non_numeric_columns:
        raise ValueError(
            "相关性分析要求参与计算的字段必须是数值型，"
            f"以下字段不是数值型: {non_numeric_columns}"
        )

    # ============================================================
    # 6. 初始化相关系数矩阵
    # ============================================================

    variable_count = len(columns)

    correlation_matrix = pd.DataFrame(
        np.nan,
        index=columns,
        columns=columns,
        dtype=float
    )

    # 对角线为 1
    for column in columns:
        correlation_matrix.loc[column, column] = 1.0

    # ============================================================
    # 7. 两两计算相关系数
    # ============================================================

    for i in range(variable_count):

        for j in range(i + 1, variable_count):

            column_x = columns[i]
            column_y = columns[j]

            # ----------------------------------------------------
            # pairwise：
            # 只保留当前两个变量同时非缺失的样本
            # ----------------------------------------------------

            pair = df[
                [column_x, column_y]
            ].dropna()

            # ----------------------------------------------------
            # 判断有效样本数量
            # ----------------------------------------------------

            valid_count = len(pair)

            if valid_count < min_periods:

                correlation = None

            else:

                x = pair[column_x]
                y = pair[column_y]

                # ------------------------------------------------
                # 如果某个变量没有变化，相关系数无法计算
                # ------------------------------------------------

                if x.nunique() <= 1 or y.nunique() <= 1:

                    correlation = None

                else:

                    correlation = _calculate_correlation(
                        x,
                        y,
                        method
                    )

                    correlation = _to_python(
                        correlation
                    )

            # ----------------------------------------------------
            # 写入矩阵
            # ----------------------------------------------------

            correlation_matrix.loc[
                column_x,
                column_y
            ] = (
                np.nan
                if correlation is None
                else correlation
            )

            correlation_matrix.loc[
                column_y,
                column_x
            ] = (
                np.nan
                if correlation is None
                else correlation
            )

    # ============================================================
    # 8. 构造输出 rows
    # ============================================================

    rows = []

    for row_variable in columns:

        row = {
            "variable": row_variable
        }

        for column in columns:

            value = correlation_matrix.loc[
                row_variable,
                column
            ]

            if pd.isna(value):
                row[column] = None
            else:
                row[column] = round(
                    float(value),
                    6
                )

        rows.append(row)

    # ============================================================
    # 9. 构造最终结果
    # ============================================================

    result = {
        "summary": {
            "method": method,
            "alpha": float(alpha),
            "variable_count": variable_count
        },
        "tables": [
            {
                "name": "correlation_matrix",
                "title": "相关系数矩阵",
                "columns": [
                    "variable"
                ] + columns,
                "rows": rows
            }
        ]
    }

    return result