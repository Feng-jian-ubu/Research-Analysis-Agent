"""数据预览路由 — 读取上传文件的前几行，返回列名和数据预览"""
import csv
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException

from services.task_manager import get_task, task_dir

router = APIRouter()


@router.get("/tasks/{task_id}/preview")
async def preview_data(task_id: str, rows: int = 10):
    """预览上传数据的前 N 行，返回列名和数据预览"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    td = task_dir(task_id)
    step_data = task.get("step_data", {})

    # 找数据文件：优先找原始上传文件
    file_path = step_data.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        # 试试 task 目录里的 CSV/XLSX：排除 anomalies.csv、state.json
        candidates = []
        for f in td.iterdir():
            if f.suffix.lower() in (".csv", ".xlsx", ".xls") and f.name != "state.json":
                # 原始上传文件（xlsx/xls）优先；CSV 中排除 anomalies.csv
                if f.name == "anomalies.csv":
                    continue
                candidates.append(f)
        # xlsx/xls 优先
        xlsx = [f for f in candidates if f.suffix.lower() in (".xlsx", ".xls")]
        csv = [f for f in candidates if f.suffix.lower() == ".csv"]
        # 选 xlsx 或最大的 CSV（通常是原始数据）
        if xlsx:
            xlsx.sort(key=lambda f: f.stat().st_size, reverse=True)
            file_path = str(xlsx[0])
        elif csv:
            csv.sort(key=lambda f: f.stat().st_size, reverse=True)
            file_path = str(csv[0])
        else:
            raise HTTPException(status_code=404, detail="未找到数据文件")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="未找到数据文件")

    ext = os.path.splitext(file_path)[1].lower()

    columns = []
    preview_rows = []
    total_rows = 0

    if ext == ".csv":
        import chardet
        # 检测编码
        with open(file_path, "rb") as f:
            raw = f.read(10000)
            detected = chardet.detect(raw)
            encoding = detected.get("encoding", "utf-8") or "utf-8"

        with open(file_path, "r", encoding=encoding, errors="replace") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i == 0:
                    columns = [c.strip() for c in row]
                else:
                    if not any(cell.strip() for cell in row):
                        continue
                    preview_rows.append([c.strip() for c in row])
                    if len(preview_rows) >= rows:
                        break
                total_rows = i  # 粗略行数

    elif ext in (".xlsx", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                columns = [str(c or "").strip() for c in row]
            else:
                vals = [str(c or "").strip() for c in row]
                if not any(v for v in vals):
                    continue
                preview_rows.append(vals)
                if len(preview_rows) >= rows:
                    break
            total_rows = i
        wb.close()

    else:
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    return {
        "task_id": task_id,
        "filename": os.path.basename(file_path),
        "file_path": file_path,
        "columns": columns,
        "total_rows": total_rows,
        "preview": preview_rows,
    }
