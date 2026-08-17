from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.agent.state_manager import get_task
from backend.schemas.result import AnalysisResultResponse


router = APIRouter(tags=["results"])


def _figure_url(
    task_id: str,
    figure: dict[str, Any],
) -> dict[str, Any]:
    converted = dict(figure)

    figure_path = (
        converted.get("path")
        or converted.get("file_path")
        or converted.get("url")
    )

    if figure_path:
        file_name = Path(figure_path).name
        converted.pop("path", None)
        converted.pop("file_path", None)
        converted["url"] = (
            f"/api/v1/figures/{task_id}/{file_name}"
        )

    return converted


def _get_report_path(result: dict[str, Any]) -> str | None:
    report = result.get("report", {})

    if report.get("path"):
        return report["path"]

    for artifact in report.get("artifacts", []):
        if artifact.get("name") == "analysis_report":
            return artifact.get("path")

    return None


@router.get(
    "/analyses/{task_id}/result",
    response_model=AnalysisResultResponse,
)
def get_analysis_result(task_id: str) -> dict:
    task = get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析任务不存在。",
        )

    if task["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="分析任务尚未完成。",
        )

    result = dict(task["result"])
    figures = [
        _figure_url(task_id, figure)
        for figure in result.get("figures", [])
    ]

    return {
        "task_id": task["task_id"],
        "dataset_id": task["dataset_id"],
        "status": task["status"],
        "question": task["question"],
        "analysis_plan": result.get("analysis_plan"),
        "profile_result": result.get("profile_result", {}),
        "cleaning_result": result.get("cleaning_result", {}),
        "statistical_results": result.get(
            "statistical_results",
            [],
        ),
        "figures": figures,
        "report_download_url": (
            f"/api/v1/reports/{task_id}/download"
        ),
        "completed_at": task["updated_at"],
    }


@router.get("/reports/{task_id}/download")
def download_report(task_id: str) -> FileResponse:
    task = get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析任务不存在。",
        )

    if task["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="分析任务尚未完成。",
        )

    report_path = _get_report_path(task["result"])

    if report_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析报告不存在。",
        )

    path = Path(report_path)

    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析报告文件不存在。",
        )

    return FileResponse(
        path=path,
        media_type="text/markdown",
        filename=f"analysis_report_{task_id}.md",
    )
