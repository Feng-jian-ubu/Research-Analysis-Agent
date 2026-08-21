"""Research Analysis Web — FastAPI 入口"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from config import HOST, PORT, BASE_DIR

app = FastAPI(title="Research Analysis Web", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由（必须先注册，避免被静态文件拦截）
from routers.upload import router as upload_router
from routers.analysis import router as analysis_router
from routers.download import router as download_router
from routers.preview import router as preview_router
from routers.events import router as events_router

app.include_router(upload_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(download_router, prefix="/api")
app.include_router(preview_router, prefix="/api")
app.include_router(events_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "research-analysis-web"}


# 前端静态文件 — 使用单独的子路由，根路径用 catch-all
frontend_dir = BASE_DIR / "frontend"

# 先挂载 css/js 等静态资源
for sub in ["css", "js"]:
    sub_path = frontend_dir / sub
    if sub_path.exists():
        app.mount(f"/{sub}", StaticFiles(directory=str(sub_path)), name=sub)


# 根路径 → index.html
@app.get("/")
async def serve_index():
    return FileResponse(str(frontend_dir / "index.html"))


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 启动服务: http://localhost:{PORT}")
    print(f"📖 API 文档: http://localhost:{PORT}/docs")
    uvicorn.run(app, host=HOST, port=PORT)
