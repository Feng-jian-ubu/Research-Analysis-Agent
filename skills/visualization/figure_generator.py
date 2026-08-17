"""Generate PNG figures for supported statistical analyses."""

import re
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

from backend.services.file_service import get_figure_path
from skills.data.loader import load_dataframe


ANALYSIS_TYPES = {
    "descriptive",
    "correlation",
    "t_test",
    "regression",
}

CHART_TYPES = {
    "descriptive": {"histogram", "bar"},
    "correlation": {"heatmap", "scatter"},
    "t_test": {"boxplot"},
    "regression": {"regression", "scatter", "residual"},
}


def _validate_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"{field} 必须是 array[string]")

    if not all(isinstance(item, str) for item in value):
        raise TypeError(f"{field} 中的元素必须都是 string")

    if any(not item.strip() for item in value):
        raise ValueError(f"{field} 中不能包含空字符串")

    if len(value) != len(set(value)):
        raise ValueError(f"{field} 中不能包含重复字段")

    return value


def _validate_optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError(f"{field} 必须是 string 或 null")

    if not value.strip():
        raise ValueError(f"{field} 不能为空字符串")

    return value


def _validate_request(request: dict) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(request, dict):
        raise TypeError("request 必须是 dict")

    task_id = request.get("task_id")

    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("缺少 task_id")

    if not re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
        raise ValueError(
            "task_id 只能包含英文字母、数字、下划线和连字符"
        )

    data_path = request.get("data_path")

    if not isinstance(data_path, str) or not data_path.strip():
        raise ValueError("缺少 data_path")

    params = request.get("params", {})

    if not isinstance(params, dict):
        raise TypeError("params 必须是 dict")

    analysis_type = params.get("analysis_type")

    if analysis_type not in ANALYSIS_TYPES:
        raise ValueError(
            "analysis_type 必须是 descriptive、correlation、"
            "t_test 或 regression"
        )

    chart_type = _validate_optional_string(
        params.get("chart_type"),
        "chart_type",
    )

    if (
        chart_type is not None
        and chart_type not in CHART_TYPES[analysis_type]
    ):
        allowed = "、".join(sorted(CHART_TYPES[analysis_type]))
        raise ValueError(
            f"{analysis_type} 的 chart_type 只能是 {allowed}"
        )

    dpi = params.get("dpi", 150)

    if isinstance(dpi, bool) or not isinstance(dpi, int):
        raise TypeError("dpi 必须是 integer")

    if not 72 <= dpi <= 600:
        raise ValueError("dpi 必须位于 72 和 600 之间")

    method = params.get("method", "pearson")

    if method not in {"pearson", "spearman", "kendall"}:
        raise ValueError("method 必须是 pearson、spearman 或 kendall")

    normalized = {
        "analysis_type": analysis_type,
        "chart_type": chart_type,
        "columns": _validate_string_list(
            params.get("columns", []),
            "columns",
        ),
        "target_column": _validate_optional_string(
            params.get("target_column"),
            "target_column",
        ),
        "group_column": _validate_optional_string(
            params.get("group_column"),
            "group_column",
        ),
        "feature_columns": _validate_string_list(
            params.get("feature_columns", []),
            "feature_columns",
        ),
        "groups": _validate_string_list(
            params.get("groups", []),
            "groups",
        ),
        "title": _validate_optional_string(
            params.get("title"),
            "title",
        ),
        "dpi": dpi,
        "method": method,
    }

    return task_id, data_path, normalized


def _configure_style() -> None:
    plt.style.use("default")
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.25
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def _require_columns(dataframe: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in dataframe.columns]

    if missing:
        raise ValueError(f"以下绘图字段不存在: {missing}")


def _require_numeric(dataframe: pd.DataFrame, columns: list[str]) -> None:
    non_numeric = [
        column
        for column in columns
        if not pd.api.types.is_numeric_dtype(dataframe[column])
    ]

    if non_numeric:
        raise ValueError(f"以下绘图字段必须是数值型: {non_numeric}")


def _save_figure(
    figure: plt.Figure,
    task_id: str,
    file_name: str,
    dpi: int,
) -> str:
    output_path = get_figure_path(task_id, file_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        figure.tight_layout()
        figure.savefig(
            output_path,
            dpi=dpi,
            format="png",
            bbox_inches="tight",
        )
    finally:
        plt.close(figure)

    return str(output_path)


def _figure_result(
    name: str,
    chart_type: str,
    title: str,
    path: str,
) -> dict[str, str]:
    return {
        "name": name,
        "chart_type": chart_type,
        "title": title,
        "path": path,
        "mime_type": "image/png",
        "alt_text": title,
    }


def _descriptive_figures(
    dataframe: pd.DataFrame,
    task_id: str,
    params: dict[str, Any],
) -> list[dict[str, str]]:
    columns = params["columns"]

    if not columns:
        raise ValueError("描述性统计绘图需要 columns")

    _require_columns(dataframe, columns)

    if params["chart_type"] == "histogram":
        _require_numeric(dataframe, columns)

    figures = []

    for index, column in enumerate(columns, start=1):
        is_numeric = pd.api.types.is_numeric_dtype(dataframe[column])
        chart_type = params["chart_type"] or (
            "histogram" if is_numeric else "bar"
        )

        if chart_type == "histogram" and not is_numeric:
            raise ValueError(f"字段 {column} 不是数值型，不能绘制直方图")

        title = params["title"] or (
            f"{column} 分布"
            if chart_type == "histogram"
            else f"{column} 类别频数"
        )

        if params["title"] and len(columns) > 1:
            title = f"{params['title']} - {column}"

        figure, axis = plt.subplots(figsize=(8, 5))

        if chart_type == "histogram":
            values = dataframe[column].dropna()

            if values.empty:
                plt.close(figure)
                raise ValueError(f"字段 {column} 没有可绘制的有效数据")

            axis.hist(
                values,
                bins="auto",
                color="#4c78a8",
                alpha=0.8,
                edgecolor="white",
            )
            axis.set_ylabel("频数")
        else:
            counts = dataframe[column].dropna().value_counts().head(20)

            if counts.empty:
                plt.close(figure)
                raise ValueError(f"字段 {column} 没有可绘制的有效数据")

            axis.bar(
                [str(value) for value in counts.index],
                counts.values,
                color="#4c78a8",
            )
            axis.tick_params(axis="x", rotation=35)
            axis.set_ylabel("频数")

        axis.set_title(title)
        axis.set_xlabel(column)
        file_name = f"descriptive_{index}.png"
        path = _save_figure(
            figure,
            task_id,
            file_name,
            params["dpi"],
        )
        figures.append(
            _figure_result(
                name=f"descriptive_{index}",
                chart_type=chart_type,
                title=title,
                path=path,
            )
        )

    return figures


def _correlation_figures(
    dataframe: pd.DataFrame,
    task_id: str,
    params: dict[str, Any],
) -> list[dict[str, str]]:
    columns = params["columns"]

    if len(columns) < 2:
        raise ValueError("相关分析绘图至少需要两个 columns")

    _require_columns(dataframe, columns)
    _require_numeric(dataframe, columns)
    chart_type = params["chart_type"] or "heatmap"
    figure, axis = plt.subplots(figsize=(8, 6))

    if chart_type == "heatmap":
        correlation = dataframe[columns].corr(method=params["method"])
        title = params["title"] or "变量相关系数热力图"
        image = axis.imshow(
            correlation.to_numpy(dtype=float),
            cmap="coolwarm",
            vmin=-1,
            vmax=1,
            aspect="equal",
        )
        axis.set_xticks(range(len(columns)), labels=columns, rotation=35)
        axis.set_yticks(range(len(columns)), labels=columns)
        axis.grid(False)
        figure.colorbar(image, ax=axis, label="相关系数")

        for row_index in range(len(columns)):
            for column_index in range(len(columns)):
                value = correlation.iloc[row_index, column_index]
                label = "—" if pd.isna(value) else f"{value:.2f}"
                axis.text(
                    column_index,
                    row_index,
                    label,
                    ha="center",
                    va="center",
                    color=(
                        "white"
                        if not pd.isna(value) and abs(value) >= 0.6
                        else "black"
                    ),
                )
        name = "correlation_heatmap"
    else:
        pair = dataframe[columns[:2]].dropna()

        if pair.empty:
            plt.close(figure)
            raise ValueError("相关分析字段没有共同有效数据")

        title = params["title"] or (
            f"{columns[0]} 与 {columns[1]} 散点图"
        )
        axis.scatter(
            pair[columns[0]],
            pair[columns[1]],
            alpha=0.7,
            color="#4c78a8",
        )
        axis.set_xlabel(columns[0])
        axis.set_ylabel(columns[1])
        name = "correlation_scatter"

    axis.set_title(title)
    path = _save_figure(
        figure,
        task_id,
        f"{name}.png",
        params["dpi"],
    )

    return [
        _figure_result(
            name=name,
            chart_type=chart_type,
            title=title,
            path=path,
        )
    ]


def _t_test_figures(
    dataframe: pd.DataFrame,
    task_id: str,
    params: dict[str, Any],
) -> list[dict[str, str]]:
    target = params["target_column"]
    group = params["group_column"]

    if target is None or group is None:
        raise ValueError("t 检验绘图需要 target_column 和 group_column")

    _require_columns(dataframe, [target, group])
    _require_numeric(dataframe, [target])
    plot_data = dataframe[[target, group]].dropna()
    groups = params["groups"]

    if groups:
        if len(groups) != 2:
            raise ValueError("groups 必须包含且只能包含两个类别")
        plot_data = plot_data[plot_data[group].isin(groups)]

    if plot_data.empty or plot_data[group].nunique() < 2:
        raise ValueError("t 检验箱线图至少需要两个包含有效数据的组")

    title = params["title"] or f"不同 {group} 的 {target} 分布"
    figure, axis = plt.subplots(figsize=(8, 5))
    group_values = groups or plot_data[group].drop_duplicates().tolist()
    distributions = [
        plot_data.loc[plot_data[group] == value, target].to_numpy()
        for value in group_values
    ]
    axis.boxplot(
        distributions,
        tick_labels=[str(value) for value in group_values],
        patch_artist=True,
        boxprops={"facecolor": "#9ecae1"},
    )
    random = np.random.default_rng(0)

    for position, values in enumerate(distributions, start=1):
        jitter = random.normal(0, 0.035, size=len(values))
        axis.scatter(
            np.full(len(values), position) + jitter,
            values,
            color="black",
            alpha=0.45,
            s=18,
        )

    axis.set_xlabel(group)
    axis.set_ylabel(target)
    axis.set_title(title)
    path = _save_figure(
        figure,
        task_id,
        "t_test_boxplot.png",
        params["dpi"],
    )

    return [
        _figure_result(
            name="t_test_boxplot",
            chart_type="boxplot",
            title=title,
            path=path,
        )
    ]


def _regression_figures(
    dataframe: pd.DataFrame,
    task_id: str,
    params: dict[str, Any],
) -> list[dict[str, str]]:
    target = params["target_column"]
    features = params["feature_columns"]

    if target is None or not features:
        raise ValueError(
            "回归绘图需要 target_column 和至少一个 feature_columns"
        )

    model_columns = [target] + features
    _require_columns(dataframe, model_columns)
    _require_numeric(dataframe, model_columns)
    model_data = dataframe[model_columns].replace(
        [np.inf, -np.inf],
        np.nan,
    ).dropna()

    if len(model_data) <= len(features) + 1:
        raise ValueError("有效样本数量不足，无法生成回归图")

    chart_type = params["chart_type"] or (
        "regression" if len(features) == 1 else "residual"
    )

    if chart_type in {"regression", "scatter"}:
        figures = []

        for index, feature in enumerate(features, start=1):
            title = params["title"] or f"{feature} 与 {target} 的关系"

            if params["title"] and len(features) > 1:
                title = f"{params['title']} - {feature}"

            figure, axis = plt.subplots(figsize=(8, 5))

            if chart_type == "regression":
                x_values = model_data[feature].to_numpy(dtype=float)
                y_values = model_data[target].to_numpy(dtype=float)
                axis.scatter(
                    x_values,
                    y_values,
                    alpha=0.65,
                    color="#4c78a8",
                )

                if np.unique(x_values).size > 1:
                    slope, intercept = np.polyfit(x_values, y_values, 1)
                    line_x = np.linspace(x_values.min(), x_values.max(), 100)
                    axis.plot(
                        line_x,
                        slope * line_x + intercept,
                        color="#d1495b",
                        linewidth=2,
                    )
            else:
                axis.scatter(
                    model_data[feature],
                    model_data[target],
                    alpha=0.7,
                    color="#4c78a8",
                )

            axis.set_xlabel(feature)
            axis.set_ylabel(target)
            axis.set_title(title)
            name = f"regression_{index}"
            path = _save_figure(
                figure,
                task_id,
                f"{name}.png",
                params["dpi"],
            )
            figures.append(
                _figure_result(
                    name=name,
                    chart_type=chart_type,
                    title=title,
                    path=path,
                )
            )

        return figures

    design = sm.add_constant(
        model_data[features].astype(float),
        has_constant="add",
    )
    model = sm.OLS(
        model_data[target].astype(float),
        design,
    ).fit()
    predicted = model.fittedvalues
    residuals = model.resid
    title = params["title"] or "回归模型残差图"
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.scatter(
        predicted,
        residuals,
        alpha=0.7,
        color="#4c78a8",
    )
    axis.axhline(0, color="#d1495b", linestyle="--", linewidth=1.5)
    axis.set_xlabel("预测值")
    axis.set_ylabel("残差")
    axis.set_title(title)
    path = _save_figure(
        figure,
        task_id,
        "regression_residual.png",
        params["dpi"],
    )

    return [
        _figure_result(
            name="regression_residual",
            chart_type="residual",
            title=title,
            path=path,
        )
    ]


def run(request: dict) -> dict:
    task_id, data_path, params = _validate_request(request)
    dataframe, _ = load_dataframe(data_path)
    _configure_style()
    analysis_type = params["analysis_type"]

    generators = {
        "descriptive": _descriptive_figures,
        "correlation": _correlation_figures,
        "t_test": _t_test_figures,
        "regression": _regression_figures,
    }
    figures = generators[analysis_type](
        dataframe,
        task_id,
        params,
    )

    return {"figures": figures}
