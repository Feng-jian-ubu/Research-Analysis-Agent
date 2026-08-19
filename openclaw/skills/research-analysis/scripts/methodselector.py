#!/usr/bin/env python3
"""
methodselector.py — 统计方法自动推荐器

功能:
  对 datacleaner.py 清洗后的数据进行结构化分析，自动推荐合适的统计方法。
  支持：目标变量自动猜测 + 假设前提检查 + 非参数替代方案推荐。

用法:
  python3 methodselector.py <输入CSV> [选项]

示例:
  python3 methodselector.py data_final.csv
  python3 methodselector.py data_final.csv --target score
  python3 methodselector.py data_final.csv -y score -x gender --full
"""

import sys
import os
import argparse
import textwrap
from typing import Optional

import pandas as pd
import numpy as np
from scipy import stats as sp_stats


# ---------------------------------------------------------------------------
# 类型识别 (与 dataloader/datacleaner 保持一致)
# ---------------------------------------------------------------------------

def infer_variable_type(series: pd.Series, cat_threshold: float = 0.05,
                        cat_max_unique: int = 30) -> str:
    n = len(series)
    if n == 0:
        return "categorical"
    clean = series.dropna()
    if len(clean) == 0:
        return "categorical"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_bool_dtype(series):
        return "categorical"
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        numeric_count = pd.to_numeric(clean, errors='coerce').notna().sum()
        ratio_numeric = numeric_count / len(clean)
        if ratio_numeric >= 0.9:
            numeric_series = pd.to_numeric(clean, errors='coerce')
            return _decide_numeric_or_cat(numeric_series, n, cat_threshold)
        return "categorical"
    if pd.api.types.is_numeric_dtype(series):
        return _decide_numeric_or_cat(clean, n, cat_threshold, cat_max_unique)
    return "categorical"


def _decide_numeric_or_cat(series: pd.Series, total_n: int,
                           cat_threshold: float,
                           cat_max_unique: int = 30) -> str:
    if len(series) == 0:
        return "categorical"
    n_unique = series.nunique()
    ratio_unique = n_unique / total_n
    if n_unique <= 1:
        return "categorical"
    if n_unique == 2:
        return "categorical"
    if ratio_unique <= cat_threshold:
        return "categorical"
    if n_unique > cat_max_unique:
        return "numeric"
    small_cutoff = max(3, total_n * 0.5)
    if total_n <= 50 and n_unique >= small_cutoff:
        return "numeric"
    if n_unique > 10 and ratio_unique > cat_threshold:
        return "numeric"
    return "categorical"


def build_type_map(df: pd.DataFrame) -> dict:
    return {col: infer_variable_type(df[col]) for col in df.columns}


# ---------------------------------------------------------------------------
# Y 自动猜测
# ---------------------------------------------------------------------------

_DISQUALIFIED_Y_WORDS = [
    "id", "编号", "序号", "index", "row", "行号",
    "name", "姓名", "名字", "url", "link", "路径",
]


def _guess_y(df: pd.DataFrame, type_map: dict) -> Optional[str]:
    """自动猜测目标变量. 返回列名, 或 None."""
    numeric_cols = [c for c, t in type_map.items() if t == "numeric"]
    cat_cols = [c for c, t in type_map.items() if t == "categorical"]
    dt_cols = [c for c, t in type_map.items() if t == "datetime"]

    def _score(col: str, typ: str) -> float:
        """为每个列打分, 越高越可能是 Y."""
        col_lower = col.lower().strip()
        score = 0.0

        # 排除 ID 类
        for kw in _DISQUALIFIED_Y_WORDS:
            if kw in col_lower:
                return -1.0

        # 典型 Y 名称加分
        y_indicators = ["target", "label", "result", "score", "grade", "y",
                        "outcome", "response", "dependent", "value",
                        "目标", "结果", "分数", "成绩", "标签", "因变量",
                        "类别", "class", "type", "category", "group",
                        "depvar", "dv"]
        for kw in y_indicators:
            if kw in col_lower:
                score += 2.0

        # 末尾列偏好 (数据集中 target 常在最后一列)
        cols = list(df.columns)
        idx = cols.index(col)
        if idx == len(cols) - 1:
            score += 1.5
        elif idx >= len(cols) - 3:
            score += 0.5

        # 二分类列是很好的 Y
        if typ == "categorical" and df[col].nunique() == 2:
            score += 2.0

        return score

    candidates = numeric_cols + cat_cols + dt_cols
    scored = [(c, _score(c, type_map[c])) for c in candidates]
    scored = [(c, s) for c, s in scored if s >= 0]
    if not scored:
        return None
    scored.sort(key=lambda x: -x[1])
    return scored[0][0]


# ---------------------------------------------------------------------------
# 假设前提检查
# ---------------------------------------------------------------------------

class AssumptionResult:
    """单一假设检查的结果."""

    def __init__(self, name: str, passed: bool, stat: float,
                 p_value: float, note: str, alternative: str = ""):
        self.name = name
        self.passed = passed
        self.stat = stat
        self.p_value = p_value
        self.note = note
        self.alternative = alternative

    def __str__(self):
        status = "✅" if self.passed else "⚠️"
        return f"  {status} {self.name}: p={self.p_value:.4f} — {self.note}"


def check_normality(series: pd.Series, alpha: float = 0.05) -> AssumptionResult:
    """Shapiro-Wilk 正态性检验. n<3 跳过."""
    clean = series.dropna()
    n = len(clean)
    if n < 3:
        return AssumptionResult("正态性 (Shapiro-Wilk)", False, 0, 0,
                                "样本量不足 (n<3)")
    if n > 5000:
        return AssumptionResult("正态性 (Shapiro-Wilk)", True, 0, 0.5,
                                "n>5000, SW 过于敏感, 建议看 Q-Q 图确认")
    stat, p = sp_stats.shapiro(clean)
    passed = p > alpha
    note = "正态" if passed else f"偏离正态 (n={n})"
    alt = "" if passed else "建议使用非参数方法 (Mann-Whitney / Kruskal-Wallis / Spearman)"
    return AssumptionResult("正态性 (Shapiro-Wilk)", passed, stat, p, note, alt)


def check_normality_by_group(series: pd.Series, group: pd.Series,
                              alpha: float = 0.05) -> list:
    """分组正态性检验."""
    results = []
    for g in group.dropna().unique():
        subset = series[group == g].dropna()
        if len(subset) < 3:
            results.append(AssumptionResult(f"  组 '{g}' 正态性", False,
                                            0, 0, "样本量不足 (n<3)"))
            continue
        stat, p = sp_stats.shapiro(subset)
        passed = p > alpha
        note = "正态" if passed else f"偏离正态 (n={len(subset)})"
        results.append(AssumptionResult(f"  组 '{g}' 正态性 (SW)",
                                        passed, stat, p, note))
    return results


def check_variance_homogeneity(series: pd.Series, group: pd.Series,
                                alpha: float = 0.05) -> AssumptionResult:
    """Levene 方差齐性检验."""
    clean_df = pd.DataFrame({"value": series, "group": group}).dropna()
    if len(clean_df) < 6 or clean_df["group"].nunique() < 2:
        return AssumptionResult("方差齐性 (Levene)", False, 0, 0,
                                "无法检验: 数据不足或分组不足")
    groups = [g["value"].values for _, g in clean_df.groupby("group")]
    if any(len(g) < 2 for g in groups):
        return AssumptionResult("方差齐性 (Levene)", False, 0, 0,
                                "某组样本量不足 (n<2)")
    stat, p = sp_stats.levene(*groups)
    passed = p > alpha
    note = "方差齐" if passed else "方差不齐"
    alt = "" if passed else "建议使用 Welch t-test / Welch ANOVA 替代"
    return AssumptionResult("方差齐性 (Levene)", passed, stat, p, note, alt)


def check_sample_size(n: int) -> AssumptionResult:
    if n < 10:
        return AssumptionResult("样本量", False, 0, 0,
                                f"n={n} < 10: 结果不可靠, 建议增大样本或使用 exact test")
    if n < 30:
        return AssumptionResult("样本量", False, 0, 0,
                                f"n={n} < 30: 小样本, 建议使用非参数方法或报告置信区间")
    if n < 100:
        return AssumptionResult("样本量", True, 0, 0,
                                f"n={n}: 样本量适中")
    return AssumptionResult("样本量", True, 0, 0, f"n={n}: 样本量充足")


# ---------------------------------------------------------------------------
# 方法推荐引擎
# ---------------------------------------------------------------------------

class MethodRecommendation:
    def __init__(self, method: str, description: str, x_vars: list,
                 y_col: str, assumptions: list = None,
                 alternative: str = "", python_code: str = "", notes: str = ""):
        self.method = method
        self.description = description
        self.x_vars = x_vars
        self.y_col = y_col
        self.assumptions = assumptions or []
        self.alternative = alternative
        self.python_code = python_code
        self.notes = notes

    def summary(self) -> str:
        return (f"📊 推荐方法: {self.method}\n"
                f"   Y = {self.y_col}  |  X = {', '.join(self.x_vars)}\n"
                f"   {self.description}")


def recommend_methods(df: pd.DataFrame, type_map: dict,
                      y_col: Optional[str] = None,
                      x_cols: Optional[list] = None,
                      do_full_check: bool = False) -> list:
    """
    返回 MethodRecommendation 列表 (主推荐 + 替代方案).
    """
    n_total = len(df)

    # ── 确定 Y ──
    if y_col and y_col not in df.columns:
        print(f"⚠️ 指定的 Y '{y_col}' 不存在, 使用自动猜测")
        y_col = _guess_y(df, type_map)
    if not y_col:
        y_col = _guess_y(df, type_map)

    if not y_col:
        return [MethodRecommendation(
            "❌ 无法确定", "无法自动猜测目标变量, 请手动指定 --target",
            [], "", notes="尝试: python3 methodselector.py data.csv --target <列名>"
        )]

    y_type = type_map[y_col]

    # ── 确定 X ──
    if x_cols:
        x_cols = [c for c in x_cols if c in df.columns and c != y_col]
    else:
        # 自动: 除 Y 外所有列
        x_cols = [c for c in df.columns if c != y_col]

    if not x_cols:
        return [MethodRecommendation(
            "❌ 无自变量", f"Y='{y_col}' 已确定, 但数据中没有其他列可作为自变量",
            [], y_col, notes="请提供包含自变量的数据"
        )]

    # 分类 X / 数值 X
    cat_x = [c for c in x_cols if type_map[c] == "categorical"]
    num_x = [c for c in x_cols if type_map[c] == "numeric"]
    n_cat_x = len(cat_x)
    n_num_x = len(num_x)

    recommendations = []

    # ── 按 Y 类型分支 ──
    if y_type == "numeric":
        recs = _recommend_numeric_y(df, type_map, y_col, cat_x, num_x,
                                     n_total, do_full_check)
        recommendations.extend(recs)
    elif y_type == "categorical":
        recs = _recommend_categorical_y(df, type_map, y_col, cat_x, num_x,
                                         n_total, do_full_check)
        recommendations.extend(recs)
    else:
        recommendations.append(MethodRecommendation(
            "❌ 不支持的 Y 类型", f"目标变量 '{y_col}' 类型为 {y_type}",
            [], y_col
        ))

    # ── 如果没有推荐, 给兜底方案 ──
    if not recommendations:
        all_numeric = all(t == "numeric" for t in type_map.values())
        all_cat = all(t == "categorical" for t in type_map.values())

        if all_numeric:
            recommendations.append(MethodRecommendation(
                "相关性矩阵 + PCA", "全部为数值变量, 适合探索性分析",
                x_cols, y_col,
                python_code="df.corr()\nfrom sklearn.decomposition import PCA",
                alternative="t-SNE / UMAP (高维数据)"
            ))
        elif all_cat:
            recommendations.append(MethodRecommendation(
                "卡方检验 + 对应分析", "全部为分类变量, 适合列联表分析",
                x_cols, y_col,
                python_code="pd.crosstab(df['X'], df['Y'])\nfrom scipy.stats import chi2_contingency\nchi2, p, dof, expected = chi2_contingency(ct)",
                alternative="Cramér's V (关联强度)"
            ))
        else:
            recommendations.append(MethodRecommendation(
                "探索性分析", "混合类型数据, 建议先做描述统计和可视化",
                x_cols, y_col,
                alternative="随机森林特征重要性 / 关联规则"
            ))

    return recommendations


# ---------------------------------------------------------------------------
# Y = 数值型 的分支
# ---------------------------------------------------------------------------

def _recommend_numeric_y(df, type_map, y_col, cat_x, num_x,
                          n_total, do_full_check):
    recs = []
    n_cat_x = len(cat_x)
    n_num_x = len(num_x)

    # ─ 1 个二分类 X → t 检验 ─
    if n_cat_x == 1 and n_num_x == 0:
        g = cat_x[0]
        groups = df[g].dropna().unique()
        n_grp = len(groups)

        if n_grp == 2:
            assumptions = []
            alt_notes = ""

            if do_full_check:
                norm_results = check_normality_by_group(df[y_col], df[g])
                assumptions.extend(norm_results)
                var_result = check_variance_homogeneity(df[y_col], df[g])
                assumptions.append(var_result)
                assumptions.append(check_sample_size(n_total))
                any_failed = any(not r.passed for r in assumptions)
                if any_failed:
                    alt_notes = "假设未满足, 建议使用 Mann-Whitney U 检验 (非参数替代)"

            g1, g2 = groups
            code = (
                f"from scipy.stats import ttest_ind\n\n"
                f"g1 = df[df['{g}'] == {repr(g1)}]['{y_col}'].dropna()\n"
                f"g2 = df[df['{g}'] == {repr(g2)}]['{y_col}'].dropna()\n"
                f"t_stat, p_value = ttest_ind(g1, g2)\n"
                f"print(f't = {{t_stat:.3f}}, p = {{p_value:.4f}}')"
            )

            recs.append(MethodRecommendation(
                "独立样本 t 检验 (两组)",
                f"比较 {g}={g1}/{g2} 两组在 {y_col} 上的均值差异",
                [g], y_col, assumptions,
                alternative=alt_notes or "Mann-Whitney U 检验",
                python_code=code
            ))

        # ─ 1 个多分类 X (≥3 组) → ANOVA ─
        elif n_grp >= 3:
            assumptions = []
            alt_notes = ""

            if do_full_check:
                norm_results = check_normality_by_group(df[y_col], df[g])
                assumptions.extend(norm_results)
                var_result = check_variance_homogeneity(df[y_col], df[g])
                assumptions.append(var_result)
                assumptions.append(check_sample_size(n_total))
                if any(not r.passed for r in assumptions):
                    alt_notes = "建议使用 Kruskal-Wallis 检验 (非参数替代)"

            groups_str = ", ".join(repr(str(g)) for g in groups[:6])
            if len(groups) > 6:
                groups_str += ", ..."

            code = (
                f"from scipy.stats import f_oneway\n\n"
                f"groups = [g['{y_col}'].dropna().values for _, g in df.groupby('{g}')]\n"
                f"f_stat, p_value = f_oneway(*groups)\n"
                f"print(f'F = {{f_stat:.3f}}, p = {{p_value:.4f}}')\n"
                f"# 事后检验可加: from statsmodels.stats.multicomp import pairwise_tukeyhsd"
            )

            recs.append(MethodRecommendation(
                "单因素 ANOVA",
                f"比较 {g} ({n_grp} 组: {groups_str}) 在 {y_col} 上的均值差异",
                [g], y_col, assumptions,
                alternative=alt_notes or "Kruskal-Wallis 检验",
                python_code=code
            ))

    # ─ 1 个连续 X → 简单线性回归 ─
    elif n_cat_x == 0 and n_num_x >= 1:
        x = num_x[0]
        assumptions = []
        alt_notes = ""

        if do_full_check:
            clean_pair = df[[x, y_col]].dropna()
            if len(clean_pair) >= 3:
                # 残差正态性 (近似)
                slope, intercept, r_val, p_val, std_err = \
                    sp_stats.linregress(clean_pair[x], clean_pair[y_col])
                residuals = clean_pair[y_col] - (slope * clean_pair[x] + intercept)
                norm_result = check_normality(residuals)
                assumptions.append(norm_result)
                if not norm_result.passed:
                    alt_notes = "残差偏离正态, 建议 Spearman 相关或稳健回归"

            assumptions.append(check_sample_size(n_total))

        code = (
            f"from scipy.stats import linregress\n\n"
            f"result = linregress(df['{x}'].dropna(), df['{y_col}'].dropna())\n"
            f"print(f'R = {{result.rvalue:.3f}}, R² = {{result.rvalue**2:.3f}}')\n"
            f"print(f'斜率 = {{result.slope:.4f}}, p = {{result.pvalue:.4f}}')"
        )

        recs.append(MethodRecommendation(
            "简单线性回归",
            f"分析 {x} 对 {y_col} 的线性影响",
            [x], y_col, assumptions,
            alternative=alt_notes or "Spearman 秩相关 / Pearson 相关",
            python_code=code
        ))

    # ─ 多个 X (混合) → 多元回归 ─
    elif n_cat_x + n_num_x >= 2:
        x_list = cat_x + num_x
        cat_str = f" (含分类: {', '.join(cat_x)})" if cat_x else ""
        code = (
            f"import statsmodels.api as sm\n\n"
            f"X = df[{[x for x in x_list]}]"
        )
        if cat_x:
            code += (
                f"\nX = pd.get_dummies(X, columns={cat_x}, drop_first=True)"
            )
        code += (
            f"\nX = sm.add_constant(X)\n"
            f"y = df['{y_col}']\n\n"
            f"model = sm.OLS(y, X).fit()\n"
            f"print(model.summary())"
        )

        recs.append(MethodRecommendation(
            "多元线性回归",
            f"分析 {len(x_list)} 个变量对 {y_col} 的综合影响{cat_str}",
            x_list, y_col,
            alternative="随机森林回归 / XGBoost (非线性关系)",
            python_code=code
        ))

    # ─ 配对 / 重复测量 线索 ─
    _check_paired_pattern(df, y_col, cat_x, recs)

    return recs


# ---------------------------------------------------------------------------
# Y = 分类型 的分支
# ---------------------------------------------------------------------------

def _recommend_categorical_y(df, type_map, y_col, cat_x, num_x,
                              n_total, do_full_check):
    recs = []
    y_nunique = df[y_col].nunique()
    is_binary = y_nunique == 2

    # ─ 二分类 Y → 逻辑回归 ─
    if is_binary and (len(cat_x) + len(num_x) >= 1):
        x_list = cat_x + num_x
        cat_str = f" (含分类: {', '.join(cat_x)})" if cat_x else ""

        code = (
            f"from sklearn.linear_model import LogisticRegression\n"
            f"from sklearn.model_selection import train_test_split\n\n"
            f"X = df[{x_list}]"
        )
        if cat_x:
            code += f"\nX = pd.get_dummies(X, columns={cat_x}, drop_first=True)"
        code += (
            f"\ny = df['{y_col}']\n\n"
            f"X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)\n"
            f"model = LogisticRegression(max_iter=1000).fit(X_train, y_train)\n"
            f"print(f'准确率: {{model.score(X_test, y_test):.3f}}')"
        )

        recs.append(MethodRecommendation(
            "逻辑回归 (二分类)",
            f"分析 {len(x_list)} 个变量对 {y_col} (二分类) 的分类预测{cat_str}",
            x_list, y_col,
            alternative="决策树 / 随机森林 / SVM",
            python_code=code
        ))

        # 如果有 1 个数值 X → 也可做独立样本 t 检验 (视角翻转)
        if len(num_x) == 1 and len(cat_x) == 0:
            x = num_x[0]
            code2 = (
                f"from scipy.stats import ttest_ind\n\n"
                f"y0 = df[df['{y_col}']==df['{y_col}'].unique()[0]]['{x}'].dropna()\n"
                f"y1 = df[df['{y_col}']==df['{y_col}'].unique()[1]]['{x}'].dropna()\n"
                f"t_stat, p_value = ttest_ind(y0, y1)\n"
                f"print(f't = {{t_stat:.3f}}, p = {{p_value:.4f}}')"
            )
            recs.append(MethodRecommendation(
                "独立样本 t 检验 (Y 为分组)",
                f"检验 {y_col} 两组在 {x} 上的均值差异 (视角翻转)",
                [x], y_col,
                alternative="Mann-Whitney U 检验",
                python_code=code2,
                notes="⚠️ 这是视角翻转: 以 Y 为分组, X 为数值目标"
            ))

    # ─ 多分类 Y → 多项逻辑回归 / 分类树 ─
    elif not is_binary and (len(cat_x) + len(num_x) >= 1):
        x_list = cat_x + num_x
        code = (
            f"from sklearn.ensemble import RandomForestClassifier\n\n"
            f"X = pd.get_dummies(df[{x_list}], columns={cat_x}, drop_first=True) if {cat_x} else df[{x_list}]\n"
            f"y = df['{y_col}']\n\n"
            f"model = RandomForestClassifier(n_estimators=100, random_state=42).fit(X, y)\n"
            f"importances = pd.DataFrame({{'feature': X.columns, 'importance': model.feature_importances_}})\n"
            f"print(importances.sort_values('importance', ascending=False))"
        )

        recs.append(MethodRecommendation(
            "随机森林分类 (多分类)",
            f"分析 {len(x_list)} 个变量对 {y_col} ({y_nunique} 类) 的分类预测",
            x_list, y_col,
            alternative="多项逻辑回归 (statsmodels) / XGBoost",
            python_code=code
        ))

    # ─ 只有分类 X → 卡方检验 ─
    if len(cat_x) >= 1 and len(num_x) == 0:
        for x in cat_x[:3]:
            code = (
                f"from scipy.stats import chi2_contingency\n\n"
                f"ct = pd.crosstab(df['{x}'], df['{y_col}'])\n"
                f"chi2, p, dof, expected = chi2_contingency(ct)\n"
                f"print(f'χ² = {{chi2:.3f}}, p = {{p:.4f}}, dof = {{dof}}')\n"
                f"# Cramér's V: import numpy as np; np.sqrt(chi2 / (len(df) * min(ct.shape)-1))"
            )
            recs.append(MethodRecommendation(
                "卡方检验 (列联表)",
                f"检验 {x} 与 {y_col} 的独立性",
                [x], y_col,
                alternative="Fisher 精确检验 (小样本)",
                python_code=code
            ))

    return recs


# ---------------------------------------------------------------------------
# 配对模式检测
# ---------------------------------------------------------------------------

def _check_paired_pattern(df, y_col, cat_x, recs):
    """检测是否有「前后测」配对设计."""
    y_lower = y_col.lower().strip()
    paired_hints = ["before", "after", "pre", "post", "前", "后",
                    "pre_test", "post_test", "t0", "t1"]
    for hint in paired_hints:
        if hint in y_lower:
            recs.insert(0, MethodRecommendation(
                "配对 t 检验",
                f"⚠️ 检测到 '{y_col}' 可能含前后测数据",
                cat_x[:1] if cat_x else [], y_col,
                alternative="Wilcoxon 符号秩检验 (非参数替代)",
                python_code=(
                    "from scipy.stats import ttest_rel\n"
                    "t_stat, p_value = ttest_rel(df['pre'], df['post'])\n"
                    "print(f't = {t_stat:.3f}, p = {p_value:.4f}')"
                ),
                notes="请确认 Y 列是配对设计 (前后测同一批对象)"
            ))
            break


# ---------------------------------------------------------------------------
# 格式化输出
# ---------------------------------------------------------------------------

def print_recommendations(recs: list, type_map: dict,
                          y_col: str, full: bool = False):
    """格式化打印所有推荐."""
    n_total = recs[0].assumptions[-1].note.split("n=")[-1].split(":")[0] \
        if recs and recs[0].assumptions else "?"

    print(f"\n{'='*65}")
    print(f" 📊 方法推荐报告")
    print(f"{'='*65}")

    # 变量总览
    numeric_cols = [c for c, t in type_map.items() if t == "numeric"]
    cat_cols = [c for c, t in type_map.items() if t == "categorical"]
    dt_cols = [c for c, t in type_map.items() if t == "datetime"]

    print(f"\n  数据集: {len(type_map)} 列  |  数值 {len(numeric_cols)} 列"
          f"  |  分类 {len(cat_cols)} 列  |  日期 {len(dt_cols)} 列")

    # Y 列详情
    y_type = type_map.get(y_col, "?")
    y_unique = df[y_col].nunique() if y_col in df.columns else 0
    y_icon = "🔢" if y_type == "numeric" else "🏷️"
    print(f"  目标 Y: {y_icon} {y_col} [{y_type}]  (unique={y_unique})")

    if full:
        print(f"\n  全部变量:")
        for col, typ in type_map.items():
            icon = "🔢" if typ == "numeric" else ("🏷️" if typ == "categorical" else "📅")
            mark = " ← Y" if col == y_col else ""
            print(f"    {icon} {col:<25} [{typ}]{mark}")

    # ── 推荐列表 ──
    print(f"\n{'─'*65}")
    for i, rec in enumerate(recs, 1):
        print(f"\n  #{i}  {rec.method}")
        print(f"     {rec.description}")
        print(f"     Y = {rec.y_col}  |  X = {', '.join(rec.x_vars)}")

        if rec.assumptions:
            print(f"\n     📋 假设前提检查:")
            for ar in rec.assumptions:
                print(f"     {ar}")

        if rec.alternative:
            print(f"\n     💡 替代方案: {rec.alternative}")

        if rec.notes:
            print(f"\n     📝 备注: {rec.notes}")

        if full and rec.python_code:
            print(f"\n     🐍 Python 代码:")
            for line in rec.python_code.split("\n"):
                print(f"       {line}")

    print(f"\n{'─'*65}")
    print(f" 💡 提示: 加 --full 查看完整代码建议 | 加 -t <列名> 指定目标变量")
    print(f"{'='*65}\n")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="统计方法自动推荐器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            示例:
              %(prog)s data_final.csv                       自动猜测 Y, 推荐方法
              %(prog)s data_final.csv -y score              指定 Y 为 score
              %(prog)s data_final.csv -y score -x gender    指定 X 为 gender
              %(prog)s data_final.csv -y score --full       显示完整 Python 代码
              %(prog)s data_final.csv --no-check            跳过假设前提检查
        """)
    )
    parser.add_argument("input", help="清洗后的 CSV 文件路径")
    parser.add_argument("-y", "--target", "--y", default=None,
                        help="指定目标变量 (Y) 列名")
    parser.add_argument("-x", "--xvars", nargs="*", default=None,
                        help="指定自变量 (X) 列名, 用空格分隔")
    parser.add_argument("--full", action="store_true",
                        help="显示完整的 Python 代码建议和所有变量详情")
    parser.add_argument("--no-check", action="store_true",
                        help="跳过假设前提检查 (仅推荐方法)")
    parser.add_argument("--encoding", default="utf-8",
                        help="文件编码 (默认 utf-8)")

    args = parser.parse_args()

    # 读取
    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    global df  # 供 print_recommendations 引用
    global df
    df = pd.read_csv(args.input, encoding=args.encoding)
    print(f"📖 已加载: {args.input} ({df.shape[0]} 行 × {df.shape[1]} 列)")
    type_map = build_type_map(df)

    # 确定 Y
    y_col = args.target
    if y_col and y_col not in df.columns:
        print(f"⚠️ 指定 Y '{y_col}' 不存在, 可用的列: {list(df.columns)}")
        sys.exit(1)

    if not y_col:
        y_col = _guess_y(df, type_map)
        if y_col:
            print(f"🎯 自动猜测目标变量 Y = '{y_col}'"
                  f" ({type_map[y_col]})")

    # 推荐
    recs = recommend_methods(
        df, type_map, y_col=y_col, x_cols=args.xvars,
        do_full_check=not args.no_check
    )

    # 输出
    print_recommendations(recs, type_map, y_col, full=args.full)

    return recs


if __name__ == "__main__":
    main()
