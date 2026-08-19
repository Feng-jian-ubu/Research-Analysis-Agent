"""Research Analysis Web — FastAPI 入口"""
import sys
import os

# 确保 import 能找到同级模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from config import HOST, PORT, BASE_DIR

app = FastAPI(title="Research Analysis Web", version="1.0.0")

# CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from routers.upload import router as upload_router
from routers.analysis import router as analysis_router
from routers.download import router as download_router

app.include_router(upload_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(download_router, prefix="/api")

# 挂载前端静态文件
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "research-analysis-web"}


if __name__ == "__main__":
    import uvicorn
    print(f"🚀 启动服务: http://localhost:{PORT}")
    print(f"📖 API 文档: http://localhost:{PORT}/docs")
    uvicorn.run(app, host=HOST, port=PORT, reload=True)
