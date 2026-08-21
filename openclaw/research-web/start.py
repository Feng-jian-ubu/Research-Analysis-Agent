"""📊 科研数据分析平台 — 一键启动（跨目录安全版）"""
import os
import sys

# 固定到项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

# 确保能找到 backend 模块
sys.path.insert(0, os.path.join(PROJECT_DIR, "backend"))

print("📊 科研数据分析平台")
print("====================")
print()

# 检查依赖
print("📦 检查依赖…")
os.system("pip3 install -q fastapi uvicorn python-multipart aiofiles 2>/dev/null")
print()

# 导入 app
from main import app
import uvicorn

print(f"🚀 服务启动中…")
print(f"   前端页面: http://localhost:8001")
print(f"   API 文档: http://localhost:8001/docs")
print(f"   按 Ctrl+C 停止")
print()
uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
