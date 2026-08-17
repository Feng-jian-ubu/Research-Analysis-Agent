"""Apply deterministic duplicate and missing-value cleaning."""

import re
from typing import Any

import pandas as pd

from backend.services.file_service import get_task_data_path
from skills.data.loader import load_dataframe


MISSING_STRATEGIES = {
    "drop_required",
    "drop_rows",
    "mean",
    "median",
    "mode",
    "none",
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

    columns = _validate_string_list(params.get("columns", []), "columns")
    required_columns = _validate_string_list(
        params.get("required_columns", []),
        "required_columns",
    )
    drop_duplicates = params.get("drop_duplicates", True)

    if not isinstance(drop_duplicates, bool):
        raise TypeError("drop_duplicates 必须是 boolean")

    missing_strategy = params.get("missing_strategy", "drop_required")

    if missing_strategy not in MISSING_STRATEGIES:
        raise ValueError(
            "missing_strategy 必须是 drop_required、drop_rows、"
            "mean、median、mode 或 none"
        )

    output_format = params.get("output_format", "csv")

    if output_format != "csv":
        raise ValueError("output_format 目前只支持 csv")

    normalized = {
        "columns": columns,
        "required_columns": required_columns,
        "drop_duplicates": drop_duplicates,
        "missing_strategy": missing_strategy,
        "output_format": output_format,
        "sheet_name": params.get("sheet_name", 0),
        "encoding": params.get("encoding"),
        "delimiter": params.get("delimiter"),
    }

    return task_id, data_path, normalized


def _impute_numeric(
    dataframe: pd.DataFrame,
    strategy: str,
) -> int:
    values_imputed = 0

    for column in dataframe.select_dtypes(include="number").columns:
        missing_count = int(dataframe[column].isna().sum())

        if missing_count == 0:
            continue

        if strategy == "mean":
            fill_value = dataframe[column].mean()
        else:
            fill_value = dataframe[column].median()

        if pd.isna(fill_value):
            continue

        dataframe[column] = dataframe[column].fillna(fill_value)
        values_imputed += missing_count

    return values_imputed


def _impute_mode(dataframe: pd.DataFrame) -> int:
    values_imputed = 0

    for column in dataframe.columns:
        missing_count = int(dataframe[column].isna().sum())

        if missing_count == 0:
            continue

        modes = dataframe[column].mode(dropna=True)

        if modes.empty:
            continue

        dataframe[column] = dataframe[column].fillna(modes.iloc[0])
        values_imputed += missing_count

    return values_imputed


def run(request: dict) -> dict:
    task_id, data_path, params = _validate_request(request)
    loader_params = {
        "sheet_name": params["sheet_name"],
        "encoding": params["encoding"],
        "delimiter": params["delimiter"],
    }
    dataframe, _ = load_dataframe(data_path, loader_params)
    input_rows = int(len(dataframe))
    columns = params["columns"] or dataframe.columns.tolist()
    required_columns = params["required_columns"]

    missing_columns = [
        column
        for column in columns + required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"以下字段不存在于数据文件中: {sorted(set(missing_columns))}"
        )

    if any(column not in columns for column in required_columns):
        raise ValueError("required_columns 必须包含在 columns 中")

    cleaned = dataframe[columns].copy()
    operations = []
    duplicates_removed = 0
    rows_removed_for_missing = 0
    values_imputed = 0

    if params["drop_duplicates"]:
        rows_before = len(cleaned)
        cleaned = cleaned.drop_duplicates().copy()
        duplicates_removed = rows_before - len(cleaned)
        operations.append(f"删除 {duplicates_removed} 行完全重复记录")

    strategy = params["missing_strategy"]

    if strategy == "drop_required":
        if required_columns:
            rows_before = len(cleaned)
            cleaned = cleaned.dropna(subset=required_columns).copy()
            rows_removed_for_missing = rows_before - len(cleaned)
        operations.append(
            "删除分析必需字段含缺失值的 "
            f"{rows_removed_for_missing} 行记录"
        )
    elif strategy == "drop_rows":
        rows_before = len(cleaned)
        cleaned = cleaned.dropna().copy()
        rows_removed_for_missing = rows_before - len(cleaned)
        operations.append(
            f"删除任意字段含缺失值的 {rows_removed_for_missing} 行记录"
        )
    elif strategy in {"mean", "median"}:
        values_imputed = _impute_numeric(cleaned, strategy)
        method_name = "均值" if strategy == "mean" else "中位数"
        operations.append(f"使用{method_name}填补 {values_imputed} 个数值")
    elif strategy == "mode":
        values_imputed = _impute_mode(cleaned)
        operations.append(f"使用众数填补 {values_imputed} 个值")
    else:
        operations.append("未处理缺失值")

    output_path = get_task_data_path(task_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_path, index=False, encoding="utf-8-sig")

    return {
        "summary": {
            "input_rows": input_rows,
            "output_rows": int(len(cleaned)),
            "duplicates_removed": int(duplicates_removed),
            "rows_removed_for_missing": int(rows_removed_for_missing),
            "values_imputed": int(values_imputed),
            "operations": operations,
        },
        "artifacts": [
            {
                "name": "cleaned_data",
                "type": "csv",
                "path": str(output_path),
            }
        ],
    }
