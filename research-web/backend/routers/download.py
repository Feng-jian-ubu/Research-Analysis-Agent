"""下载路由"""
import os
import io
import zipfile
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from services.task_manager import get_task, task_dir

router = APIRouter()


def _find_first(td, patterns: list[str]) -> str | None:
    """按 patterns 顺序查找第一个匹配的文件"""
    for pat in patterns:
        matches = sorted(td.rglob(pat), key=lambda f: f.stat().st_mtime, reverse=True)
        if matches:
            return str(matches[0])
    return None


_FIGURE_EXT = {".html", ".png", ".jpg", ".jpeg", ".gif", ".svg"}


@router.get("/download/{task_id}/{file_type:path}")
async def download_file(task_id: str, file_type: str):
    """下载分析结果文件

    file_type:
      - report.md       — Markdown 报告
      - result.json     — JSON 统计结果
      - summary.md      — 文本摘要
      - data.csv        — 清洗后的原始数据
      - figures.zip     — 全部图表打包
      - figures/xxx     — 具体图表文件
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    td = task_dir(task_id)

    # ── figures.zip：实时打包 ──
    if file_type == "figures.zip":
        fig_dir = td / "figures"
        if not fig_dir.exists() or not any(fig_dir.iterdir()):
            raise HTTPException(status_code=404, detail="未找到图表文件")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(fig_dir.iterdir()):
                if f.is_file():
                    zf.write(str(f), arcname=f.name)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{task_id}_figures.zip"'},
        )

    # ── 已知类型映射 ──
    type_map = {
        "report.md":   (["reports/*.md"], f"{task_id}_report.md"),
        "result.json": (["*_result.json"], f"{task_id}_result.json"),
        "summary.md":  (["*_summary.md"], f"{task_id}_summary.md"),
        "data.csv":    (["*_final.csv", "*_cleaned.csv"], f"{task_id}_data.csv"),
    }

    if file_type in type_map:
        patterns, filename = type_map[file_type]
        path = _find_first(td, patterns)
        if not path:
            raise HTTPException(status_code=404, detail="未找到文件")
        return FileResponse(path, filename=filename)

    # ── 子路径（figures/xxx.html 等）──
    sub_path = td / file_type
    if sub_path.exists() and sub_path.is_file():
        return FileResponse(str(sub_path))

    # ── 带扩展名的简单文件名（如 xxx.png）→ 在 figures/ 里搜索 ──
    ext = os.path.splitext(file_type)[1].lower()
    if ext in _FIGURE_EXT:
        found = _find_first(td, [f"**/{file_type}", f"figures/{file_type}"])
        if found:
            return FileResponse(found)

    raise HTTPException(status_code=404, detail=f"文件不存在: {file_type}")


@router.get("/files/{task_id}")
async def list_task_files(task_id: str):
    """列出任务的所有输出文件"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    td = task_dir(task_id)
    files = []
    for f in sorted(td.rglob("*")):
        if f.is_file() and f.name != "state.json":
            rel = f.relative_to(td)
            files.append({"name": str(rel), "size": f.stat().st_size})
    return {"task_id": task_id, "files": files}
