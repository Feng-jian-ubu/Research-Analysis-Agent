"""分析路由 — 启动分析 & 查状态"""
import asyncio
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.task_manager import get_task, update_task, list_tasks
from services.pipeline import run_pipeline

router = APIRouter()


class AnalyzeRequest(BaseModel):
    y: str | None = None
    x: list[str] | None = None
    method: str | None = None


@router.post("/analyze/{task_id}")
async def start_analysis(task_id: str, req: AnalyzeRequest):
    """启动数据分析流水线"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    step_data = task.get("step_data", {})
    file_path = step_data.get("file_path", "")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="数据文件不存在或已被清理")

    params = {
        "y": req.y,
        "x": req.x or [],
        "method": req.method,
    }

    asyncio.create_task(run_pipeline(task_id, file_path, params))

    return {"task_id": task_id, "status": "running", "message": "分析已启动"}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态和结果"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/tasks")
async def list_recent_tasks():
    """列出最近的任务"""
    return list_tasks(limit=20)
