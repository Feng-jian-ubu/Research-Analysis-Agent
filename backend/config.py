import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
TASKS_DIR = OUTPUTS_DIR / "tasks"
FIGURES_DIR = OUTPUTS_DIR / "figures"
REPORTS_DIR = OUTPUTS_DIR / "reports"


APP_NAME = "Research Analysis Agent API"
APP_DESCRIPTION = "基于智能体的数据分析系统后端接口。"
APP_VERSION = "2.0.0"

API_PREFIX = "/api/v1"


LLM_API_KEY = (
    os.getenv("LLM_API_KEY")
    or os.getenv("OPENAI_API_KEY")
)

LLM_BASE_URL = (
    os.getenv("LLM_BASE_URL")
    or os.getenv("OPENAI_BASE_URL")
)

LLM_MODEL = (
    os.getenv("LLM_MODEL")
    or os.getenv("OPENAI_MODEL")
)

LLM_TEMPERATURE = float(
    os.getenv("LLM_TEMPERATURE", "0.0")
)


def get_frontend_origins() -> list[str]:
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


FRONTEND_ORIGINS = get_frontend_origins()


ALLOWED_FILE_SUFFIXES = {
    ".csv",
    ".xls",
    ".xlsx",
}

DEFAULT_CSV_ENCODING = "utf-8"
DEFAULT_CSV_DELIMITER = ","
DEFAULT_EXCEL_SHEET = 0

DEFAULT_SAMPLE_ROWS = 5
DEFAULT_TOP_CATEGORIES = 10

DEFAULT_ALPHA = 0.05
DEFAULT_FIGURE_DPI = 150
DEFAULT_REPORT_FORMAT = "markdown"


TASK_STATUS_PENDING = "pending"
TASK_STATUS_PLANNING = "planning"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_REPORTING = "reporting"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"