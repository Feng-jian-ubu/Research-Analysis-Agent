"""流水线编排 — 异步调用各脚本"""
import asyncio
import json
import os
import shutil
import re
from pathlib import Path

from config import SKILL_DIR
from services.task_manager import update_task, task_dir


# ─── 工具函数 ────────────────────────────────────────────


def _find_in_dir(dir_path: str, pattern: str) -> str | None:
    """在目录里找符合 pattern 的文件，返回最新那个的绝对路径"""
    p = Path(dir_path)
    matches = sorted(p.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else None


def _output_name(input_path: str, suffix: str) -> str:
    """根据输入文件路径生成同目录输出路径"""
    d = os.path.dirname(input_path) or "."
    base = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(d, f"{base}{suffix}")


def _collect_outputs(td: Path, task_id: str) -> dict:
    """扫描 task 目录，收集所有结果文件信息"""
    files = []
    for f in sorted(td.rglob("*")):
        if f.is_file() and f.name != "state.json":
            rel = f.relative_to(td)
            files.append({"name": str(rel), "size": f.stat().st_size})
    update_task(task_id, step_data={"files": files})
    return files


# ─── 脚本执行 ────────────────────────────────────────────


async def _run_script(task_id: str, script_name: str, args: list[str],
                      step: str, progress: int, message: str,
                      cwd: str | None = None) -> tuple[str, str]:
    """运行脚本，返回 (stdout, stderr)"""
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
        err = stderr.decode()[:1000] if stderr else "未知错误"
        out = stdout.decode()[:500] if stdout else ""
        raise RuntimeError(f"「{script_name}」执行失败 (exit={proc.returncode})\n{err}\n{out}")

    return stdout.decode(), stderr.decode()


# ─── 流水线步骤 ───────────────────────────────────────────


async def run_pipeline(task_id: str, input_path: str, params: dict):
    """运行完整流水线"""
    td = task_dir(task_id)
    try:
        # 步骤 1: 数据加载
        cleaned_csv = await _step_loading(task_id, td, input_path)

        # 步骤 2: 数据清洗
        final_csv = await _step_cleaning(task_id, td, cleaned_csv)

        # 步骤 2.5: 方法推荐（用户未指定方法时自动推荐）
        method = params.get("method", "")
        if not method:
            method = await _step_method_recommend(task_id, td, final_csv, params)

        # 步骤 3: 统计分析
        result_json = await _step_analyzing(task_id, td, final_csv, params, method)

        # 步骤 4: 图表生成
        await _step_figures(task_id, td, final_csv, result_json)

        # 步骤 5: 报告生成
        await _step_report(task_id, td, result_json, final_csv)

        # 收尾：收集文件清单
        _collect_outputs(td, task_id)
        update_task(task_id, status="completed", progress=100, step="completed",
                    message="✅ 分析完成！")

    except Exception as e:
        update_task(task_id, status="failed", message=str(e))
        raise


async def _step_loading(task_id: str, td: Path, input_path: str) -> str:
    """dataloader → 输入文件 → _cleaned.csv（同目录）"""
    await _run_script(
        task_id, "dataloader.py", [input_path],
        "loading", 10, "正在加载数据文件…",
        cwd=str(td),
    )

    # 输出: input 同目录下的 <basename>_cleaned.csv
    cleaned_csv = _output_name(input_path, "_cleaned.csv")
    if not os.path.exists(cleaned_csv):
        # fallback: 在 task 目录里找任意 _cleaned.csv
        found = _find_in_dir(str(td), "*_cleaned.csv")
        if not found:
            raise RuntimeError("dataloader 未生成 _cleaned.csv 文件")
        cleaned_csv = found

    update_task(task_id, step_data={"cleaned_csv": cleaned_csv})
    return cleaned_csv


async def _step_cleaning(task_id: str, td: Path, cleaned_csv: str) -> str:
    """datacleaner → _cleaned.csv → _final.csv（同目录）"""
    await _run_script(
        task_id, "datacleaner.py", [cleaned_csv],
        "cleaning", 30, "正在清洗数据…",
        cwd=str(td),
    )

    final_csv = _output_name(cleaned_csv, "_final.csv")
    if not os.path.exists(final_csv):
        found = _find_in_dir(str(td), "*_final.csv")
        if not found:
            raise RuntimeError("datacleaner 未生成 _final.csv 文件")
        final_csv = found

    update_task(task_id, step_data={"final_csv": final_csv})
    return final_csv


async def _step_method_recommend(task_id: str, td: Path, final_csv: str,
                                 params: dict) -> str:
    """methodselector 自动推荐方法"""
    y = params.get("y")
    x = params.get("x", [])

    args = [final_csv]
    if y:
        args.extend(["-y", y])
    for xi in x:
        args.extend(["-x", xi])

    stdout, _ = await _run_script(
        task_id, "methodselector.py", args,
        "analyzing", 40, "正在推荐分析方法…",
        cwd=str(td),
    )

    # 从 stdout 里解析推荐的方法
    method = _extract_method(stdout)
    update_task(task_id, step_data={"recommended_method": method})
    return method


def _extract_method(text: str) -> str:
    """从 methodselector 输出中解析推荐的方法名"""
    # 常见方法关键词
    for kw in ["ttest", "mannwhitney", "anova", "kruskal",
               "regression", "logistic", "chi2", "correlation", "describe"]:
        if re.search(rf"\b{kw}\b", text, re.IGNORECASE):
            return kw
    return ""


async def _step_analyzing(task_id: str, td: Path, final_csv: str,
                          params: dict, method: str) -> str | None:
    """statisticsexecutor → 统计结果 _result.json + _summary.md"""
    y = params.get("y")
    x = params.get("x", [])

    args = [final_csv]
    if method:
        args.extend(["-m", method])
    if y:
        args.extend(["-y", y])
    for xi in x:
        args.extend(["-x", xi])

    await _run_script(
        task_id, "statisticsexecutor.py", args,
        "analyzing", 55, "正在执行统计分析…",
        cwd=str(td),
    )

    # 输出: 同目录下的 <basename>_result.json
    result_json = _output_name(final_csv, "_result.json")
    if not os.path.exists(result_json):
        found = _find_in_dir(str(td), "*_result.json")
        if found:
            result_json = found
        else:
            update_task(task_id, message="统计分析完成，但未生成结果 JSON")
            return None

    update_task(task_id, step_data={"result_json": result_json})
    return result_json


async def _step_figures(task_id: str, td: Path, final_csv: str | None,
                        results_json: str | None):
    """figuregenerator → 交互式图表（硬编码到 skill/figures/，需拷贝回）"""
    if not results_json or not os.path.exists(results_json):
        update_task(task_id, message="跳过图表生成（无结果数据）")
        return

    await _run_script(
        task_id, "figuregenerator.py",
        [final_csv or "", results_json, "-t", "all", "--clean"],
        "figures", 70, "正在生成图表…",
        cwd=str(td),
    )

    # *** 拷贝回 task 目录 ***
    skill_fig_dir = Path(SKILL_DIR).parent / "figures"
    task_fig_dir = td / "figures"
    task_fig_dir.mkdir(parents=True, exist_ok=True)

    if skill_fig_dir.exists():
        count = 0
        for f in skill_fig_dir.iterdir():
            if f.is_file():
                dest = task_fig_dir / f.name
                shutil.copy2(str(f), str(dest))
                # 清理源文件
                f.unlink()
                count += 1
        update_task(task_id, message=f"图表生成完成（{count} 个）")


async def _step_report(task_id: str, td: Path, results_json: str | None,
                       final_csv: str | None):
    """reportgenerator → MD 报告（硬编码到 skill/reports/，需拷贝回）"""
    if not results_json or not os.path.exists(results_json):
        update_task(task_id, message="跳过报告生成（无结果数据）")
        return

    args = [results_json]
    if final_csv:
        args.extend(["--data", final_csv])

    await _run_script(
        task_id, "reportgenerator.py", args,
        "report", 90, "正在生成分析报告…",
        cwd=str(td),
    )

    # *** 拷贝回 task 目录 ***
    skill_reports_dir = Path(SKILL_DIR).parent / "reports"
    task_reports_dir = td / "reports"
    task_reports_dir.mkdir(parents=True, exist_ok=True)

    if skill_reports_dir.exists():
        count = 0
        for f in skill_reports_dir.iterdir():
            if f.is_file():
                dest = task_reports_dir / f.name
                shutil.copy2(str(f), str(dest))
                f.unlink()
                count += 1
        update_task(task_id, message=f"报告生成完成（{count} 个）")
