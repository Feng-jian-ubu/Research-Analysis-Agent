from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ColumnProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    data_type: Literal[
        "numeric",
        "categorical",
        "datetime",
        "text",
        "boolean",
    ]
    pandas_dtype: str
    missing_count: int = Field(ge=0)
    missing_ratio: float = Field(ge=0, le=1)
    unique_count: int = Field(ge=0)
    sample_values: list[Any] = Field(default_factory=list)


class DatasetUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    status: Literal["ready"]
    file_name: str
    file_type: Literal["csv", "xls", "xlsx"]
    sheet_name: str | None = None
    file_size: int = Field(ge=0)
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    duplicate_row_count: int = Field(ge=0)
    total_missing: int = Field(ge=0)
    columns: list[ColumnProfile] = Field(default_factory=list)
    preview: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
