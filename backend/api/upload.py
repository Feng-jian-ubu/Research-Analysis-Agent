from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from backend.agent.skill_router import run_skill
from backend.agent.state_manager import create_dataset, get_dataset
from backend.schemas.dataset import DatasetUploadResponse
from backend.services.file_service import save_upload_file


router = APIRouter(
    prefix="/datasets",
    tags=["datasets"],
)


def _format_columns(profile: dict) -> list[dict]:
    columns = []

    for column in profile.get("columns", []):
        columns.append(
            {
                "name": column["name"],
                "data_type": column.get(
                    "inferred_type",
                    column.get("data_type"),
                ),
                "pandas_dtype": column.get(
                    "dtype",
                    column.get("pandas_dtype"),
                ),
                "missing_count": column.get("missing_count", 0),
                "missing_ratio": column.get(
                    "missing_rate",
                    column.get("missing_ratio", 0),
                ),
                "unique_count": column.get("unique_count", 0),
                "sample_values": column.get("sample_values", []),
            }
        )

    return columns


def _dataset_response(dataset: dict) -> dict:
    profile = dataset["profile"]

    return {
        "dataset_id": dataset["dataset_id"],
        "status": "ready",
        "file_name": dataset["file_name"],
        "file_type": dataset["file_type"],
        "sheet_name": dataset.get("sheet_name"),
        "file_size": dataset.get("file_size", 0),
        "row_count": profile.get("row_count", 0),
        "column_count": profile.get("column_count", 0),
        "duplicate_row_count": profile.get(
            "duplicate_rows",
            profile.get("duplicate_row_count", 0),
        ),
        "total_missing": profile.get("total_missing", 0),
        "columns": _format_columns(profile),
        "preview": profile.get("preview", []),
        "created_at": dataset["created_at"],
    }


@router.post(
    "",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset(
    file: UploadFile = File(...),
    sheet_name: str | None = Form(default=None),
) -> dict:
    dataset_id = f"ds_{uuid4().hex[:8]}"

    file_info = await save_upload_file(
        upload_file=file,
        dataset_id=dataset_id,
    )

    file_path = file_info["file_path"]
    file_suffix = Path(file_info["file_name"]).suffix.lower()

    loader_params = {
        "sheet_name": sheet_name if sheet_name is not None else 0,
        "encoding": None,
        "delimiter": None,
    }

    run_skill(
        skill_name="data_loader",
        task_id=dataset_id,
        data_path=file_path,
        params=loader_params,
    )

    profiler_result = run_skill(
        skill_name="data_profiler",
        task_id=dataset_id,
        data_path=file_path,
        params={
            "sample_rows": 5,
            "top_categories": 10,
            **loader_params,
        },
    )

    profile = profiler_result["summary"]

    dataset = create_dataset(
        dataset_id=dataset_id,
        file_name=file_info["file_name"],
        file_path=file_path,
        profile=profile,
        loader_params=loader_params,
        file_type=file_suffix.lstrip("."),
        file_size=file_info["file_size"],
        sheet_name=sheet_name,
    )

    return _dataset_response(dataset)


@router.get(
    "/{dataset_id}/profile",
    response_model=DatasetUploadResponse,
)
def get_dataset_profile(dataset_id: str) -> dict:
    dataset = get_dataset(dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在。",
        )

    return _dataset_response(dataset)
