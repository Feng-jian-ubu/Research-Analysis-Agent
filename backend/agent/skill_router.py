from importlib import import_module
from typing import Any


SKILL_REGISTRY = {
    "data_loader": "skills.data.loader",
    "data_profiler": "skills.data.profiler",
    "data_cleaner": "skills.data.cleaner",
    "descriptive": "skills.statistics.descriptive",
    "correlation": "skills.statistics.correlation",
    "t_test": "skills.statistics.t_test",
    "regression": "skills.statistics.regression",
    "figure_generator": "skills.visualization.figure_generator",
    "report_generator": "skills.report.report_generator",
}

STATISTICAL_SKILLS = {
    "descriptive",
    "correlation",
    "t_test",
    "regression",
}


def get_registered_skills() -> list[str]:
    return list(SKILL_REGISTRY.keys())


def run_skill(
    skill_name: str,
    task_id: str,
    data_path: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict:
    module_path = SKILL_REGISTRY[skill_name]
    module = import_module(module_path)

    request = {
        "task_id": task_id,
        "skill_name": skill_name,
        "params": params or {},
    }

    if data_path is not None:
        request["data_path"] = data_path

    return module.run(request)


def run_step(
    step: dict,
    task_id: str,
    data_path: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> dict:
    skill_name = step["skill_name"]
    params = dict(step.get("params", {}))

    if extra_params:
        params.update(extra_params)

    return run_skill(
        skill_name=skill_name,
        task_id=task_id,
        data_path=data_path,
        params=params,
    )