#!/usr/bin/env python3
"""
reportgenerator.py — 科研数据分析报告生成器 (学术风格)

从 statisticsexecutor.py 输出的 results.json（支持多个）和 figuregenerator.py
生成的图表文件，输出一份完整的 Markdown 分析报告，包含：
  - 人话解释（p 值意义、效应量评价、模型拟合评估）
  - 嵌入的 PNG 静态截图 + 交互式 HTML 链接
  - 结构化 HTML 注释元数据（便于后处理）

用法:
  # 单个结果
  python3 scripts/reportgenerator.py results.json --data data_final.csv -o report

  # 多个结果合并为一个报告
  python3 scripts/reportgenerator.py results1.json results2.json --data data_final.csv -o report

  # 指定图表前缀（自动发现 PNG + HTML）
  python3 scripts/reportgenerator.py results.json --data data_final.csv --figure-prefix data_final_figure -o report

  # 手动指定图表
  python3 scripts/reportgenerator.py results.json --data data_final.csv --figures "fig/result_box.png" "fig/result_box.html" -o report
"""

import os
import sys
import re
import json
import argparse
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

import numpy as np


# ===================================================================
# 路径配置
# ===================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent
FIGURES_DIR = SKILL_DIR / "figures"
REPORTS_DIR = SKILL_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ===================================================================
# 加载数据
# ===================================================================

def load_results(json_paths: List[str]) -> List[dict]:
    """读取一个或多个 results.json."""
    results_list = []
    for path in json_paths:
        if not os.path.exists(path):
            print(f"  ⚠️ 未找到: {path}")
            continue
        with open(path, "r", encoding="utf-8") as f:
            results_list.append(json.load(f))
        print(f"  📄 已加载: {path}")
    if not results_list:
        print("❌ 没有可用的 results.json")
        sys.exit(1)
    return results_list


def load_data(csv_path: Optional[str]) -> Optional[dict]:
    """读取 CSV 头部信息用于数据概览，不加载全部数据."""
    if not csv_path or not os.path.exists(csv_path):
        return None
    import pandas as pd
    df = pd.read_csv(csv_path, encoding="utf-8")
    info = {
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "columns": list(df.columns),
        "numeric_cols": df.select_dtypes(include=[np.number]).columns.tolist(),
        "cat_cols": df.select_dtypes(include=["object", "category"]).columns.tolist(),
        "missing_total": int(df.isna().sum().sum()),
    }
    return info


# ===================================================================
# 图表发现
# ===================================================================

def discover_figures(figure_prefixes: Optional[List[str]] = None,
                     figure_paths: Optional[List[str]] = None) -> dict:
    """
    发现图表文件，返回 {chart_type: [{"png": path, "html": path}, ...]}.
    支持两种方式：
      1. --figure-prefix: 自动在 figures/ 下扫描匹配前缀的文件
      2. --figures: 手动指定文件列表
    """
    from figuregenerator import TYPES_AVAILABLE

    figures = {}

    if figure_paths:
        for fp in figure_paths:
            p = Path(fp)
            if not p.exists():
                continue
            base = p.stem
            matched = None
            for ct in sorted(TYPES_AVAILABLE, key=len, reverse=True):
                if base.endswith(f"_{ct}"):
                    matched = ct
                    break
            chart_type = matched or "figure"
            if chart_type not in figures:
                figures[chart_type] = []
            # 尝试合并到已有 item
            merged = False
            for item in figures[chart_type]:
                if chart_type == matched and len(item) == 1:
                    if p.suffix == ".png" and "png" not in item:
                        item["png"] = str(p.resolve())
                        merged = True
                        break
                    elif p.suffix == ".html" and "html" not in item:
                        item["html"] = str(p.resolve())
                        merged = True
                        break
            if not merged:
                figures[chart_type].append({p.suffix.lstrip("."): str(p.resolve())})

    if figure_prefixes and FIGURES_DIR.exists():
        for prefix in figure_prefixes:
            if not prefix:
                continue
            for ct in TYPES_AVAILABLE:
                png_file = FIGURES_DIR / f"{prefix}_{ct}.png"
                html_file = FIGURES_DIR / f"{prefix}_{ct}.html"
                if not png_file.exists() and not html_file.exists():
                    continue
                item = {}
                if png_file.exists():
                    item["png"] = str(png_file.resolve())
                if html_file.exists():
                    item["html"] = str(html_file.resolve())
                if ct not in figures:
                    figures[ct] = []
                figures[ct].append(item)

    return figures

def _source_label(path_str: str) -> str:
    """从文件路径推断来源标签."""
    name = Path(path_str).stem
    if name.startswith("train_"):
        return "训练集"
    elif name.startswith("test_"):
        return "测试集"
    return ""


# ===================================================================
# 解释引擎
# ===================================================================

def describe_p(p_val) -> str:
    """p 值的学术化文字解释."""
    if p_val is None:
        return ""
    if p_val < 0.001:
        return "p < 0.001，具有高度统计学显著性"
    if p_val < 0.01:
        return f"p = {p_val:.4f} < 0.01，具有较强统计学显著性"
    if p_val < 0.05:
        return f"p = {p_val:.4f} < 0.05，具有统计学显著性"
    return f"p = {p_val:.4f} ≥ 0.05，未达到统计学显著水平"


def describe_effect_size(effect: dict) -> str:
    """效应量的学术化解释."""
    if not effect:
        return ""
    interp = effect.get("interpretation", "")
    texts = []

    # Cohen's d
    d = effect.get("cohens_d")
    if d is not None:
        ad = abs(d)
        if ad < 0.2:
            strength = "极小"
        elif ad < 0.5:
            strength = "较小"
        elif ad < 0.8:
            strength = "中等"
        else:
            strength = "较大"
        texts.append(f"Cohen's d = {d:.3f}，效应量{strength}")

    # R²
    r2 = effect.get("R_squared")
    if r2 is not None:
        if r2 >= 0.5:
            texts.append(f"R² = {r2:.4f}，模型解释了 {r2*100:.1f}% 的方差，拟合效果较好")
        elif r2 >= 0.25:
            texts.append(f"R² = {r2:.4f}，模型解释了 {r2*100:.1f}% 的方差，拟合效果中等")
        elif r2 >= 0.1:
            texts.append(f"R² = {r2:.4f}，模型解释了 {r2*100:.1f}% 的方差，拟合效果较弱")
        else:
            texts.append(f"R² = {r2:.4f}，模型解释力较低")

    # AUC
    auc = effect.get("auc_roc")
    if auc is not None:
        if auc >= 0.9:
            texts.append(f"AUC = {auc:.3f}，模型区分能力优秀")
        elif auc >= 0.8:
            texts.append(f"AUC = {auc:.3f}，模型区分能力良好")
        elif auc >= 0.7:
            texts.append(f"AUC = {auc:.3f}，模型区分能力可接受")
        else:
            texts.append(f"AUC = {auc:.3f}，模型区分能力较差")

    # η²
    eta2 = effect.get("eta_squared")
    if eta2 is not None:
        if eta2 >= 0.14:
            texts.append(f"η² = {eta2:.4f}，效应量大")
        elif eta2 >= 0.06:
            texts.append(f"η² = {eta2:.4f}，效应量中等")
        else:
            texts.append(f"η² = {eta2:.4f}，效应量较小")

    # Cramér's V
    v = effect.get("cramers_v")
    if v is not None:
        if v >= 0.5:
            texts.append(f"Cramér's V = {v:.4f}，关联度高")
        elif v >= 0.3:
            texts.append(f"Cramér's V = {v:.4f}，关联度中等")
        else:
            texts.append(f"Cramér's V = {v:.4f}，关联度较低")

    # 秩双列 r
    r = effect.get("rank_biserial_r")
    if r is not None:
        ar = abs(r)
        if ar >= 0.5:
            texts.append(f"秩双列 r = {r:.4f}，效应量较大")
        elif ar >= 0.3:
            texts.append(f"秩双列 r = {r:.4f}，效应量中等")
        else:
            texts.append(f"秩双列 r = {r:.4f}，效应量较小")

    # adj R²
    adj_r2 = effect.get("adjusted_R_squared")
    if adj_r2 is not None and r2 is None:
        if adj_r2 >= 0.5:
            texts.append(f"调整 R² = {adj_r2:.4f}，模型拟合效果较好")
        elif adj_r2 >= 0.25:
            texts.append(f"调整 R² = {adj_r2:.4f}，模型拟合效果中等")
        else:
            texts.append(f"调整 R² = {adj_r2:.4f}，模型拟合效果较弱")

    if interp and not texts:
        texts.append(f"效应强度: {interp}")

    return "；".join(texts)


def generate_interpretation(result: dict) -> str:
    """根据统计方法和结果生成完整的段落解释."""
    method = result.get("method", "")
    y_col = result.get("y_col", "")
    x_vars = result.get("x_vars", [])
    p_val = result.get("p_value")
    effect = result.get("effect_size", {})
    stat = result.get("statistics", {})
    group_stats = result.get("group_stats", [])
    assumptions = result.get("assumptions", [])

    paragraphs = []

    method_norm = method.lower().replace(" ", "")

    # --- t 检验 ---
    if "t检验" in method_norm:
        t_val = stat.get("t_statistic", "?")
        x_name = x_vars[0] if x_vars else "分组"
        p_desc = describe_p(p_val)
        ef_desc = describe_effect_size(effect)

        # 均值对比
        means = []
        for gs in group_stats:
            if "mean" in gs and "std" in gs:
                means.append(f"{gs['group']} (M={gs['mean']:.2f}, SD={gs['std']:.2f}, n={gs['n']})")

        para = f"采用独立样本 t 检验分析 {x_name} 对 {y_col} 的影响。"
        if means:
            para += f"描述统计结果显示：{'，'.join(means)}。"
        para += f"检验结果显示 t = {t_val}，{p_desc}。"
        para += f"{ef_desc}。"

        # 假设前提
        asmp_texts = []
        for a in assumptions:
            icon = "满足" if a.get("passed") else "不满足"
            asmp_texts.append(f"{a['name']}: {icon}")
        if asmp_texts:
            para += f" 前提假设检验：{'；'.join(asmp_texts)}。"

        paragraphs.append(para)

    # --- Mann-Whitney ---
    elif "mann-whitney" in method_norm:
        u_val = stat.get("U_statistic", "?")
        x_name = x_vars[0] if x_vars else "分组"
        p_desc = describe_p(p_val)
        ef_desc = describe_effect_size(effect)

        para = f"采用 Mann-Whitney U 检验分析 {x_name} 对 {y_col} 的影响。"
        paras_med = []
        for gs in group_stats:
            if "median" in gs:
                paras_med.append(f"{gs['group']} 中位数={gs['median']:.2f}")
        if paras_med:
            para += f"{'，'.join(paras_med)}。"
        para += f"U = {u_val}，{p_desc}。{ef_desc}。"
        paragraphs.append(para)

    # --- ANOVA ---
    elif "anova" in method_norm or "welch" in method_norm:
        f_val = stat.get("F_statistic", "?")
        x_name = x_vars[0] if x_vars else "分组"
        p_desc = describe_p(p_val)
        ef_desc = describe_effect_size(effect)

        para = f"采用{method}分析 {x_name} 对 {y_col} 的影响。"
        grp_parts = []
        for gs in group_stats:
            if "mean" in gs and "std" in gs:
                grp_parts.append(f"{gs['group']} (M={gs['mean']:.2f}, SD={gs['std']:.2f}, n={gs['n']})")
        if grp_parts:
            para += f"描述统计：{'，'.join(grp_parts)}。"
        para += f"F({stat.get('df_between', '?')}, {stat.get('df_within', '?')}) = {f_val}，{p_desc}。{ef_desc}。"
        paragraphs.append(para)

    # --- Kruskal-Wallis ---
    elif "kruskal" in method_norm:
        h_val = stat.get("H_statistic", "?")
        x_name = x_vars[0] if x_vars else "分组"
        p_desc = describe_p(p_val)
        ef_desc = describe_effect_size(effect)

        para = f"采用 Kruskal-Wallis 检验分析 {x_name} 对 {y_col} 的影响。"
        grp_med = []
        for gs in group_stats:
            if "median" in gs:
                grp_med.append(f"{gs['group']} 中位数={gs['median']:.2f}")
        if grp_med:
            para += f"{'，'.join(grp_med)}。"
        para += f"H = {h_val}，{p_desc}。{ef_desc}。"
        paragraphs.append(para)

    # --- 线性回归 ---
    elif "线性回归" in method_norm or "regression" in method_norm:
        r2 = stat.get("R_squared", "?")
        adj_r2 = stat.get("adjusted_R_squared", "")
        f_val = stat.get("F_statistic", "?")
        f_p = stat.get("F_p_value")
        p_desc = describe_p(f_p or p_val)
        ef_desc = describe_effect_size(effect)

        para = f"采用线性回归模型分析 {'、'.join(x_vars)} 对 {y_col} 的预测作用。"
        para += f"模型整体 F({stat.get('df_model', '?')}, {stat.get('df_residual', '?')}) = {f_val}，{p_desc}。"
        para += f"{ef_desc}。"

        if adj_r2:
            para += f" 调整后 R² = {adj_r2:.4f}，对模型复杂度进行了校正。"

        # 系数表
        coefs = stat.get("coefficients", [])
        if coefs:
            coef_parts = []
            for c in coefs:
                coef_parts.append(f"{c['feature']} 系数={c['coef']}")
            para += f" 回归系数：{'；'.join(coef_parts)}。"

        paragraphs.append(para)

    # --- 逻辑回归 ---
    elif "逻辑回归" in method_norm or "logistic" in method_norm:
        acc = stat.get("accuracy")
        auc_val = stat.get("auc_roc")
        ef_desc = describe_effect_size(effect)

        para = f"采用逻辑回归模型预测 {y_col}。"
        if acc is not None:
            para += f"模型在测试集上的准确率为 {acc:.3f}。"
        if auc_val is not None:
            para += f"AUC-ROC = {auc_val:.3f}。"
        para += f"{ef_desc}。"

        # 系数
        coefs = stat.get("coefficients", [])
        if coefs:
            coef_parts = []
            for c in coefs:
                or_val = c.get("odds_ratio", "")
                if or_val:
                    coef_parts.append(f"{c['feature']} (OR={or_val}")
                else:
                    coef_parts.append(f"{c['feature']} (系数={c['coef']}")
            para += f" 模型系数：{'；'.join(coef_parts)}。"

        paragraphs.append(para)

    # --- 卡方检验 ---
    elif "卡方" in method_norm or "chi" in method_norm:
        chi2 = stat.get("chi_squared", "?")
        dof = stat.get("degrees_of_freedom", "?")
        x_name = x_vars[0] if x_vars else "变量"
        p_desc = describe_p(p_val)
        ef_desc = describe_effect_size(effect)

        para = f"采用卡方独立性检验分析 {x_name} 与 {y_col} 之间的关联性。"
        para += f"χ²({dof}) = {chi2}，{p_desc}。{ef_desc}。"

        # 列联表片段
        if group_stats:
            para += f" 列联表共包含 {len(group_stats)} 个单元格。"

        paragraphs.append(para)

    # --- 相关性 ---
    elif "相关" in method_norm or "correlation" in method_norm:
        pairs = stat.get("pairs", [])
        if pairs:
            top = pairs[0]
            r_val = top.get("pearson_r", 0)
            p_pair = top.get("p_value", 1)
            p_desc = describe_p(p_pair)
            ar = abs(r_val)
            if ar >= 0.7:
                strength = "强相关"
            elif ar >= 0.4:
                strength = "中等相关"
            else:
                strength = "弱相关"

            para = f"Pearson 相关分析显示，{top['var1']} 与 {top['var2']} 之间存在{strength}"
            para += f" (r = {r_val:.4f}, n = {top.get('n', '?')}，{p_desc})。"

            if len(pairs) > 1:
                para += f" 其他显著相关共有 {sum(1 for p in pairs if p.get('p_value', 1) < 0.05)} 对。"

            paragraphs.append(para)

    # --- 描述统计 ---
    elif "描述统计" in method_norm or "describe" in method_norm:
        numeric_cols = [k for k, v in stat.items()
                        if isinstance(v, dict) and "mean" in v]
        cat_cols = [k for k, v in stat.items()
                    if isinstance(v, dict) and "frequencies" in v]

        para = f"描述统计分析报告。"
        n_num = len(numeric_cols)
        n_cat = len(cat_cols)
        para += f"数据包含 {n_num} 个数值变量和 {n_cat} 个分类变量。"

        if group_stats:
            para += " 详细统计量见附录。"

        paragraphs.append(para)

    # --- 综合 ---
    if not paragraphs:
        # 兜底：通用描述
        parts = []
        p_desc = describe_p(p_val)
        if p_desc:
            parts.append(p_desc)
        ef_desc = describe_effect_size(effect)
        if ef_desc:
            parts.append(ef_desc)
        if parts:
            paragraphs.append(f"采用 {method} 进行分析。{'；'.join(parts)}。")
        else:
            paragraphs.append(f"采用 {method} 进行分析。具体统计量见附录。")

    return "\n\n".join(paragraphs)


def generate_summary(results_list: List[dict]) -> str:
    """生成整篇报告的摘要（一句话核心结论）。"""
    summaries = []
    for r in results_list:
        interp = r.get("interpretation", "")
        p_val = r.get("p_value")
        if interp:
            sig = ""
            if p_val is not None:
                if p_val < 0.001:
                    sig = "（高度显著）"
                elif p_val < 0.05:
                    sig = "（显著）"
                else:
                    sig = "（不显著）"
            interp_clean = interp.strip().rstrip("（显著）（不显著）")
            summaries.append(f"{r.get('method', '分析')}：{interp_clean}{sig}")
        else:
            p_desc = describe_p(p_val)
            if p_desc:
                summaries.append(f"{r.get('method', '分析')}：{p_desc}")
    return "；".join(summaries) if summaries else "完成数据分析报告。"


# ===================================================================
# 元数据生成
# ===================================================================

def make_meta_block(results_list: List[dict], data_info: Optional[dict]) -> str:
    """生成结构化 HTML 注释元数据块."""
    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tool": "reportgenerator.py",
        "skill": "research-analysis",
        "n_analyses": len(results_list),
        "methods": [r.get("method", "") for r in results_list],
    }
    if data_info:
        meta["data"] = {
            "n_rows": data_info["n_rows"],
            "n_cols": data_info["n_cols"],
            "numeric_vars": len(data_info["numeric_cols"]),
            "categorical_vars": len(data_info["cat_cols"]),
            "missing_total": data_info["missing_total"],
        }
    for i, r in enumerate(results_list):
        meta[f"analysis_{i}"] = {
            "method": r.get("method", ""),
            "y": r.get("y_col", ""),
            "x": r.get("x_vars", []),
            "p_value": r.get("p_value"),
            "sample_size": r.get("sample_size", {}),
        }
    return f"<!-- meta: {json.dumps(meta, ensure_ascii=False, indent=2)} -->"


# ===================================================================
# 辅助：从 results 提取样本量等信息
# ===================================================================

def _total_sample(results_list: List[dict]) -> int:
    for r in results_list:
        ss = r.get("sample_size", {})
        v = ss.get("total") or ss.get("valid")
        if v:
            return v
    return 0


def _method_desc(method: str) -> str:
    """统计方法的中文长描述."""
    m = method.lower()
    if "t检验" in m:
        return "独立样本 t 检验，用于比较两组间连续变量的均值差异"
    if "mann-whitney" in m:
        return "Mann-Whitney U 检验，用于比较两组间连续变量的中位数差异（非参数）"
    if "anova" in m or "welch" in m:
        return "单因素方差分析 (ANOVA)，用于比较多组间连续变量的均值差异"
    if "kruskal" in m:
        return "Kruskal-Wallis 检验，用于比较多组间连续变量的中位数差异（非参数）"
    if "线性回归" in m or "regression" in m:
        return "线性回归，用于分析自变量对连续因变量的线性预测作用"
    if "逻辑回归" in m or "logistic" in m:
        return "逻辑回归，用于分析自变量对二分类因变量的预测作用"
    if "卡方" in m or "chi" in m:
        return "卡方独立性检验，用于分析两个分类变量之间的关联性"
    if "相关" in m or "correlation" in m:
        return "Pearson 相关分析，用于评估连续变量之间的线性相关程度"
    if "描述统计" in m or "describe" in m:
        return "描述统计分析，提供数据的基本统计特征"
    return method


def _figure_title(chart_type: str) -> str:
    """图表类型对应的学术标题."""
    titles = {
        "scatter_reg": "散点图与回归线",
        "box": "分组箱线图",
        "violin": "小提琴图",
        "bar_grouped": "分组柱状图",
        "residual": "残差诊断图",
        "qq": "Q-Q 图（残差正态性检验）",
        "heatmap": "相关性热力图",
        "roc": "ROC 曲线",
        "histogram": "变量分布直方图",
        "pie": "分类变量饼图",
    }
    return titles.get(chart_type, chart_type)


def _figure_caption(chart_type: str, result: dict) -> str:
    """图的学术说明文字."""
    method = result.get("method", "")
    y_col = result.get("y_col", "")
    x_vars = result.get("x_vars", [])

    captions = {
        "scatter_reg": f"图：{y_col} 与 {', '.join(x_vars)} 的散点图与线性回归拟合线（含 95% 置信区间）",
        "box": f"图：{' vs '.join(x_vars)} 在 {y_col} 上的分组箱线图（含数据点）",
        "violin": f"图：{' vs '.join(x_vars)} 在 {y_col} 上的小提琴图",
        "bar_grouped": f"图：{' vs '.join(x_vars)} 在 {y_col} 上的分组柱状图",
        "residual": "图：回归模型的残差诊断图（残差 vs 拟合值及残差分布）",
        "qq": "图：回归残差的 Q-Q 图（正态性检验）",
        "heatmap": "图：变量间 Pearson 相关系数热力图",
        "roc": "图：逻辑回归模型的 ROC 曲线",
        "histogram": "图：各数值变量的分布直方图（含核密度估计曲线）",
        "pie": "图：分类变量分布饼图",
    }
    return captions.get(chart_type, f"图：{_figure_title(chart_type)}")


# ===================================================================
# 报告生成
# ===================================================================

def build_report(results_list: List[dict],
                 data_info: Optional[dict],
                 figures: dict) -> str:
    """构建完整的 Markdown 报告."""
    lines = []

    # ==== 标题 ====
    methods_str = " + ".join(r.get("method", "") for r in results_list)
    lines.append("# 数据分析报告")
    lines.append("")
    lines.append("> 生成时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("")
    lines.append("---")
    lines.append("")

    # ==== 结构化元数据 ====
    meta_block = make_meta_block(results_list, data_info)
    lines.append(meta_block)
    lines.append("")

    # ==== 摘要 ====
    lines.append("## 摘要")
    lines.append("")
    summary_text = generate_summary(results_list)
    lines.append(summary_text)
    lines.append("")
    lines.append("---")
    lines.append("")

    # ==== 1. 数据与方法 ====
    lines.append("## 1. 数据与方法")
    lines.append("")

    if data_info:
        lines.append(f"### 1.1 数据概览")
        lines.append("")
        lines.append(f"- **样本量**：{data_info['n_rows']} 条观测")
        lines.append(f"- **变量数**：{data_info['n_cols']} 个变量 "
                      f"（{len(data_info['numeric_cols'])} 个数值型，"
                      f"{len(data_info['cat_cols'])} 个分类型）")
        lines.append(f"- **缺失值**：共 {data_info['missing_total']} 个")
        lines.append("")

    lines.append(f"### 1.2 分析方法")
    lines.append("")
    for i, r in enumerate(results_list):
        method = r.get("method", "")
        y_col = r.get("y_col", "")
        x_vars = r.get("x_vars", [])
        lines.append(f"**分析 {i+1}：{method}**")
        lines.append("")
        lines.append(f"- 方法说明：{_method_desc(method)}")
        if y_col:
            lines.append(f"- **目标变量 (Y)**：{y_col}")
        if x_vars:
            lines.append(f"- **自变量 (X)**：{'、'.join(x_vars)}")
        ss = r.get("sample_size", {})
        total = ss.get("total", "")
        valid = ss.get("valid", "")
        lines.append(f"- **样本量**：{valid}/{total} 有效")
        lines.append("")

        # 假设前提
        assumptions = r.get("assumptions", [])
        if assumptions:
            lines.append(f"**前提假设检验：**")
            lines.append("")
            for a in assumptions:
                icon = "✅" if a.get("passed") else "⚠️"
                lines.append(f"- {icon} **{a['name']}**：p = {a.get('p_value', 0):.4f} — {a.get('note', '')}")
            lines.append("")

    lines.append("---")
    lines.append("")

    # ==== 2. 统计结果 ====
    lines.append("## 2. 统计结果")
    lines.append("")

    for i, r in enumerate(results_list):
        method = r.get("method", "")
        y_col = r.get("y_col", "")
        x_vars = r.get("x_vars", [])

        lines.append(f"### 2.{i+1} {method}")
        lines.append("")

        # 解释段落
        interp = generate_interpretation(r)
        lines.append(interp)
        lines.append("")

        # 统计数值明细
        lines.append("**检验统计量：**")
        lines.append("")
        stat = r.get("statistics", {})
        for k, v in stat.items():
            if k in ("coefficients", "pairs", "matrix", "df_model", "df_residual"):
                continue
            if isinstance(v, float):
                lines.append(f"- **{k}**：{v:.4f}")
            elif isinstance(v, int):
                lines.append(f"- **{k}**：{v}")
        if r.get("p_value") is not None:
            lines.append(f"- **p 值**：{r['p_value']:.6f}")
        lines.append("")

        # 效应量
        effect = r.get("effect_size", {})
        if effect and any(v for k, v in effect.items() if k != "interpretation" and v is not None):
            lines.append("**效应量：**")
            lines.append("")
            for k, v in effect.items():
                if k == "interpretation":
                    continue
                if isinstance(v, float):
                    lines.append(f"- **{k}**：{v:.4f}")
                elif isinstance(v, (int,)):
                    lines.append(f"- **{k}**：{v}")
            if effect.get("interpretation"):
                lines.append(f"- **强度评价**：{effect['interpretation']}")
            lines.append("")

        # 分组统计
        group_stats = r.get("group_stats", [])
        if group_stats:
            lines.append("**分组统计：**")
            lines.append("")
            # 表头
            headers = list(group_stats[0].keys())
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for gs in group_stats:
                row = []
                for h in headers:
                    v = gs.get(h, "")
                    if isinstance(v, float):
                        row.append(f"{v:.3f}")
                    else:
                        row.append(str(v))
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")

        # 嵌入图表 - 根据当前分析的变量名匹配对应图表
        is_train = any("Train" in v or "train" in v for v in x_vars)
        is_test = any("Test" in v or "test" in v for v in x_vars)
        chart_types = ["scatter_reg", "box", "violin", "bar_grouped",
                       "residual", "qq", "heatmap", "roc", "histogram", "pie"]
        for ct in chart_types:
            if ct in figures:
                for idx, fig_info in enumerate(figures[ct]):
                    png_path = fig_info.get("png")
                    html_path = fig_info.get("html")
                    source = _source_label(png_path or html_path or "")

                    # 只嵌入匹配当前分析的图表
                    if source == "训练集" and not is_train:
                        continue
                    if source == "测试集" and not is_test:
                        continue
                    if not source and idx > 0:
                        continue

                    label = _figure_title(ct)
                    if source:
                        label += f" ({source})"

                    lines.append(f"**{label}**")
                    lines.append("")
                    lines.append(f"*{_figure_caption(ct, r)}*")
                    lines.append("")

                    if png_path:
                        rel_png = os.path.relpath(png_path, str(REPORTS_DIR))
                        lines.append(f"![{_figure_title(ct)}]({rel_png})")
                        lines.append("")

                    if html_path:
                        rel_html = os.path.relpath(html_path, str(REPORTS_DIR))
                        lines.append(f"> 🔗 [查看交互式图表]({rel_html})（可悬停查看数值、滚轮缩放）")
                        lines.append("")

        lines.append("---")
        lines.append("")

    # ==== 3. 讨论 ====
    lines.append("## 3. 讨论")
    lines.append("")

    # 综合讨论
    for i, r in enumerate(results_list):
        method = r.get("method", "")
        y_col = r.get("y_col", "")
        p_val = r.get("p_value")
        effect = r.get("effect_size", {})
        ss = r.get("sample_size", {})
        total = ss.get("total") or ss.get("valid", 0)

        parts = []

        # 显著性讨论
        if p_val is not None:
            if p_val < 0.05:
                parts.append(f"分析 {i+1}（{method}）的结果具有统计学显著性，"
                              f"表明 {y_col} 在不同条件下存在可检测的差异或关系。")
            else:
                parts.append(f"分析 {i+1}（{method}）未达到统计学显著水平，"
                              f"当前数据不支持 {y_col} 在不同条件下存在差异的假设。")

        # 效应量讨论
        ef_desc = describe_effect_size(effect)
        if ef_desc:
            parts.append(f"效应量分析表明{ef_desc}。")

        # 样本量讨论
        if total > 0:
            if total < 30:
                parts.append(f"样本量相对较小 (n={total})，建议在更大样本中验证本结论的稳健性。")
            elif total < 100:
                parts.append(f"样本量适中 (n={total})，结论具有初步参考价值。")
            else:
                parts.append(f"样本量较充足 (n={total})，结论具有较好的统计效力。")

        if parts:
            lines.append(f"### 3.{i+1} 对分析 {i+1} 的讨论")
            lines.append("")
            for p in parts:
                lines.append(p)
                lines.append("")

    # 局限性
    lines.append("### 局限性")
    lines.append("")
    lines.append("本报告的分析结果受限于以下因素：")
    lines.append("")
    lines.append("- 数据质量：分析结果依赖于原始数据的准确性和完整性。")
    lines.append("- 样本代表性：样本需能够代表其所属总体。")
    lines.append("- 模型假设：统计方法的结论有效性取决于其前提假设的满足程度。")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ==== 4. 结论 ====
    lines.append("## 4. 结论")
    lines.append("")
    lines.append(summary_text)
    lines.append("")
    lines.append("---")
    lines.append("")

    # ==== 附录 ====
    lines.append("## 附录：统计数值明细")
    lines.append("")
    lines.append("> 以下为各分析的完整统计量数值，供查验与复现。")
    lines.append("")

    for i, r in enumerate(results_list):
        lines.append(f"### A.{i+1} {r.get('method', '')}")
        lines.append("")
        lines.append("```json")
        serializable = {}
        for k, v in r.items():
            if k in ("group_stats", "assumptions"):
                continue
            serializable[k] = v
        lines.append(json.dumps(serializable, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


# ===================================================================
# 保存
# ===================================================================

def save_report(markdown: str, output_prefix: str) -> Path:
    """保存报告为 .md 文件."""
    output_path = REPORTS_DIR / f"{output_prefix}.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"  ✅ 报告已保存: {output_path}")
    return output_path


# ===================================================================
# CLI 入口
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="📝 ReportGenerator — 科研数据分析报告生成器（学术风格）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            使用示例:
              %(prog)s results.json --data data_final.csv -o report
              %(prog)s results1.json results2.json --data data_final.csv -o report
              %(prog)s results.json --data data_final.csv --figure-prefix exp_figure -o report
              %(prog)s results.json --figures "fig/box.png" "fig/box.html" -o report
        """))
    parser.add_argument("results_json", nargs="+",
                        help="一个或多个 results.json 文件路径")
    parser.add_argument("--data", "-d", default=None,
                        help="原始数据 CSV 文件 (用于数据概览)")
    parser.add_argument("--output", "-o", default="report",
                        help="输出文件名前缀 (默认: report)")
    parser.add_argument("--figure-prefix", "-fp", nargs="*", default=None,
                        help="图表前缀(可多个), 自动在 figures/ 下匹配对应文件")
    parser.add_argument("--figures", "-f", nargs="*", default=None,
                        help="手动指定图表文件路径")

    args = parser.parse_args()

    print("📝 ReportGenerator — 生成数据分析报告")
    print("=" * 50)

    # 加载
    print("📄 加载 results.json...")
    results_list = load_results(args.results_json)

    data_info = None
    if args.data:
        print("📊 加载数据概览...")
        data_info = load_data(args.data)
        if data_info:
            print(f"   {data_info['n_rows']} 行 × {data_info['n_cols']} 列")

    print("🖼️  发现图表文件...")
    figures = discover_figures(args.figure_prefix, args.figures)
    if figures:
        for ct, items in figures.items():
            for info in items:
                png_str = f" PNG={info.get('png', '')}" if info.get('png') else ""
                html_str = f" HTML={info.get('html', '')}" if info.get('html') else ""
                print(f"   {ct}:{png_str}{html_str}")
    else:
        print("   未发现图表文件（仅生成纯文字报告）")

    print("✍️  生成报告...")
    report = build_report(results_list, data_info, figures)

    print("💾 保存报告...")
    path = save_report(report, args.output)

    print(f"\n✅ 报告生成完成: {path}")
    print(f"📐 共 {len(report.splitlines())} 行")


if __name__ == "__main__":
    main()
