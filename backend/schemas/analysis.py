from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alpha: float = Field(default=0.05, gt=0, lt=1)


class AnalysisCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    dataset_id: str = Field(min_length=1)
    question: str = Field(min_length=2, max_length=1000)
    options: AnalysisOptions = Field(
        default_factory=AnalysisOptions,
    )


class AnalysisCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    dataset_id: str
    status: Literal["pending"]
    progress: int = Field(ge=0, le=100)
    message: str
    status_url: str
    result_url: str
    created_at: datetime