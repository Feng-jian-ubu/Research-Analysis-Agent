from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.plan import AnalysisPlan


TaskStatus = Literal[
    "pending",
    "profiling",
    "planning",
    "running",
    "reporting",
    "completed",
    "failed",
]


class TaskError(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str
    error_code: str | None = None
    details: dict[str, Any] | None = None


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    dataset_id: str
    status: TaskStatus
    progress: int = Field(ge=0, le=100)
    current_step: str
    plan: AnalysisPlan | None = None
    error: TaskError | None = None
    result_url: str | None = None
    created_at: datetime
    updated_at: datetime