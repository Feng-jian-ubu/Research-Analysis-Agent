"""Build JSON-serializable dataset profiles."""

import math
from typing import Any

import numpy as np
import pandas as pd

from skills.data.loader import load_dataframe


def _to_python(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, pd.Timedelta):
        return str(value)

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        value = float(value)

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, np.bool_):
        return bool(value)

    try:
        return None if pd.isna(value) else value
    except (TypeError, ValueError):
        return str(value)


def _looks_like_datetime(series: pd.Series) -> bool:
    values = series.dropna().astype(str).str.strip()

    if len(values) == 0:
        return False

    date_like = values.str.contains(
        r"[-/:T年/月]",
        regex=True,
    )

    if date_like.mean() < 0.8:
        return False

    parsed = pd.to_datetime(values, errors="coerce", format="mixed")
    return bool(parsed.notna().mean() >= 0.8)


def _infer_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"

    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    if _looks_like_datetime(series):
        return "datetime"

    non_null_count = int(series.notna().sum())
    unique_count = int(series.nunique(dropna=True))
    category_limit = max(20, int(non_null_count * 0.2))

    if unique_count <= category_limit:
        return "categorical"

    return "text"


def _sample_values(series: pd.Series, limit: int = 5) -> list[Any]:
    values = series.dropna().drop_duplicates().head(limit)
    return [_to_python(value) for value in values.tolist()]


def _top_values(series: pd.Series, limit: int) -> list[dict[str, Any]]:
    if limit == 0:
        return []

    counts = series.dropna().value_counts().head(limit)
    return [
        {
            "value": _to_python(value),
            "count": int(count),
        }
        for value, count in counts.items()
    ]


def _validate_params(params: dict) -> tuple[int, int, dict[str, Any]]:
    if not isinstance(params, dict):
        raise TypeError("params 必须是 dict")

    sample_rows = params.get("sample_rows", 5)
    top_categories = params.get("top_categories", 10)

    if isinstance(sample_rows, bool) or not isinstance(sample_rows, int):
        raise TypeError("sample_rows 必须是 integer")

    if sample_rows < 0:
        raise ValueError("sample_rows 不能小于 0")

    if isinstance(top_categories, bool) or not isinstance(top_categories, int):
        raise TypeError("top_categories 必须是 integer")

    if top_categories < 0:
        raise ValueError("top_categories 不能小于 0")

    loader_params = {
        key: params.get(key)
        for key in ("sheet_name", "encoding", "delimiter")
        if key in params
    }

    return sample_rows, top_categories, loader_params


def run(request: dict) -> dict:
    if not isinstance(request, dict):
        raise TypeError("request 必须是 dict")

    params = request.get("params", {})
    sample_rows, top_categories, loader_params = _validate_params(params)
    dataframe, _ = load_dataframe(
        data_path=request.get("data_path"),
        params=loader_params,
    )

    row_count = int(dataframe.shape[0])
    columns = []

    for name in dataframe.columns:
        series = dataframe[name]
        non_null_count = int(series.notna().sum())
        missing_count = int(series.isna().sum())
        inferred_type = _infer_type(series)
        column_profile = {
            "name": name,
            "inferred_type": inferred_type,
            "dtype": str(series.dtype),
            "non_null_count": non_null_count,
            "missing_count": missing_count,
            "missing_rate": (
                round(missing_count / row_count, 6)
                if row_count > 0
                else 0.0
            ),
            "unique_count": int(series.nunique(dropna=True)),
            "sample_values": _sample_values(series),
        }

        if inferred_type in {"categorical", "boolean"}:
            column_profile["top_values"] = _top_values(
                series,
                top_categories,
            )

        columns.append(column_profile)

    preview = [
        {
            name: _to_python(value)
            for name, value in row.items()
        }
        for row in dataframe.head(sample_rows).to_dict(orient="records")
    ]

    return {
        "summary": {
            "row_count": row_count,
            "column_count": int(dataframe.shape[1]),
            "duplicate_rows": int(dataframe.duplicated().sum()),
            "total_missing": int(dataframe.isna().sum().sum()),
            "columns": columns,
            "preview": preview,
        }
    }
