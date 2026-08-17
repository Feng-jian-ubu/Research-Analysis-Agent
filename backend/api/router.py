from fastapi import APIRouter

from backend.api.analysis import router as analysis_router
from backend.api.report import router as report_router
from backend.api.task import router as task_router
from backend.api.upload import router as upload_router


api_router = APIRouter()

api_router.include_router(upload_router)
api_router.include_router(analysis_router)
api_router.include_router(task_router)
api_router.include_router(report_router)