from copy import deepcopy
from typing import Any

from backend.agent.planner import create_analysis_plan
from backend.agent.skill_router import (
    STATISTICAL_SKILLS,
    run_step,
)
from backend.agent.state_manager import (
    save_task_result,
    update_task,
)


STEP_NAMES = {
    "data_cleaner": "正在清洗数据",
    "descriptive": "正在执行描述性统计",
    "correlation": "正在执行相关分析",
    "t_test": "正在执行独立样本 t 检验",
    "regression": "正在执行回归分析",
    "figure_generator": "正在生成可视化图表",
    "report_generator": "正在生成分析报告",
}


def _get_artifact_path(
    result: dict,
    artifact_name: str,
) -> str | None:
    for artifact in result.get("artifacts", []):
        if artifact.get("name") == artifact_name:
            return artifact.get("path")

    return None


def _prepare_report_params(
    question: str,
    profile_result: dict,
    cleaning_result: dict,
    analysis_plan: dict,
    statistical_results: list[dict],
    figures: list[dict],
    original_params: dict,
) -> dict:
    return {
        **original_params,
        "question": question,
        "profile_result": profile_result,
        "cleaning_result": cleaning_result,
        "analysis_plan": analysis_plan,
        "statistical_results": statistical_results,
        "figures": figures,
        "output_format": "markdown",
    }


def run_analysis(
    task_id: str,
    data_path: str,
    question: str,
    profile_result: dict[str, Any],
    options: dict[str, Any] | None = None,
    loader_params: dict[str, Any] | None = None,
) -> dict:
    update_task(
        task_id=task_id,
        status="planning",
        progress=10,
        current_step="正在生成分析计划",
    )

    analysis_plan = create_analysis_plan(
        question=question,
        profile_result=profile_result,
        options=options or {},
    )

    update_task(
        task_id=task_id,
        status="planning",
        progress=20,
        current_step="分析计划已生成",
        plan=analysis_plan,
    )

    current_data_path = data_path
    cleaning_result: dict = {}
    statistical_results: list[dict] = []
    figures: list[dict] = []
    report_result: dict = {}

    steps = deepcopy(analysis_plan["steps"])
    total_steps = len(steps)

    for index, step in enumerate(steps, start=1):
        skill_name = step["skill_name"]

        progress = 20 + int((index - 1) / total_steps * 70)

        if skill_name == "report_generator":
            status = "reporting"
        else:
            status = "running"

        update_task(
            task_id=task_id,
            status=status,
            progress=progress,
            current_step=STEP_NAMES[skill_name],
        )

        if skill_name == "report_generator":
            report_params = _prepare_report_params(
                question=question,
                profile_result=profile_result,
                cleaning_result=cleaning_result,
                analysis_plan=analysis_plan,
                statistical_results=statistical_results,
                figures=figures,
                original_params=step.get("params", {}),
            )

            report_result = run_step(
                step=step,
                task_id=task_id,
                data_path=current_data_path,
                extra_params=report_params,
            )

            continue

        result = run_step(
            step=step,
            task_id=task_id,
            data_path=current_data_path,
            extra_params=(
                loader_params
                if skill_name == "data_cleaner"
                else None
            ),
        )

        if skill_name == "data_cleaner":
            cleaning_result = result

            cleaned_data_path = _get_artifact_path(
                result=result,
                artifact_name="cleaned_data",
            )

            if cleaned_data_path is not None:
                current_data_path = cleaned_data_path

        elif skill_name in STATISTICAL_SKILLS:
            statistical_results.append(
                {
                    "skill_name": skill_name,
                    **result,
                }
            )

        elif skill_name == "figure_generator":
            figures.extend(result.get("figures", []))

    report_path = _get_artifact_path(
        result=report_result,
        artifact_name="analysis_report",
    )

    final_result = {
        "task_id": task_id,
        "question": question,
        "analysis_plan": analysis_plan,
        "profile_result": profile_result,
        "cleaning_result": cleaning_result,
        "statistical_results": statistical_results,
        "figures": figures,
        "report": {
            "path": report_path,
            "artifacts": report_result.get("artifacts", []),
        },
    }

    save_task_result(
        task_id=task_id,
        result=final_result,
    )

    return final_result
