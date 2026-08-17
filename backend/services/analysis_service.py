from typing import Any
from uuid import uuid4

from backend.agent.main_agent import run_analysis
from backend.agent.state_manager import (
    create_task,
    get_dataset,
    get_task,
)
from backend.services.file_service import create_task_directories


def create_analysis_task(
    dataset_id: str,
    question: str,
    options: dict[str, Any] | None = None,
) -> dict:
    dataset = get_dataset(dataset_id)

    if dataset is None:
        raise ValueError("数据集不存在。")

    task_id = f"task_{uuid4().hex[:12]}"

    create_task_directories(task_id)

    return create_task(
        task_id=task_id,
        dataset_id=dataset_id,
        question=question,
        options=options or {},
    )


def execute_analysis(task_id: str) -> dict:
    task = get_task(task_id)

    if task is None:
        raise ValueError("分析任务不存在。")

    dataset = get_dataset(task["dataset_id"])

    if dataset is None:
        raise ValueError("数据集不存在。")

    return run_analysis(
        task_id=task_id,
        data_path=dataset["file_path"],
        question=task["question"],
        profile_result=dataset["profile"],
        options=task["options"],
        loader_params=dataset.get("loader_params", {}),
    )
