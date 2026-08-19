"""下载路由"""
import os
import shutil
import zipfile
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from services.task_manager import get_task, task_dir

router = APIRouter()


def _find_report_file(task_id: str, pattern: str) -> str | None:
    td = task_dir(task_id)
    if not td.exists():
        return None
    matches = list(td.rglob(pattern))
    if matches:
        return str(matches[0])
    return None


@router.get("/download/{task_id}/{file_type}")
async def download_file(task_id: str, file_type: str):
    """下载分析结果文件

    file_type:
      - report.md     — Markdown 报告
      - result.json   — JSON 结果
      - summary.md    — 摘要报告
      - figures.zip   — 全部图表打包
      - figures/html  — 某一 HTML 图表
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    td = task_dir(task_id)

    if file_type == "report.md":
        path = _find_report_file(task_id, "reports/*.md")
        if not path:
            raise HTTPException(status_code=404, detail="未找到报告文件")
        name = f"{task_id}_report.md"

    elif file_type == "summary.md":
        path = _find_report_file(task_id, "*_summary.md")
        if not path:
            raise HTTPException(status_code=404, detail="未找到摘要文件")
        name = f"{task_id}_summary.md"

    elif file_type == "result.json":
        path = _find_report_file(task_id, "*_result.json")
        if not path:
            raise HTTPException(status_code=404, detail="未找到结果文件")
        name = f"{task_id}_result.json"

    elif file_type == "figures.zip":
        # 打包所有图表
        zip_path = td / "figures.zip"
        figures_dir = td / "figures"
        if not figures_dir.exists() or not list(figures_dir.iterdir()):
            raise HTTPException(status_code=404, detail="未找到图表文件")
        return FileResponse(str(figures_dir / ".." / "figures.zip"))

    else:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_type}")

    return FileResponse(path, filename=name)


@router.get("/files/{task_id}")
async def list_task_files(task_id: str):
    """列出任务的所有输出文件"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    td = task_dir(task_id)
    files = []
    for f in sorted(td.rglob("*")):
        if f.is_file() and f.name != "state.json" and ".gitkeep" not in f.name:
            rel = f.relative_to(td)
            files.append({
                "name": str(rel),
                "size": f.stat().st_size,
            })
    return {"task_id": task_id, "files": files}
