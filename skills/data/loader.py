"""Load CSV and Excel datasets."""

from pathlib import Path
from typing import Any

import pandas as pd


ALLOWED_SUFFIXES = {".csv", ".xls", ".xlsx"}


def _validate_loader_params(params: dict[str, Any]) -> dict[str, Any]:
    sheet_name = params.get("sheet_name", 0)
    encoding = params.get("encoding")
    delimiter = params.get("delimiter")

    if isinstance(sheet_name, bool) or not isinstance(
        sheet_name,
        (str, int),
    ):
        raise TypeError("sheet_name 必须是 string 或 integer")

    if isinstance(sheet_name, int) and sheet_name < 0:
        raise ValueError("sheet_name 序号不能小于 0")

    if isinstance(sheet_name, str) and not sheet_name.strip():
        raise ValueError("sheet_name 不能为空字符串")

    if encoding is not None and (
        not isinstance(encoding, str) or not encoding.strip()
    ):
        raise TypeError("encoding 必须是非空 string 或 null")

    if delimiter is not None and (
        not isinstance(delimiter, str) or len(delimiter) != 1
    ):
        raise TypeError("delimiter 必须是单个字符或 null")

    return {
        "sheet_name": sheet_name,
        "encoding": encoding,
        "delimiter": delimiter,
    }


def _read_csv(
    data_path: Path,
    encoding: str | None,
    delimiter: str | None,
) -> pd.DataFrame:
    separator = delimiter or ","

    if encoding is not None:
        return pd.read_csv(
            data_path,
            encoding=encoding,
            sep=separator,
        )

    decoding_errors = []

    for candidate in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(
                data_path,
                encoding=candidate,
                sep=separator,
            )
        except UnicodeDecodeError as exc:
            decoding_errors.append(str(exc))

    raise ValueError(
        "无法识别 CSV 文件编码，请通过 params.encoding 指定编码。"
        f"尝试结果: {'; '.join(decoding_errors)}"
    )


def load_dataframe(
    data_path: str,
    params: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, str]:
    if not isinstance(data_path, str) or not data_path.strip():
        raise ValueError("缺少 data_path")

    if params is None:
        params = {}

    if not isinstance(params, dict):
        raise TypeError("params 必须是 dict")

    validated = _validate_loader_params(params)
    path = Path(data_path)
    suffix = path.suffix.lower()

    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("仅支持 CSV、XLS 和 XLSX 文件")

    if not path.is_file():
        raise FileNotFoundError(f"找不到数据文件: {data_path}")

    try:
        if suffix == ".csv":
            dataframe = _read_csv(
                data_path=path,
                encoding=validated["encoding"],
                delimiter=validated["delimiter"],
            )
        else:
            dataframe = pd.read_excel(
                path,
                sheet_name=validated["sheet_name"],
            )
    except (FileNotFoundError, ValueError):
        raise
    except Exception as exc:
        raise ValueError(f"读取数据文件失败: {exc}") from exc

    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError("读取结果不是单个数据表，请指定一个 Excel 工作表")

    if dataframe.shape[1] == 0:
        raise ValueError("数据文件不包含任何字段")

    normalized_columns = [str(column) for column in dataframe.columns]

    if len(normalized_columns) != len(set(normalized_columns)):
        raise ValueError("字段名称转换为字符串后存在重复")

    dataframe = dataframe.copy()
    dataframe.columns = normalized_columns

    return dataframe, suffix.lstrip(".")


def run(request: dict) -> dict:
    if not isinstance(request, dict):
        raise TypeError("request 必须是 dict")

    dataframe, file_type = load_dataframe(
        data_path=request.get("data_path"),
        params=request.get("params", {}),
    )

    return {
        "dataframe": dataframe,
        "summary": {
            "file_type": file_type,
            "row_count": int(dataframe.shape[0]),
            "column_count": int(dataframe.shape[1]),
            "columns": dataframe.columns.tolist(),
        },
    }
