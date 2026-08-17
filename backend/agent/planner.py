import json
import re
from typing import Any

from backend.llm.client import chat
from backend.llm.prompts import (
    PLANNER_SYSTEM_PROMPT,
    build_planner_user_prompt,
)


ALLOWED_SKILLS = {
    "data_cleaner",
    "descriptive",
    "correlation",
    "t_test",
    "regression",
    "figure_generator",
    "report_generator",
}

STATISTICAL_SKILLS = {
    "descriptive",
    "correlation",
    "t_test",
    "regression",
}


def _extract_json(response_text: str) -> dict:
    text = response_text.strip()

    code_block = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        flags=re.DOTALL,
    )

    if code_block:
        text = code_block.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:
            text = text[start:end + 1]

    return json.loads(text)


def _normalize_plan(plan: dict, question: str) -> dict:
    normalized_steps = []

    for step in plan.get("steps", []):
        skill_name = step.get("skill_name")

        if skill_name not in ALLOWED_SKILLS:
            continue

        normalized_steps.append(
            {
                "skill_name": skill_name,
                "params": step.get("params", {}),
            }
        )

    if not any(
        step["skill_name"] == "data_cleaner"
        for step in normalized_steps
    ):
        normalized_steps.insert(
            0,
            {
                "skill_name": "data_cleaner",
                "params": {
                    "columns": [],
                    "drop_duplicates": True,
                    "missing_strategy": "drop_required",
                    "required_columns": [],
                    "output_format": "csv",
                },
            },
        )

    if not any(
        step["skill_name"] in STATISTICAL_SKILLS
        for step in normalized_steps
    ):
        normalized_steps.append(
            {
                "skill_name": "descriptive",
                "params": {
                    "columns": [],
                    "group_by": None,
                    "include_percentiles": True,
                },
            }
        )

    if not any(
        step["skill_name"] == "figure_generator"
        for step in normalized_steps
    ):
        analysis_type = next(
            step["skill_name"]
            for step in normalized_steps
            if step["skill_name"] in STATISTICAL_SKILLS
        )

        normalized_steps.append(
            {
                "skill_name": "figure_generator",
                "params": {
                    "analysis_type": analysis_type,
                    "chart_type": None,
                    "columns": [],
                    "target_column": None,
                    "group_column": None,
                    "feature_columns": [],
                    "title": None,
                    "dpi": 150,
                },
            }
        )

    if not any(
        step["skill_name"] == "report_generator"
        for step in normalized_steps
    ):
        normalized_steps.append(
            {
                "skill_name": "report_generator",
                "params": {
                    "output_format": "markdown",
                },
            }
        )

    return {
        "question": plan.get("question", question),
        "steps": normalized_steps,
    }


def create_analysis_plan(
    question: str,
    profile_result: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> dict:
    user_prompt = build_planner_user_prompt(
        question=question,
        profile_result=profile_result,
        options=options or {},
    )

    messages = [
        {
            "role": "system",
            "content": PLANNER_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    response_text = chat(messages)
    plan = _extract_json(response_text)

    return _normalize_plan(
        plan=plan,
        question=question,
    )