from fastapi import APIRouter, HTTPException, status

from backend.agent.state_manager import get_task
from backend.schemas.task import TaskStatusResponse


router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
)


@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
)
def get_task_status(task_id: str) -> dict:
    task = get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析任务不存在。",
        )

    error = None

    if task["status"] == "failed":
        result = task.get("result") or {}
        error = result.get(
            "error",
            {
                "message": "分析任务执行失败。",
            },
        )

    response = {
        "task_id": task["task_id"],
        "dataset_id": task["dataset_id"],
        "status": task["status"],
        "progress": task["progress"],
        "current_step": task["current_step"],
        "plan": task["plan"],
        "error": error,
        "result_url": None,
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }

    if task["status"] == "completed":
        response["result_url"] = (
            f"/api/v1/analyses/{task_id}/result"
        )

    return response
