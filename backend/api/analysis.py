from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from backend.agent.main_agent import run_analysis
from backend.agent.state_manager import (
    create_task,
    get_dataset,
    update_task,
)
from backend.schemas.analysis import (
    AnalysisCreateRequest,
    AnalysisCreateResponse,
)


router = APIRouter(
    prefix="/analyses",
    tags=["analyses"],
)


def _execute_analysis(
    task_id: str,
    data_path: str,
    question: str,
    profile_result: dict,
    options: dict,
    loader_params: dict,
) -> None:
    try:
        run_analysis(
            task_id=task_id,
            data_path=data_path,
            question=question,
            profile_result=profile_result,
            options=options,
            loader_params=loader_params,
        )
    except Exception as exc:
        update_task(
            task_id=task_id,
            status="failed",
            current_step="分析任务执行失败",
            result={
                "error": {
                    "message": str(exc),
                }
            },
        )


@router.post(
    "",
    response_model=AnalysisCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_analysis(
    request: AnalysisCreateRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    dataset = get_dataset(request.dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在。",
        )

    task_id = f"task_{uuid4().hex[:12]}"

    task = create_task(
        task_id=task_id,
        dataset_id=request.dataset_id,
        question=request.question,
        options=request.options.model_dump(),
    )

    background_tasks.add_task(
        _execute_analysis,
        task_id,
        dataset["file_path"],
        request.question,
        dataset["profile"],
        request.options.model_dump(),
        dataset.get("loader_params", {}),
    )

    return {
        "task_id": task_id,
        "dataset_id": request.dataset_id,
        "status": task["status"],
        "progress": task["progress"],
        "message": "分析任务已创建。",
        "status_url": f"/api/v1/tasks/{task_id}",
        "result_url": f"/api/v1/analyses/{task_id}/result",
        "created_at": task["created_at"],
    }
