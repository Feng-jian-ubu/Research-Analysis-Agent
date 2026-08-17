from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SkillName = Literal[
    "data_cleaner",
    "descriptive",
    "correlation",
    "t_test",
    "regression",
    "figure_generator",
    "report_generator",
]


class AnalysisStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: SkillName
    params: dict[str, Any] = Field(default_factory=dict)


class AnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    steps: list[AnalysisStep] = Field(min_length=1)