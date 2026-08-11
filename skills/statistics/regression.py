import pandas as pd
import numpy as np
import statsmodels.api as sm


def _to_python(value):
    """
    将 numpy 类型转换为 Python 原生类型，
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


def _round_value(value, digits=6):
    """
    将数值转换为 Python float 并进行四舍五入。
    """
    value = _to_python(value)

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return round(float(value), digits)

    return value


def run(request: dict) -> dict:
    """
    使用一个或多个数值型解释变量建立 OLS 线性回归模型。

    输入格式：

    {
        "data_path": "outputs/uploads/task_xxx/cleaned.csv",
        "params": {
            "target_column": "yield",
            "feature_columns": [
                "temperature",
                "rainfall"
            ],
            "add_constant": true,
            "alpha": 0.05,
            "standardize": false
        }
    }

    输出：
    {
        "summary": {
            "model": "ols",
            "n_observations": 115,
            "r_squared": 0.68,
            "adjusted_r_squared": 0.66,
            "f_statistic": 38.2,
            "f_p_value": 0.000001,
            "rmse": 2.14,
            "aic": 318.4,
            "bic": 329.1
        },
        "tables": [
            {
                "name": "coefficients",
                "title": "回归系数",
                "columns": [
                    "variable",
                    "coefficient",
                    "standard_error",
                    "t_value",
                    "p_value",
                    "confidence_interval_lower",
                    "confidence_interval_upper"
                ],
                "rows": []
            },
            {
                "name": "model_metrics",
                "title": "回归模型整体指标",
                "columns": [
                    "r_squared",
                    "adjusted_r_squared",
                    "rmse",
                    "aic",
                    "bic",
                    "f_statistic",
                    "f_p_value"
                ],
                "rows": []
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

    target_column = params.get("target_column")

    if not target_column:
        raise ValueError("缺少 target_column")

    feature_columns = params.get("feature_columns")

    if not feature_columns:
        raise ValueError("feature_columns 不能为空")

    if not isinstance(feature_columns, list):
        raise TypeError(
            "feature_columns 必须是 array[string]"
        )

    if not all(
        isinstance(column, str)
        for column in feature_columns
    ):
        raise TypeError(
            "feature_columns 中的元素必须都是 string"
        )

    # 检查重复变量
    if len(feature_columns) != len(set(feature_columns)):
        raise ValueError(
            "feature_columns 中不能包含重复字段"
        )

    # target 不能同时作为 feature
    if target_column in feature_columns:
        raise ValueError(
            "target_column 不能同时出现在 feature_columns 中"
        )

    add_constant = params.get(
        "add_constant",
        True
    )

    if not isinstance(add_constant, bool):
        raise TypeError(
            "add_constant 必须是 boolean"
        )

    alpha = params.get(
        "alpha",
        0.05
    )

    if not isinstance(alpha, (int, float)):
        raise TypeError(
            "alpha 必须是数字"
        )

    if alpha <= 0 or alpha >= 1:
        raise ValueError(
            "alpha 必须位于 0 和 1 之间"
        )

    standardize = params.get(
        "standardize",
        False
    )

    if not isinstance(standardize, bool):
        raise TypeError(
            "standardize 必须是 boolean"
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

    if target_column not in df.columns:
        raise ValueError(
            f"目标变量不存在: {target_column}"
        )

    missing_features = [
        column
        for column in feature_columns
        if column not in df.columns
    ]

    if missing_features:
        raise ValueError(
            f"以下解释变量不存在: {missing_features}"
        )

    # ============================================================
    # 5. 检查变量是否为数值型
    # ============================================================

    if not pd.api.types.is_numeric_dtype(
        df[target_column]
    ):
        raise ValueError(
            f"目标变量 {target_column} 必须是数值型"
        )

    non_numeric_features = [
        column
        for column in feature_columns
        if not pd.api.types.is_numeric_dtype(
            df[column]
        )
    ]

    if non_numeric_features:
        raise ValueError(
            "OLS 回归要求解释变量必须是数值型，"
            f"以下变量不是数值型: {non_numeric_features}"
        )

    # ============================================================
    # 6. 提取建模数据
    # ============================================================

    model_columns = [
        target_column
    ] + feature_columns

    model_df = df[model_columns].copy()

    # 删除目标变量或解释变量中存在缺失值的行
    model_df = model_df.dropna()

    n_observations = len(model_df)

    if n_observations == 0:
        raise ValueError(
            "删除缺失值后没有可用于回归分析的数据"
        )

    # ============================================================
    # 7. 检查样本数量
    # ============================================================

    parameter_count = len(feature_columns)

    if add_constant:
        parameter_count += 1

    if n_observations <= parameter_count:
        raise ValueError(
            "有效样本数量不足，无法建立 OLS 模型。"
            f"当前有效样本数: {n_observations}，"
            f"模型参数数量: {parameter_count}"
        )

    # ============================================================
    # 8. 构造 X 和 y
    # ============================================================

    y = model_df[target_column].astype(float)

    X = model_df[feature_columns].astype(float).copy()

    # ============================================================
    # 9. 标准化解释变量
    # ============================================================

    if standardize:

        for column in feature_columns:

            mean = X[column].mean()
            std = X[column].std(ddof=0)

            if std == 0:
                raise ValueError(
                    f"解释变量 {column} 的标准差为 0，"
                    "无法进行标准化"
                )

            X[column] = (
                X[column] - mean
            ) / std

    # ============================================================
    # 10. 添加常数项
    # ============================================================

    if add_constant:
        X = sm.add_constant(
            X,
            has_constant="add"
        )

    # ============================================================
    # 11. 建立 OLS 模型
    # ============================================================

    try:
        model = sm.OLS(
            y,
            X
        ).fit()

    except Exception as e:
        raise ValueError(
            f"OLS 模型拟合失败: {str(e)}"
        )

    # ============================================================
    # 12. 计算 RMSE
    # ============================================================

    residuals = model.resid

    rmse = np.sqrt(
        np.mean(
            residuals ** 2
        )
    )

    # ============================================================
    # 13. 获取整体模型指标
    # ============================================================

    r_squared = model.rsquared

    adjusted_r_squared = model.rsquared_adj

    f_statistic = model.fvalue

    f_p_value = model.f_pvalue

    aic = model.aic

    bic = model.bic

    # ============================================================
    # 14. 获取系数信息
    # ============================================================

    confidence_intervals = model.conf_int(
        alpha=alpha
    )

    coefficient_rows = []

    for variable in model.params.index:

        coefficient = model.params[variable]

        standard_error = model.bse[variable]

        t_value = model.tvalues[variable]

        p_value = model.pvalues[variable]

        ci_lower = confidence_intervals.loc[
            variable,
            0
        ]

        ci_upper = confidence_intervals.loc[
            variable,
            1
        ]

        coefficient_rows.append(
            {
                "variable": variable,
                "coefficient": _round_value(
                    coefficient
                ),
                "standard_error": _round_value(
                    standard_error
                ),
                "t_value": _round_value(
                    t_value
                ),
                "p_value": _round_value(
                    p_value
                ),
                "confidence_interval_lower": _round_value(
                    ci_lower
                ),
                "confidence_interval_upper": _round_value(
                    ci_upper
                )
            }
        )

    # ============================================================
    # 15. 模型整体指标
    # ============================================================

    model_metrics_row = {
        "r_squared": _round_value(
            r_squared
        ),
        "adjusted_r_squared": _round_value(
            adjusted_r_squared
        ),
        "rmse": _round_value(
            rmse
        ),
        "aic": _round_value(
            aic
        ),
        "bic": _round_value(
            bic
        ),
        "f_statistic": _round_value(
            f_statistic
        ),
        "f_p_value": _round_value(
            f_p_value
        )
    }

    # ============================================================
    # 16. 构造最终输出
    # ============================================================

    result = {
        "summary": {
            "model": "ols",
            "n_observations": int(
                n_observations
            ),
            "r_squared": _round_value(
                r_squared
            ),
            "adjusted_r_squared": _round_value(
                adjusted_r_squared
            ),
            "f_statistic": _round_value(
                f_statistic
            ),
            "f_p_value": _round_value(
                f_p_value
            ),
            "rmse": _round_value(
                rmse
            ),
            "aic": _round_value(
                aic
            ),
            "bic": _round_value(
                bic
            )
        },

        "tables": [
            {
                "name": "coefficients",
                "title": "回归系数",
                "columns": [
                    "variable",
                    "coefficient",
                    "standard_error",
                    "t_value",
                    "p_value",
                    "confidence_interval_lower",
                    "confidence_interval_upper"
                ],
                "rows": coefficient_rows
            },
            {
                "name": "model_metrics",
                "title": "回归模型整体指标",
                "columns": [
                    "r_squared",
                    "adjusted_r_squared",
                    "rmse",
                    "aic",
                    "bic",
                    "f_statistic",
                    "f_p_value"
                ],
                "rows": [
                    model_metrics_row
                ]
            }
        ]
    }

    return result