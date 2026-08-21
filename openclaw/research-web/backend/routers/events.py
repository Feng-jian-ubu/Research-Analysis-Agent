"""SSE 事件推送路由 — 替代前端轮询"""
import asyncio
import json
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from services.task_manager import get_task, task_dir

router = APIRouter()


@router.get("/events/{task_id}")
async def task_events(task_id: str):
    """Server-Sent Events: 实时推送任务状态变化"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    state_path = task_dir(task_id) / "state.json"

    async def event_generator():
        last_updated = 0

        while True:
            try:
                if state_path.exists():
                    with open(state_path) as f:
                        state = json.load(f)
                    updated = state.get("updated_at", 0)

                    if updated > last_updated:
                        last_updated = updated
                        step_data = state.get("step_data", {})
                        event = "message"

                        # 完成/失败时发特定事件
                        if state.get("status") == "completed":
                            event = "completed"
                        elif state.get("status") == "failed":
                            event = "error"

                        data = json.dumps({
                            "task_id": task_id,
                            "status": state.get("status", ""),
                            "step": state.get("step", ""),
                            "progress": state.get("progress", 0),
                            "message": state.get("message", ""),
                            "step_data": {
                                "recommended_method": step_data.get("recommended_method", ""),
                                "files": step_data.get("files", []),
                            },
                        }, ensure_ascii=False)

                        yield f"event: {event}\ndata: {data}\n\n"

                    # 完成或失败后延迟发送关闭事件，然后退出
                    if state.get("status") in ("completed", "failed"):
                        yield f"event: done\ndata: {json.dumps({'status': state.get('status')})}\n\n"
                        return

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception:
                # 文件读写异常时继续尝试
                await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
