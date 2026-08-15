import json
from pathlib import Path

from backend.llm.client import chat

REPORT_SYSTEM_PROMPT="""
你是一名专业的数据分析报告撰写助手

请根据用户问题、数据集概况（数据画像）、数据清洗结果、分析计划、
统计分析结果和图表信息，生成一份完整的Markdown数据分析报告。

报告必须包含以下结构：

#数据分析报告

##1.分析问题
说明用户希望解决的问题

##2.数据集概况
介绍数据集的行数。列数、字段、缺失值和重复值等基本信息。

##3.数据清洗说明
说明数据清洗过程中执行的操作，以及清洗前后的数据量变化

##4.分析计划与方法
说明本次使用的统计分析方法及其目的。

##5.统计分析结果
准确展示并解释已有统计结果。

##6.可视化图表
使用 Markdown 图片语法插入已有图表，并简要说明图表反映的信息。

##7.分析结论
回答用户最初提出的分析问题，并总结主要发现。

写作要求：
1. 只能依据提供的分析结果撰写报告，不得虚构、修改或补充不存在的数据。
2. 不得重新计算统计指标。
3. 所有统计数值必须与输入结果保持一致。
4. 使用简洁、清晰、客观的中文。
5. 对专业统计指标进行必要解释，但避免过度展开。
6. 若结果包含 p 值，应结合显著性水平判断结果是否具有统计显著性。
7. 若提供了图表路径，应使用 Markdown 图片语法插入图表。
8. 直接输出 Markdown 报告正文，不要使用代码块包裹报告。
"""


def build_report_context(params: dict) -> str:
    context={
        "用户问题": params.get("question", ""),
        "数据集概况": params.get("profile_result", {}),
        "数据清洗结果": params.get("cleaning_result", {}),
        "分析计划": params.get("analysis_plan", {}),
        "统计分析结果": params.get("statistical_results", []),
        "图表信息": params.get("figures", []),
    }

    context_text=json.dumps(
        context,
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    return (
        "以下是本次任务的真实分析信息。"
        "请严格依据这些信息生成报告：\n\n"
        f"{context_text}"
    )

def generate_report_content(report_context: str) -> str:
    messages = [
        {
            "role": "system",
            "content": REPORT_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": report_context,
        },
    ]

    report_content = chat(
        messages=messages,
        temperature=0.0,
    )

    return report_content


def save_report(
    task_id: str,
    report_content: str,
) -> str:

    report_dir = Path("outputs/reports") / task_id
    report_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = report_dir / "report.md"

    report_path.write_text(
        report_content,
        encoding="utf-8",
    )

    return str(report_path)

def run(request: dict) -> dict:
    task_id=request["task_id"]
    params=request["params"]

    report_context=build_report_context(params)

    report_content=generate_report_content(
        report_context=report_context,
    )

    report_path=save_report(
        task_id=task_id,
        report_content=report_content,
    )

    return {
        "artifacts": [
            {
                "name": "analysis_report",
                "type": "markdown",
                "path": report_path,
            }
        ]
    }



