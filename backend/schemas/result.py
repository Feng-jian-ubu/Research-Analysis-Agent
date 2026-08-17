from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.plan import AnalysisPlan


class ResultTable(BaseModel):
    model_config = ConfigDict(extra="allow")

    table_id: str | None = None
    title: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Figure(BaseModel):
    model_config = ConfigDict(extra="allow")

    figure_id: str | None = None
    title: str | None = None
    type: str | None = None
    url: str
    alt_text: str | None = None


class Artifact(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    path: str | None = None


class StatisticalResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    skill_name: str
    summary: dict[str, Any] = Field(default_factory=dict)
    tables: list[ResultTable] = Field(default_factory=list)


class AnalysisResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    dataset_id: str
    status: str
    question: str
    analysis_plan: AnalysisPlan
    profile_result: dict[str, Any] = Field(default_factory=dict)
    cleaning_result: dict[str, Any] = Field(default_factory=dict)
    statistical_results: list[StatisticalResult] = Field(
        default_factory=list,
    )
    figures: list[Figure] = Field(default_factory=list)
    report_download_url: str
    completed_at: datetime
