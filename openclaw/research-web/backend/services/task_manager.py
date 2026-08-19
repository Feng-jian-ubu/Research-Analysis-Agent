"""任务管理器 — 基于文件的状态管理"""
import json
import os
import time
import uuid
from pathlib import Path
from config import OUTPUT_DIR


def new_task() -> str:
    """创建新任务，返回 task_id"""
    task_id = uuid.uuid4().hex[:12]
    task_dir = OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "step": "",
        "message": "",
        "original_filename": "",
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _write_state(task_id, state)
    return task_id


def get_task(task_id: str) -> dict | None:
    """获取任务状态"""
    path = _state_path(task_id)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def update_task(task_id: str, **kwargs):
    """更新任务状态字段"""
    state = get_task(task_id)
    if state is None:
        return
    for k, v in kwargs.items():
        state[k] = v
    state["updated_at"] = time.time()
    _write_state(task_id, state)


def list_tasks(limit: int = 20) -> list[dict]:
    """列出最近任务"""
    if not OUTPUT_DIR.exists():
        return []
    tasks = []
    for d in sorted(OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        state_path = d / "state.json"
        if state_path.exists():
            with open(state_path) as f:
                tasks.append(json.load(f))
        if len(tasks) >= limit:
            break
    return tasks


def task_dir(task_id: str) -> Path:
    """任务数据目录"""
    return OUTPUT_DIR / task_id


def _state_path(task_id: str) -> Path:
    return OUTPUT_DIR / task_id / "state.json"


def _write_state(task_id: str, state: dict):
    _state_path(task_id).parent.mkdir(parents=True, exist_ok=True)
    with open(_state_path(task_id), "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
