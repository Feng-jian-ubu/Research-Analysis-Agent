from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo


DATASETS: dict[str, dict[str, Any]] = {}
TASKS: dict[str, dict[str, Any]] = {}

_STATE_LOCK = Lock()
_TIMEZONE = ZoneInfo("Asia/Singapore")


def _current_time() -> str:
    return datetime.now(_TIMEZONE).isoformat(timespec="seconds")


def create_dataset(
    dataset_id: str,
    file_name: str,
    file_path: str,
    profile: dict,
    loader_params: dict | None = None,
    file_type: str | None = None,
    file_size: int = 0,
    sheet_name: str | None = None,
) -> dict:
    now = _current_time()

    dataset = {
        "dataset_id": dataset_id,
        "file_name": file_name,
        "file_path": file_path,
        "profile": profile,
        "loader_params": loader_params or {},
        "file_type": (
            file_type
            or Path(file_name).suffix.lower().lstrip(".")
        ),
        "file_size": file_size,
        "sheet_name": sheet_name,
        "created_at": now,
    }

    with _STATE_LOCK:
        DATASETS[dataset_id] = dataset

    return deepcopy(dataset)


def get_dataset(dataset_id: str) -> dict | None:
    with _STATE_LOCK:
        dataset = DATASETS.get(dataset_id)

    return deepcopy(dataset) if dataset is not None else None


def create_task(
    task_id: str,
    dataset_id: str,
    question: str,
    options: dict | None = None,
) -> dict:
    now = _current_time()

    task = {
        "task_id": task_id,
        "dataset_id": dataset_id,
        "question": question,
        "options": options or {},
        "status": "pending",
        "progress": 0,
        "current_step": "任务已创建",
        "plan": None,
        "result": None,
        "created_at": now,
        "updated_at": now,
    }

    with _STATE_LOCK:
        TASKS[task_id] = task

    return deepcopy(task)


def get_task(task_id: str) -> dict | None:
    with _STATE_LOCK:
        task = TASKS.get(task_id)

    return deepcopy(task) if task is not None else None


def update_task(
    task_id: str,
    status: str | None = None,
    progress: int | None = None,
    current_step: str | None = None,
    plan: dict | None = None,
    result: dict | None = None,
) -> dict:
    with _STATE_LOCK:
        task = TASKS[task_id]

        if status is not None:
            task["status"] = status

        if progress is not None:
            task["progress"] = max(0, min(100, progress))

        if current_step is not None:
            task["current_step"] = current_step

        if plan is not None:
            task["plan"] = plan

        if result is not None:
            task["result"] = result

        task["updated_at"] = _current_time()

        updated_task = deepcopy(task)

    return updated_task


def save_task_result(task_id: str, result: dict) -> dict:
    return update_task(
        task_id=task_id,
        status="completed",
        progress=100,
        current_step="分析完成",
        result=result,
    )


def list_datasets() -> list[dict]:
    with _STATE_LOCK:
        datasets = list(DATASETS.values())

    return deepcopy(datasets)


def list_tasks() -> list[dict]:
    with _STATE_LOCK:
        tasks = list(TASKS.values())

    return deepcopy(tasks)
