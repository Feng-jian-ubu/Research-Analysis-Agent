"""应用配置"""
import os
from pathlib import Path

# 路径
BASE_DIR = Path(__file__).resolve().parent.parent
SKILL_DIR = os.path.expanduser("~/.openclaw/workspace/skills/research-analysis/scripts")
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs" / "tasks"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 服务器
HOST = "0.0.0.0"
PORT = 8001

# 上传限制
MAX_UPLOAD_SIZE = 200 * 1024 * 1024  # 200 MB
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# 流水线步骤
PIPELINE_STEPS = [
    "uploaded",
    "loading",
    "cleaning",
    "analyzing",
    "figures",
    "report",
    "completed",
]
