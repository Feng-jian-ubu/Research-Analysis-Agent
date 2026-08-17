import re
from pathlib import Path
from typing import Any

from fastapi import UploadFile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

UPLOADS_DIR = OUTPUTS_DIR / "uploads"
TASKS_DIR = OUTPUTS_DIR / "tasks"
FIGURES_DIR = OUTPUTS_DIR / "figures"
REPORTS_DIR = OUTPUTS_DIR / "reports"

ALLOWED_FILE_SUFFIXES = {
    ".csv",
    ".xls",
    ".xlsx",
}


def _sanitize_file_name(file_name: str) -> str:
    original_name = Path(file_name).name
    safe_name = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]',
        "_",
        original_name,
    )

    return safe_name or "dataset.csv"


def _ensure_allowed_file(file_name: str) -> None:
    suffix = Path(file_name).suffix.lower()

    if suffix not in ALLOWED_FILE_SUFFIXES:
        raise ValueError(
            "仅支持 CSV、XLS 和 XLSX 文件。"
        )


def get_upload_directory(dataset_id: str) -> Path:
    return UPLOADS_DIR / dataset_id


def get_task_directory(task_id: str) -> Path:
    return TASKS_DIR / task_id


def get_figure_directory(task_id: str) -> Path:
    return FIGURES_DIR / task_id


def get_report_directory(task_id: str) -> Path:
    return REPORTS_DIR / task_id


def get_upload_path(
    dataset_id: str,
    file_name: str,
) -> Path:
    safe_name = _sanitize_file_name(file_name)
    suffix = Path(safe_name).suffix.lower()

    return get_upload_directory(dataset_id) / f"original{suffix}"


def get_task_data_path(
    task_id: str,
    file_name: str = "cleaned.csv",
) -> Path:
    safe_name = _sanitize_file_name(file_name)

    return get_task_directory(task_id) / safe_name


def get_figure_path(
    task_id: str,
    file_name: str,
) -> Path:
    safe_name = _sanitize_file_name(file_name)

    return get_figure_directory(task_id) / safe_name


def get_report_path(
    task_id: str,
    file_name: str = "report.md",
) -> Path:
    safe_name = _sanitize_file_name(file_name)

    return get_report_directory(task_id) / safe_name


def create_dataset_directory(dataset_id: str) -> Path:
    directory = get_upload_directory(dataset_id)
    directory.mkdir(parents=True, exist_ok=True)

    return directory


def create_task_directories(
    task_id: str,
) -> dict[str, Path]:
    directories = {
        "task": get_task_directory(task_id),
        "figures": get_figure_directory(task_id),
        "reports": get_report_directory(task_id),
    }

    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)

    return directories


async def save_upload_file(
    upload_file: UploadFile,
    dataset_id: str,
) -> dict[str, Any]:
    original_file_name = upload_file.filename or "dataset.csv"
    safe_file_name = _sanitize_file_name(original_file_name)

    _ensure_allowed_file(safe_file_name)
    create_dataset_directory(dataset_id)

    file_path = get_upload_path(
        dataset_id=dataset_id,
        file_name=safe_file_name,
    )

    file_size = 0

    with file_path.open("wb") as file_object:
        while chunk := await upload_file.read(1024 * 1024):
            file_object.write(chunk)
            file_size += len(chunk)

    await upload_file.close()

    return {
        "dataset_id": dataset_id,
        "file_name": safe_file_name,
        "file_path": str(file_path),
        "file_size": file_size,
    }


def path_to_api_url(
    file_path: str | Path,
    task_id: str,
) -> str:
    path = Path(file_path)
    file_name = path.name

    if REPORTS_DIR in path.parents:
        return f"/api/v1/reports/{task_id}/download"

    if FIGURES_DIR in path.parents:
        return f"/api/v1/figures/{task_id}/{file_name}"

    return str(path)