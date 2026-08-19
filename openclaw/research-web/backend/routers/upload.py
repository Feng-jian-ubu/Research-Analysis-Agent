"""上传路由"""
import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from config import UPLOAD_DIR, ALLOWED_EXTENSIONS, OUTPUT_DIR
from services.task_manager import new_task, update_task, task_dir

router = APIRouter()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传数据文件，返回 task_id"""
    # 校验扩展名
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，支持 {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 创建任务
    task_id = new_task()
    update_task(task_id, status="uploading", progress=5,
                message="接收文件中…", original_filename=file.filename or "unknown")

    # 保存文件
    task_in_dir = task_dir(task_id)
    save_path = os.path.join(str(task_in_dir), file.filename or f"data{ext}")

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    update_task(task_id, status="ready", progress=10,
                message="文件上传完成，请配置分析参数",
                step="ready",
                step_data={"file_path": save_path, "filename": file.filename})

    return {
        "task_id": task_id,
        "filename": file.filename,
        "size": len(content),
        "message": "上传成功",
    }
