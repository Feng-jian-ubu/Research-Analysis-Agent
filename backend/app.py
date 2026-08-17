import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.agent.state_manager import get_task
from backend.api import api_router
from backend.services.file_service import get_figure_directory


def _get_allowed_origins() -> list[str]:
    #确定哪些前端可以访问后端
    #函数的结果会交给CORSMiddleware，用于解决前端和后端端口不同导致的跨域问题。

    configured_origins = os.getenv("FRONTEND_ORIGINS")

    if configured_origins:
        return [
            origin.strip()
            for origin in configured_origins.split(",")
            if origin.strip()
        ]

    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def _is_safe_figure_name(file_name: str) -> bool:
    #检查用户请求的图表文件名是否合法
    #只能包含英文字母、数字、下划线和连字符，且必须以png结尾
    return bool(
        re.fullmatch(
            r"[A-Za-z0-9_-]+\.png",
            file_name,
            flags=re.IGNORECASE,
        )
    )


def _get_figure_file_names(
    result: dict[str, Any] | None,
) -> set[str]:
    #从分析结果中，提取出生成的图表文件名
    if not result:
        return set()

    file_names = set()

    for figure in result.get("figures", []):
        figure_path = (
            figure.get("path")
        )

        if figure_path:
            file_names.add(Path(figure_path).name)

    return file_names


app = FastAPI(
    title="Research Analysis Agent API",
    description="基于智能体的数据分析系统后端接口。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
    ],
    allow_headers=[
        "Content-Type",
        "Authorization",
    ],
)

app.include_router(
    api_router,
    prefix="/api/v1",
)


@app.get("/")
def root() -> dict:
    return {
        "name": "Research Analysis Agent API",
        "version": "1.0.0",
        "docs_url": "/docs",
    }


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "healthy",
    }


@app.get(
    "/api/v1/figures/{task_id}/{file_name}",
    response_class=FileResponse,
)
def get_figure(
    task_id: str,
    file_name: str,
) -> FileResponse:
    if not _is_safe_figure_name(file_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图表文件名不合法。",
        )

    task = get_task(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分析任务不存在。",
        )

    allowed_file_names = _get_figure_file_names(
        task.get("result"),
    )

    if file_name not in allowed_file_names:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图表不存在。",
        )

    figure_directory = get_figure_directory(task_id).resolve()
    figure_path = (figure_directory / file_name).resolve()

    if figure_path.parent != figure_directory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="图表文件名不合法。",
        )

    if not figure_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图表文件不存在。",
        )

    return FileResponse(
        path=figure_path,
        media_type="image/png",
        filename=file_name,
    )