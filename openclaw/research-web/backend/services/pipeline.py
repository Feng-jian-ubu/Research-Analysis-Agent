"""流水线编排 — 异步调用各脚本"""
import asyncio
import os
import shutil
import subprocess
import json
from pathlib import Path

from config import SKILL_DIR, OUTPUT_DIR
from services.task_manager import update_task, task_dir


def _find_latest_file(dir_path: str, ext: str, prefix: str = "") -> str | None:
    """在目录中找到最新的匹配扩展名的文件"""
    p = Path(dir_path)
    candidates = list(p.glob(f"{prefix}*{ext}"))
    if not candidates:
        return None
    return str(sorted(candidates, key=lambda f: f.stat().st_mtime, reverse=True)[0])


async def run_pipeline(task_id: str, input_path: str, params: dict):
    """运行完整流水线"""
    try:
        await _step_loading(task_id, input_path)
        cleaned_csv = await _step_cleaning(task_id)
        await _step_analyzing(task_id, cleaned_csv, params)
        results_json = _find_latest_file(str(task_dir(task_id)), "_result.json")
        await _step_figures(task_id, cleaned_csv, results_json, params)
        await _step_report(task_id, results_json, cleaned_csv, params)
        update_task(task_id, status="completed", progress=100, step="completed",
                    message="分析完成！")

    except Exception as e:
        update_task(task_id, status="failed", message=f"错误: {str(e)}")
        raise


async def _run_script(task_id: str, script_name: str, args: list[str],
                      step: str, progress: int, message: str,
                      cwd: str | None = None) -> str:
    """运行一个脚本并更新任务状态"""
    update_task(task_id, status="running", step=step, progress=progress,
                message=message)

    script_path = os.path.join(SKILL_DIR, script_name)
    cmd = ["python3", script_path] + args

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd or str(task_dir(task_id)),
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode() if stderr else "未知错误"
        raise RuntimeError(f"{script_name} 失败:\n{error_msg[:500]}")

    return stdout.decode()


async def _step_loading(task_id: str, input_path: str):
    """步骤 1: 数据加载"""
    td = task_dir(task_id)
    await _run_script(
        task_id, "dataloader.py",
        [input_path],
        "loading", 10, "正在加载数据文件…",
        cwd=str(td),
    )

    # 找到生成的 cleaned CSV
    csv_path = _find_latest_file(str(td), "_cleaned.csv")
    if not csv_path:
        # 试试其他模式
        csv_path = _find_latest_file(str(td), ".csv")
    if not csv_path:
        raise RuntimeError("数据加载后未找到输出 CSV 文件")

    update_task(task_id, step_data={"cleaned_csv": csv_path})


async def _step_cleaning(task_id: str) -> str:
    """步骤 2: 数据清洗"""
    td = task_dir(task_id)
    state = None
    state_path = os.path.join(str(td), "state.json")
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)

    cleaned_csv = (state or {}).get("step_data", {}).get("cleaned_csv", "")
    if not cleaned_csv or not os.path.exists(cleaned_csv):
        raise RuntimeError("找不到上一步生成的 CSV 文件")

    # 复制到任务目录并重命名为原始名
    basename = os.path.basename(cleaned_csv)
    dest = os.path.join(str(td), basename)
    if cleaned_csv != dest:
        shutil.copy2(cleaned_csv, dest)
        cleaned_csv = dest

    await _run_script(
        task_id, "datacleaner.py",
        [cleaned_csv],
        "cleaning", 30, "正在清洗数据…",
        cwd=str(td),
    )

    # 找到最终 CSV
    final_csv = _find_latest_file(str(td), "_final.csv")
    if final_csv:
        update_task(task_id, step_data={"final_csv": final_csv})
        return final_csv

    # 没有 _final.csv 则返回 cleaned 本身
    update_task(task_id, step_data={"final_csv": cleaned_csv})
    return cleaned_csv


async def _step_analyzing(task_id: str, cleaned_csv: str, params: dict):
    """步骤 3: 统计分析"""
    td = task_dir(task_id)

    y = params.get("y")
    x = params.get("x", [])
    method = params.get("method", "")

    args = [cleaned_csv]

    if method:
        args.extend(["-m", method])
    if y:
        args.extend(["-y", y])
    for xi in x:
        args.extend(["-x", xi])

    await _run_script(
        task_id, "statisticsexecutor.py",
        args,
        "analyzing", 50, "正在执行统计分析…",
        cwd=str(td),
    )

    # 找到结果 JSON（尝试多种命名模式）
    result_json = _find_latest_file(str(td), "_result.json")
    if not result_json:
        # 可能命名不同，找所有 json
        result_json = _find_latest_file(str(td), ".json")
    if result_json:
        update_task(task_id, step_data={"result_json": result_json})


async def _step_figures(task_id: str, cleaned_csv: str | None,
                        results_json: str | None, params: dict):
    """步骤 4: 图表生成"""
    td = task_dir(task_id)
    if not results_json or not os.path.exists(results_json):
        update_task(task_id, message="跳过图表生成（无结果数据）")
        return

    await _run_script(
        task_id, "figuregenerator.py",
        [cleaned_csv or "", results_json, "-t", "all"],
        "figures", 70, "正在生成图表…",
        cwd=str(td),
    )


async def _step_report(task_id: str, results_json: str | None,
                       cleaned_csv: str | None, params: dict):
    """步骤 5: 报告生成"""
    td = task_dir(task_id)
    if not results_json or not os.path.exists(results_json):
        update_task(task_id, message="跳过报告生成（无结果数据）")
        return

    args = [results_json]
    if cleaned_csv:
        args.extend(["--data", cleaned_csv])

    # 查找图表前缀
    figures_dir = td / "figures"
    if figures_dir.exists() and list(figures_dir.glob("*.png")):
        args.extend(["--figure-prefix", os.path.splitext(os.path.basename(cleaned_csv or ""))[0]])

    await _run_script(
        task_id, "reportgenerator.py",
        args,
        "report", 90, "正在生成分析报告…",
        cwd=str(td),
    )
