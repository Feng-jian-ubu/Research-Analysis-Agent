#!/usr/bin/env python3
"""
statisticsexecutor.py — 统计方法执行器

功能:
  根据 methodselector 的推荐结果或用户手动指定，实际执行统计分析。
  输出: 控制台报告 + results.json + results_summary.md

用法:
  # 自动模式 (内部调用 methodselector 逻辑推荐方法)
  python3 statisticsexecutor.py data_final.csv

  # 手动指定方法
  python3 statisticsexecutor.py data_final.csv --method ttest --target score --x gender
  python3 statisticsexecutor.py data_final.csv --method anova --target salary --x education
  python3 statisticsexecutor.py data_final.csv --method regression --target score --x age
  python3 statisticsexecutor.py data_final.csv --method logistic --target is_pass --x age gender
  python3 statisticsexecutor.py data_final.csv --method chi2 --x gender --target is_pass
  python3 statisticsexecutor.py data_final.csv --method correlation
  python3 statisticsexecutor.py data_final.csv --method describe

  # 跳过假设检查
  python3 statisticsexecutor.py data_final.csv --no-check
"""

import sys
import os
import argparse
import json
import textwrap
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np
from scipy import stats as sp_stats


# ===================================================================
# 类型识别 (与 methodselector.py 共享同一逻辑)
# ===================================================================

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


# ===================================================================
# 假设检查 (精简版)
# ===================================================================

class AssumptionResult:
    def __init__(self, name: str, passed: bool, p_value: float, note: str):
        self.name = name
        self.passed = passed
        self.p_value = p_value
        self.note = note


def check_normality(series: pd.Series) -> AssumptionResult:
    clean = series.dropna()
    if len(clean) < 3:
        return AssumptionResult("正态性 (Shapiro-Wilk)", False, 0, "样本量不足")
    if len(clean) > 5000:
        return AssumptionResult("正态性 (Shapiro-Wilk)", True, 0.5, "n>5000, 建议看Q-Q图")
    stat, p = sp_stats.shapiro(clean)
    passed = p > 0.05
    note = "正态" if passed else "偏离正态"
    return AssumptionResult("正态性 (Shapiro-Wilk)", passed, p, note)


def check_variance_homogeneity(series: pd.Series, group: pd.Series) -> AssumptionResult:
    clean_df = pd.DataFrame({"value": series, "group": group}).dropna()
    if clean_df["group"].nunique() < 2 or len(clean_df) < 6:
        return AssumptionResult("方差齐性 (Levene)", False, 0, "数据不足")
    groups = [g["value"].values for _, g in clean_df.groupby("group")]
    if any(len(g) < 2 for g in groups):
        return AssumptionResult("方差齐性 (Levene)", False, 0, "某组样本不足")
    stat, p = sp_stats.levene(*groups)
    passed = p > 0.05
    return AssumptionResult("方差齐性 (Levene)", passed, p, "方差齐" if passed else "方差不齐")


# ===================================================================
# 效应量 & 置信区间 工具函数
# ===================================================================

def cohens_d(s1: np.ndarray, s2: np.ndarray) -> float:
    """Cohen's d (独立样本)."""
    n1, n2 = len(s1), len(s2)
    s1_mean, s2_mean = s1.mean(), s2.mean()
    var1, var2 = s1.var(ddof=1), s2.var(ddof=1)
    pooled = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled == 0:
        return 0.0
    return (s1_mean - s2_mean) / pooled


def cohens_d_interpret(d: float) -> str:
    ad = abs(d)
    if ad < 0.2:
        return "极小"
    if ad < 0.5:
        return "小"
    if ad < 0.8:
        return "中"
    return "大"


def eta_squared(groups: list) -> float:
    """η² = SS_between / SS_total 用于 ANOVA."""
    all_vals = np.concatenate(groups)
    grand_mean = all_vals.mean()
    ss_total = np.sum((all_vals - grand_mean) ** 2)
    if ss_total == 0:
        return 0.0
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
    return ss_between / ss_total


def eta_squared_interpret(eta2: float) -> str:
    if eta2 < 0.01:
        return "极小"
    if eta2 < 0.06:
        return "小"
    if eta2 < 0.14:
        return "中"
    return "大"


def cramers_v(contingency_table: np.ndarray) -> float:
    """Cramér's V 用于卡方检验."""
    chi2 = sp_stats.chi2_contingency(contingency_table)[0]
    n = contingency_table.sum()
    k = min(contingency_table.shape)
    if n == 0 or k <= 1:
        return 0.0
    v = np.sqrt(chi2 / (n * (k - 1)))
    return min(v, 1.0)


def cramers_v_interpret(v: float) -> str:
    if v < 0.1:
        return "极小"
    if v < 0.3:
        return "小"
    if v < 0.5:
        return "中"
    return "大"


def mean_ci(data: np.ndarray, confidence: float = 0.95) -> tuple:
    """均值 + 置信区间."""
    n = len(data)
    if n < 2:
        return data.mean(), data.mean(), data.mean()
    se = sp_stats.sem(data, ddof=1)
    h = se * sp_stats.t.ppf((1 + confidence) / 2, n - 1)
    return data.mean(), data.mean() - h, data.mean() + h


def bootstrap_ci(data1: np.ndarray, data2: np.ndarray,
                 func, n_bootstrap: int = 5000,
                 confidence: float = 0.95) -> tuple:
    """Bootstrap 置信区间 (用于 Cohen's d 等非标准统计量)."""
    combined = np.concatenate([data1, data2])
    n1, n2 = len(data1), len(data2)
    estimates = []
    for _ in range(n_bootstrap):
        resample1 = np.random.choice(data1, n1, replace=True)
        resample2 = np.random.choice(data2, n2, replace=True)
        try:
            estimates.append(func(resample1, resample2))
        except Exception:
            continue
    if len(estimates) < 100:
        return np.nan, np.nan
    alpha = (1 - confidence) / 2
    lower = np.percentile(estimates, alpha * 100)
    upper = np.percentile(estimates, (1 - alpha) * 100)
    return lower, upper


# ===================================================================
# 结果容器
# ===================================================================

class AnalysisResult:
    """单个分析的结果，可序列化为 dict."""

    def __init__(self, method: str, y_col: str = "", x_vars: list = None,
                 n_total: int = 0, n_valid: int = 0):
        self.method = method
        self.y_col = y_col
        self.x_vars = x_vars or []
        self.n_total = n_total
        self.n_valid = n_valid
        self.statistics = {}      # 检验统计量
        self.p_value = None
        self.effect_size = {}     # {name: value, interpretation: str}
        self.ci_95 = {}           # {name: [lower, upper]}
        self.group_stats = []     # 各组的描述统计
        self.assumptions = []     # [AssumptionResult]
        self.interpretation = ""  # 一句话结论
        self.code_snippet = ""    # 复现代码

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "y_col": self.y_col,
            "x_vars": self.x_vars,
            "sample_size": {"total": self.n_total, "valid": self.n_valid},
            "statistics": self.statistics,
            "p_value": self.p_value,
            "effect_size": self.effect_size,
            "ci_95": self.ci_95,
            "group_stats": self.group_stats,
            "assumptions": [{"name": a.name, "passed": a.passed,
                             "p_value": a.p_value, "note": a.note}
                            for a in self.assumptions],
            "interpretation": self.interpretation,
            "code_snippet": self.code_snippet,
        }


# ===================================================================
# 各种统计方法的执行函数
# ===================================================================

def _describe(df: pd.DataFrame, type_map: dict,
              y_col: str, x_vars: list) -> AnalysisResult:
    """描述统计（兜底用）. """
    res = AnalysisResult("描述统计", y_col, x_vars, len(df))
    numeric_cols = [c for c, t in type_map.items() if t == "numeric"]
    cat_cols = [c for c, t in type_map.items() if t == "categorical"]

    # 数值型描述统计
    for col in numeric_cols:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        m, ci_low, ci_high = mean_ci(s.values)
        desc = {
            "column": col, "n": len(s), "missing": int(df[col].isna().sum()),
            "mean": round(m, 4), "std": round(s.std(ddof=1), 4),
            "min": round(s.min(), 4), "q25": round(s.quantile(0.25), 4),
            "median": round(s.median(), 4), "q75": round(s.quantile(0.75), 4),
            "max": round(s.max(), 4), "ci_95": [round(ci_low, 4), round(ci_high, 4)],
        }
        res.group_stats.append(desc)
        res.statistics[col] = desc

    # 分类型频数统计
    for col in cat_cols:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        freq = s.value_counts()
        desc = {
            "column": col, "n": len(s), "missing": int(df[col].isna().sum()),
            "unique": int(s.nunique()),
            "frequencies": {str(k): int(v) for k, v in freq.items()},
        }
        res.group_stats.append(desc)
        res.statistics[col] = desc

    res.interpretation = f"包含 {len(numeric_cols)} 个数值列和 {len(cat_cols)} 个分类列的描述统计"
    return res


def _ttest(df: pd.DataFrame, y_col: str, x_col: str,
           do_check: bool = True) -> AnalysisResult:
    """独立样本 t 检验 (含 Welch 校正)."""
    groups = df[x_col].dropna().unique()
    g1_name, g2_name = groups[0], groups[1]
    g1 = df[df[x_col] == g1_name][y_col].dropna().values
    g2 = df[df[x_col] == g2_name][y_col].dropna().values

    res = AnalysisResult("独立样本 t 检验", y_col, [x_col],
                         len(df), len(g1) + len(g2))
    res.group_stats = [
        {"group": str(g1_name), "n": len(g1),
         "mean": round(g1.mean(), 4), "std": round(g1.std(ddof=1), 4)},
        {"group": str(g2_name), "n": len(g2),
         "mean": round(g2.mean(), 4), "std": round(g2.std(ddof=1), 4)},
    ]

    if do_check:
        for g, vals in [(g1_name, g1), (g2_name, g2)]:
            res.assumptions.append(check_normality(pd.Series(vals)))
        res.assumptions.append(check_variance_homogeneity(
            df[y_col], df[x_col]))

    # Welch t-test (默认不等方差，更稳健)
    equal_var = True
    for a in res.assumptions:
        if "方差齐" in a.note and not a.passed:
            equal_var = False

    t_stat, p_val = sp_stats.ttest_ind(g1, g2, equal_var=equal_var)
    d = cohens_d(g1, g2)
    d_low, d_high = bootstrap_ci(g1, g2, cohens_d)

    res.statistics = {
        "t_statistic": round(t_stat, 4),
        "degrees_of_freedom": len(g1) + len(g2) - 2,
        "welch_corrected": not equal_var,
    }
    res.p_value = p_val
    res.effect_size = {
        "cohens_d": round(d, 4),
        "interpretation": cohens_d_interpret(d),
    }
    res.ci_95 = {
        "mean_diff_95ci": [
            round(g1.mean() - g2.mean() - t_stat * np.sqrt(
                g1.var(ddof=1) / len(g1) + g2.var(ddof=1) / len(g2)), 4),
            round(g1.mean() - g2.mean() + t_stat * np.sqrt(
                g1.var(ddof=1) / len(g1) + g2.var(ddof=1) / len(g2)), 4),
        ],
    }
    if not np.isnan(d_low):
        res.effect_size["cohens_d_95ci"] = [round(d_low, 4), round(d_high, 4)]

    sig = "显著" if p_val < 0.05 else "不显著"
    res.interpretation = (
        f"在 {x_col}={g1_name}/{g2_name} 两组间，{y_col} 的差异{sig} "
        f"(t={t_stat:.3f}, p={p_val:.4f}, Cohen's d={d:.3f}【{cohens_d_interpret(d)}】)"
    )

    eq_str = ", equal_var=False" if not equal_var else ""
    g1r, g2r = repr(str(g1_name)), repr(str(g2_name))
    res.code_snippet = (
        f"from scipy.stats import ttest_ind\n\n"
        f"g1 = df[df['{x_col}']=={g1r}]['{y_col}'].dropna()\n"
        f"g2 = df[df['{x_col}']=={g2r}]['{y_col}'].dropna()\n"
        f"t_stat, p_val = ttest_ind(g1, g2{eq_str})\n"
        f"print(f't = {{t_stat:.3f}}, p = {{p_val:.4f}}')"
    )
    return res


def _mannwhitney(df: pd.DataFrame, y_col: str, x_col: str) -> AnalysisResult:
    """Mann-Whitney U 检验 (非参数替代 t 检验)."""
    groups = df[x_col].dropna().unique()
    g1_name, g2_name = groups[0], groups[1]
    g1 = df[df[x_col] == g1_name][y_col].dropna().values
    g2 = df[df[x_col] == g2_name][y_col].dropna().values

    res = AnalysisResult("Mann-Whitney U 检验", y_col, [x_col],
                         len(df), len(g1) + len(g2))
    u_stat, p_val = sp_stats.mannwhitneyu(g1, g2)

    # 秩双列相关系数 (effect size)
    r = 1 - (2 * u_stat) / (len(g1) * len(g2))
    r_abs = abs(r)

    res.statistics = {"U_statistic": round(u_stat, 4)}
    res.p_value = p_val
    res.effect_size = {
        "rank_biserial_r": round(r, 4),
        "interpretation": ("大" if r_abs > 0.5 else
                           "中" if r_abs > 0.3 else
                           "小" if r_abs > 0.1 else "极小"),
    }
    res.group_stats = [
        {"group": str(g1_name), "n": len(g1),
         "median": round(np.median(g1), 4),
         "mean_rank": round(np.mean([sp_stats.rankdata(np.concatenate([g1, g2]))[:len(g1)]]), 4)},
        {"group": str(g2_name), "n": len(g2),
         "median": round(np.median(g2), 4)},
    ]

    sig = "显著" if p_val < 0.05 else "不显著"
    res.interpretation = (
        f"Mann-Whitney U 检验: {x_col} 两组在 {y_col} 上{sig} "
        f"(U={u_stat:.1f}, p={p_val:.4f}, r={r:.3f})"
    )
    return res


def _anova(df: pd.DataFrame, y_col: str, x_col: str,
           do_check: bool = True) -> AnalysisResult:
    """单因素 ANOVA (含 Welch ANOVA 后备)."""
    groups_raw = df[[x_col, y_col]].dropna()
    groups_list = []
    group_info = []
    for g_name, g_data in groups_raw.groupby(x_col):
        vals = g_data[y_col].values
        if len(vals) >= 2:
            groups_list.append(vals)
            group_info.append({
                "group": str(g_name), "n": len(vals),
                "mean": round(vals.mean(), 4),
                "std": round(vals.std(ddof=1), 4),
            })

    res = AnalysisResult("单因素 ANOVA", y_col, [x_col],
                         len(df), sum(len(g) for g in groups_list))
    res.group_stats = group_info
    n_grp = len(groups_list)

    if do_check:
        for gi in group_info:
            g_vals = [g for g in groups_list if len(g) == gi["n"]][0]
            res.assumptions.append(check_normality(pd.Series(g_vals)))
        if n_grp >= 2:
            res.assumptions.append(check_variance_homogeneity(
                df[y_col], df[x_col]))

    # 检查是否需要用 Welch ANOVA
    use_welch = False
    for a in res.assumptions:
        if "方差齐" in a.note and not a.passed:
            use_welch = True

    if use_welch and n_grp >= 2:
        # Welch ANOVA (scipy >= 1.13 内置, 否则手动)
        try:
            f_stat, p_val = sp_stats.oneway(*groups_list, equal_var=False)
            res.method = "Welch ANOVA (方差不齐校正)"
        except TypeError:
            f_stat, p_val = sp_stats.f_oneway(*groups_list)
    else:
        f_stat, p_val = sp_stats.f_oneway(*groups_list)

    eta2 = eta_squared(groups_list)

    res.statistics = {
        "F_statistic": round(f_stat, 4),
        "df_between": n_grp - 1,
        "df_within": sum(len(g) for g in groups_list) - n_grp,
    }
    res.p_value = p_val
    res.effect_size = {
        "eta_squared": round(eta2, 4),
        "interpretation": eta_squared_interpret(eta2),
    }

    sig = "显著" if p_val < 0.05 else "不显著"
    res.interpretation = (
        f"单因素 ANOVA: {x_col} ({n_grp} 组) 在 {y_col} 上{sig} "
        f"(F={f_stat:.3f}, p={p_val:.4f}, η²={eta2:.4f}【{eta_squared_interpret(eta2)}】)"
    )

    res.code_snippet = (
        f"from scipy.stats import f_oneway\n\n"
        f"groups = [g['{y_col}'].dropna().values for _, g in df.groupby('{x_col}')]\n"
        f"f_stat, p_val = f_oneway(*groups)\n"
        f"print(f'F = {{f_stat:.3f}}, p = {{p_val:.4f}}')"
    )
    return res


def _kruskal(df: pd.DataFrame, y_col: str, x_col: str) -> AnalysisResult:
    """Kruskal-Wallis 检验 (非参数 ANOVA)."""
    groups_raw = df[[x_col, y_col]].dropna()
    groups_list = []
    group_info = []
    for g_name, g_data in groups_raw.groupby(x_col):
        vals = g_data[y_col].values
        if len(vals) >= 2:
            groups_list.append(vals)
            group_info.append({
                "group": str(g_name), "n": len(vals),
                "median": round(np.median(vals), 4),
            })

    res = AnalysisResult("Kruskal-Wallis 检验", y_col, [x_col],
                         len(df), sum(len(g) for g in groups_list))
    res.group_stats = group_info

    h_stat, p_val = sp_stats.kruskal(*groups_list)
    n_total = sum(len(g) for g in groups_list)
    # ε² 效应量 (epsilon-squared)
    eps2 = (h_stat - len(groups_list) + 1) / (n_total - len(groups_list))
    eps2 = max(0, min(1, eps2))

    res.statistics = {"H_statistic": round(h_stat, 4), "df": len(groups_list) - 1}
    res.p_value = p_val
    res.effect_size = {
        "epsilon_squared": round(eps2, 4),
        "interpretation": eta_squared_interpret(eps2),
    }

    sig = "显著" if p_val < 0.05 else "不显著"
    res.interpretation = (
        f"Kruskal-Wallis 检验: {x_col} ({len(groups_list)} 组) 在 {y_col} 上{sig} "
        f"(H={h_stat:.3f}, p={p_val:.4f}, ε²={eps2:.4f})"
    )
    return res


def _linear_regression(df: pd.DataFrame, y_col: str, x_vars: list,
                       type_map: dict, do_check: bool = True) -> AnalysisResult:
    """线性回归 (简单/多元)."""
    cat_x = [c for c in x_vars if type_map.get(c) == "categorical"]
    num_x = [c for c in x_vars if type_map.get(c) == "numeric"]

    res = AnalysisResult("线性回归", y_col, x_vars, len(df))
    clean_df = df[x_vars + [y_col]].dropna()
    res.n_valid = len(clean_df)

    # 构建 X 矩阵
    X = clean_df[num_x].copy() if num_x else pd.DataFrame(index=clean_df.index)
    if cat_x:
        X = pd.concat([X, pd.get_dummies(clean_df[cat_x], drop_first=True)], axis=1)
    X = sm_add_constant(X)
    y = clean_df[y_col]

    if X.shape[1] < 2 or len(X) < X.shape[1] + 2:
        res.interpretation = "样本量不足, 无法拟合回归模型"
        return res

    # 用 sklearn 做回归 (更可控)
    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score
        model = LinearRegression()
        model.fit(X.iloc[:, 1:], y)  # 去掉常数项
        y_pred = model.predict(X.iloc[:, 1:])
        r2 = r2_score(y, y_pred)
        n, k = len(y), X.shape[1] - 1
        adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k - 1) if n > k + 1 else r2

        # F 检验
        residuals = y - y_pred
        ss_res = np.sum(residuals ** 2)
        ss_reg = np.sum((y_pred - y.mean()) ** 2)
        f_stat = (ss_reg / k) / (ss_res / (n - k - 1)) if ss_res > 0 and n > k + 1 else 0
        f_p = 1 - sp_stats.f.cdf(f_stat, k, n - k - 1)

        if do_check and n >= 20:
            res.assumptions.append(check_normality(pd.Series(residuals)))

        # 系数表
        coef_table = []
        feature_names = X.columns[1:]
        for i, name in enumerate(feature_names):
            coef_table.append({
                "feature": name, "coef": round(model.coef_[i], 4),
            })

        res.statistics = {
            "R_squared": round(r2, 4),
            "adjusted_R_squared": round(adj_r2, 4),
            "F_statistic": round(f_stat, 4),
            "F_p_value": round(f_p, 4),
            "df_model": k,
            "df_residual": n - k - 1,
            "coefficients": coef_table,
        }
        res.p_value = f_p
        res.effect_size = {
            "R_squared": round(r2, 4),
            "adjusted_R_squared": round(adj_r2, 4),
            "interpretation": ("强" if r2 > 0.5 else
                               "中" if r2 > 0.25 else
                               "弱" if r2 > 0.1 else "极弱"),
        }

        sig = "显著" if f_p < 0.05 else "不显著"
        res.interpretation = (
            f"线性回归: {len(x_vars)} 个变量对 {y_col} 的回归模型{sig} "
            f"(R²={r2:.4f}, adj.R²={adj_r2:.4f}, F={f_stat:.3f}, p={f_p:.4f})"
        )

        # 代码
        dum_str = ""
        if cat_x:
            dum_str = f"\nX = pd.get_dummies(X, columns={cat_x}, drop_first=True)"
        res.code_snippet = (
            f"from sklearn.linear_model import LinearRegression\n\n"
            f"X = df[{x_vars}]{dum_str}\n"
            f"y = df['{y_col}']\n"
            f"model = LinearRegression().fit(X, y)\n"
            f"print(f'R² = {{model.score(X, y):.4f}}')"
        )

    except ImportError:
        res.interpretation = "需要 sklearn 库: pip install scikit-learn"

    return res


def _logistic(df: pd.DataFrame, y_col: str, x_vars: list,
              type_map: dict) -> AnalysisResult:
    """逻辑回归 (二分类 Y)."""
    cat_x = [c for c in x_vars if type_map.get(c) == "categorical"]
    num_x = [c for c in x_vars if type_map.get(c) == "numeric"]

    res = AnalysisResult("逻辑回归", y_col, x_vars, len(df))
    clean_df = df[x_vars + [y_col]].dropna()
    res.n_valid = len(clean_df)

    X = clean_df[num_x].copy() if num_x else pd.DataFrame(index=clean_df.index)
    if cat_x:
        X = pd.concat([X, pd.get_dummies(clean_df[cat_x], drop_first=True)], axis=1)
    y = clean_df[y_col]

    if X.shape[1] < 1 or len(X) < 20:
        res.interpretation = "样本量不足, 无法拟合逻辑回归模型"
        return res

    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, roc_auc_score

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42)

        model = LogisticRegression(max_iter=1000, solver='lbfgs')
        model.fit(X_train, y_train)

        acc = accuracy_score(y_test, model.predict(X_test))
        try:
            auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
        except Exception:
            auc = None

        coef_table = []
        for i, name in enumerate(X.columns):
            coef_table.append({
                "feature": name,
                "coef": round(model.coef_[0][i], 4),
                "odds_ratio": round(np.exp(model.coef_[0][i]), 4),
            })

        res.statistics = {
            "accuracy": round(acc, 4),
            "auc_roc": round(auc, 4) if auc is not None else None,
            "n_features": X.shape[1],
            "coefficients": coef_table,
        }
        res.effect_size = {
            "accuracy": round(acc, 4),
            "auc_roc": round(auc, 4) if auc is not None else None,
            "interpretation": ("优秀" if (auc or 0) > 0.8 else
                               "良好" if (auc or 0) > 0.7 else
                               "一般" if (auc or 0) > 0.6 else "差"),
        }

        res.interpretation = (
            (f"逻辑回归: 准确率={acc:.3f}, AUC={auc:.3f}" if auc is not None else f"逻辑回归: 准确率={acc:.3f}, AUC=N/A")
        )

        dum_str = ""
        if cat_x:
            dum_str = f"\nX = pd.get_dummies(X, columns={cat_x}, drop_first=True)"
        res.code_snippet = (
            f"from sklearn.linear_model import LogisticRegression\n\n"
            f"X = df[{x_vars}]{dum_str}\n"
            f"y = df['{y_col}']\n"
            f"model = LogisticRegression(max_iter=1000).fit(X, y)\n"
            f"print(f'Accuracy = {{model.score(X, y):.3f}}')"
        )

    except ImportError:
        res.interpretation = "需要 sklearn 库: pip install scikit-learn"

    return res


def _chi2(df: pd.DataFrame, y_col: str, x_col: str) -> AnalysisResult:
    """卡方独立性检验."""
    res = AnalysisResult("卡方独立性检验", y_col, [x_col], len(df))
    ct = pd.crosstab(df[x_col], df[y_col])
    chi2, p_val, dof, expected = sp_stats.chi2_contingency(ct)
    v = cramers_v(ct.values)

    res.statistics = {
        "chi_squared": round(chi2, 4),
        "degrees_of_freedom": dof,
    }
    res.p_value = p_val
    res.effect_size = {
        "cramers_v": round(v, 4),
        "interpretation": cramers_v_interpret(v),
    }
    # 每组频数
    res.group_stats = []
    for row_name in ct.index:
        for col_name in ct.columns:
            res.group_stats.append({
                f"{x_col}={row_name}": str(row_name),
                f"{y_col}={col_name}": str(col_name),
                "observed": int(ct.loc[row_name, col_name]),
                "expected": round(expected[ct.index.get_loc(row_name),
                                           ct.columns.get_loc(col_name)], 2),
            })

    sig = "显著" if p_val < 0.05 else "不显著"
    res.interpretation = (
        f"卡方检验: {x_col} 与 {y_col} 的关联{sig} "
        f"(χ²={chi2:.3f}, p={p_val:.4f}, Cramér's V={v:.4f}【{cramers_v_interpret(v)}】)"
    )
    res.code_snippet = (
        f"from scipy.stats import chi2_contingency\n\n"
        f"ct = pd.crosstab(df['{x_col}'], df['{y_col}'])\n"
        f"chi2, p, dof, expected = chi2_contingency(ct)\n"
        f"print(f'χ² = {{chi2:.3f}}, p = {{p:.4f}}')"
    )
    return res


def _correlation(df: pd.DataFrame, y_col: Optional[str] = None,
                 x_vars: Optional[list] = None) -> AnalysisResult:
    """相关性矩阵 (数值变量之间)."""
    numeric_cols = [c for c, t in build_type_map(df).items()
                    if t == "numeric"]
    if not numeric_cols:
        return AnalysisResult("相关性分析", "", [], len(df),
                              interpretation="没有数值变量, 无法计算相关")

    mat = df[numeric_cols].dropna()
    res = AnalysisResult("Pearson 相关性矩阵", "", numeric_cols, len(df), len(mat))

    corr = mat.corr()
    pairs = []
    for i in range(len(corr.columns)):
        for j in range(i + 1, len(corr.columns)):
            c1, c2 = corr.columns[i], corr.columns[j]
            r_val = corr.iloc[i, j]
            n = len(mat)
            # 近似 p 值
            t_val = r_val * np.sqrt((n - 2) / max(1 - r_val ** 2, 1e-10))
            p_val = 2 * (1 - sp_stats.t.cdf(abs(t_val), n - 2))
            pairs.append({
                "var1": c1, "var2": c2,
                "pearson_r": round(r_val, 4),
                "p_value": round(p_val, 4),
                "n": n,
            })
    pairs.sort(key=lambda x: -abs(x["pearson_r"]))

    res.statistics = {"pairs": pairs[:30], "matrix": corr.round(4).to_dict()}
    if pairs:
        top = pairs[0]
        p_abs = abs(top["pearson_r"])
        strength = ("强" if p_abs > 0.7 else "中" if p_abs > 0.4 else "弱")
        sig = "显著" if top["p_value"] < 0.05 else "不显著"
        res.interpretation = (
            f"最强相关: {top['var1']} vs {top['var2']} "
            f"r={top['pearson_r']:.4f} ({strength}, {sig})"
        )

    res.code_snippet = (
        f"df.corr()\n\n"
        f"# 或带 p 值:\n"
        f"from scipy.stats import pearsonr\n"
        f"r, p = pearsonr(df['col1'], df['col2'])\n"
        f"print(f'r = {{r:.3f}}, p = {{p:.4f}}')"
    )
    return res


# ===================================================================
# 方法分发
# ===================================================================

METHOD_MAP = {
    "describe": _describe,
    "ttest": _ttest,
    "mannwhitney": _mannwhitney,
    "anova": _anova,
    "kruskal": _kruskal,
    "regression": _linear_regression,
    "logistic": _logistic,
    "chi2": _chi2,
    "correlation": _correlation,
}

METHOD_ALIASES = {
    "t": "ttest", "t-test": "ttest", "t_test": "ttest",
    "mw": "mannwhitney", "mann-whitney": "mannwhitney",
    "aov": "anova",
    "kw": "kruskal", "kruskal-wallis": "kruskal",
    "linreg": "regression", "linear": "regression", "ols": "regression",
    "logit": "logistic",
    "chisq": "chi2", "chisquare": "chi2",
    "corr": "correlation", "pearson": "correlation",
    "desc": "describe", "summary": "describe",
}


def resolve_method(method: str) -> str:
    m = method.lower().strip()
    if m in METHOD_MAP:
        return m
    if m in METHOD_ALIASES:
        return METHOD_ALIASES[m]
    return ""


def sm_add_constant(X: pd.DataFrame) -> pd.DataFrame:
    """添加常数项 (无需 statsmodels)."""
    X = X.copy()
    X.insert(0, "const", 1.0)
    return X


# ===================================================================
# 推荐器 (精简版, 自动选择方法)
# ===================================================================

def _guess_y(df: pd.DataFrame, type_map: dict) -> Optional[str]:
    _DISQUALIFIED = ["id", "编号", "序号", "index", "row", "行号",
                     "name", "姓名", "url", "link"]
    numeric_cols = [c for c, t in type_map.items() if t == "numeric"]
    cat_cols = [c for c, t in type_map.items() if t == "categorical"]

    def _score(col: str, typ: str) -> float:
        col_lower = col.lower().strip()
        for kw in _DISQUALIFIED:
            if kw in col_lower:
                return -1.0
        score = 0.0
        for kw in ["target", "label", "result", "score", "grade", "y",
                    "outcome", "response", "dependent", "value",
                    "目标", "结果", "分数", "成绩", "标签", "因变量",
                    "类别", "class", "type", "category", "group",
                    "depvar", "dv", "is_"]:
            if kw in col_lower:
                score += 2.0
        cols = list(df.columns)
        idx = cols.index(col)
        if idx == len(cols) - 1:
            score += 1.5
        elif idx >= len(cols) - 3:
            score += 0.5
        if typ == "categorical" and df[col].nunique() == 2:
            score += 2.0
        return score

    candidates = numeric_cols + cat_cols
    scored = [(c, _score(c, type_map[c])) for c in candidates]
    scored = [(c, s) for c, s in scored if s >= 0]
    if not scored:
        return candidates[0] if candidates else None
    scored.sort(key=lambda x: -x[1])
    return scored[0][0]


def auto_detect_method(df: pd.DataFrame, type_map: dict,
                        y_col: str, x_vars: list) -> tuple:
    """自动检测最适合的方法. 返回 (method_name, kwargs)."""
    y_type = type_map.get(y_col, "categorical")

    if y_type == "numeric":
        if len(x_vars) == 1:
            x_type = type_map.get(x_vars[0], "categorical")
            if x_type == "categorical":
                n_grp = df[x_vars[0]].nunique()
                if n_grp == 2:
                    return "ttest", {}
                elif n_grp >= 3:
                    return "anova", {}
            elif x_type == "numeric":
                return "regression", {}
        else:
            return "regression", {}

    elif y_type == "categorical":
        y_nunique = df[y_col].nunique()
        all_cat_x = all(type_map.get(c) == "categorical" for c in x_vars)
        if y_nunique == 2:
            return "logistic", {}
        else:
            return "logistic", {}

    return "describe", {}


# ===================================================================
# 输出工具
# ===================================================================

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            if np.isnan(obj):
                return None
            return float(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (pd.Timestamp,)):
            return str(obj)
        return super().default(obj)


def write_json(result: AnalysisResult, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
    print(f"  💾 JSON: {path}")


def write_md(result: AnalysisResult, path: str):
    """输出可读的 Markdown 报告."""
    d = result.to_dict()
    lines = []
    lines.append(f"# 统计分析报告\n")
    lines.append(f"**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**方法:** {d['method']}\n")
    lines.append(f"**目标变量 (Y):** {d['y_col']}")
    if d['x_vars']:
        lines.append(f"  \n**自变量 (X):** {', '.join(d['x_vars'])}")
    lines.append(f"\n---\n")
    lines.append(f"## 样本信息\n")
    lines.append(f"- 总样本量: {d['sample_size']['total']}")
    lines.append(f"- 有效样本量: {d['sample_size']['valid']}\n")

    # 各组统计
    if d['group_stats']:
        lines.append(f"## 分组描述统计\n")
        for gs in d['group_stats']:
            items = [f"{k}: {v}" for k, v in gs.items()]
            lines.append(f"- {' | '.join(items)}")
        lines.append("")

    # 假设检验
    if d['assumptions']:
        lines.append(f"## 假设前提检查\n")
        for a in d['assumptions']:
            icon = "✅" if a['passed'] else "⚠️"
            lines.append(f"- {icon} **{a['name']}**: p={a['p_value']:.4f} — {a['note']}")
        lines.append("")

    # 统计量 & p 值
    lines.append(f"## 检验结果\n")
    for k, v in d['statistics'].items():
        if k != "coefficients" and k != "pairs" and k != "matrix":
            if isinstance(v, float):
                lines.append(f"- **{k}:** {v:.4f}")
            else:
                lines.append(f"- **{k}:** {v}")
    lines.append(f"- **p 值:** {d['p_value']:.6f}" if d['p_value'] is not None
                 else "- **p 值:** N/A")

    # 效应量
    if d['effect_size']:
        lines.append(f"\n## 效应量\n")
        for k, v in d['effect_size'].items():
            if k == "interpretation":
                continue
            if isinstance(v, float):
                lines.append(f"- **{k}:** {v:.4f}")
            else:
                lines.append(f"- **{k}:** {v}")
        lines.append(f"- **强度:** {d['effect_size'].get('interpretation', 'N/A')}")

    # 置信区间
    if d['ci_95']:
        lines.append(f"\n## 95% 置信区间\n")
        for k, (lo, hi) in d['ci_95'].items():
            lines.append(f"- **{k}:** [{lo:.4f}, {hi:.4f}]")

    # 系数表 (回归)
    if "coefficients" in d['statistics']:
        lines.append(f"\n## 回归系数\n")
        lines.append(f"| 变量 | 系数 |")
        lines.append(f"|------|------|")
        for coef in d['statistics']['coefficients']:
            lines.append(f"| {coef['feature']} | {coef['coef']} |")

    # 相关性矩阵
    if "pairs" in d['statistics']:
        lines.append(f"\n## 相关性 (Top 10)\n")
        lines.append(f"| 变量1 | 变量2 | r | p值 |")
        lines.append(f"|-------|-------|----|-----|")
        for pair in d['statistics']['pairs'][:10]:
            lines.append(f"| {pair['var1']} | {pair['var2']} | "
                         f"{pair['pearson_r']:.4f} | {pair['p_value']:.4f} |")

    # 解释
    lines.append(f"\n## 结论\n")
    lines.append(f"{d['interpretation']}\n")

    # 代码
    if d['code_snippet']:
        lines.append(f"\n## 复现代码\n")
        lines.append(f"```python\n{d['code_snippet']}\n```\n")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  📝 MD:  {path}")


def print_console(result: AnalysisResult):
    """控制台输出."""
    d = result.to_dict()
    print(f"\n{'='*60}")
    print(f" 📊 {d['method']}")
    print(f"{'='*60}")
    if d['y_col']:
        print(f"   Y: {d['y_col']}")
    if d['x_vars']:
        print(f"   X: {', '.join(d['x_vars'])}")
    print(f"   样本: {d['sample_size']['valid']}/{d['sample_size']['total']} 有效")

    if d['assumptions']:
        print(f"\n  📋 假设检查:")
        for a in d['assumptions']:
            icon = "✅" if a['passed'] else "⚠️"
            print(f"    {icon} {a['name']}: p={a['p_value']:.4f} — {a['note']}")

    print(f"\n  📊 检验结果:")
    for k, v in d['statistics'].items():
        if k not in ("coefficients", "pairs", "matrix"):
            if isinstance(v, float):
                print(f"     {k}: {v:.4f}")
            else:
                print(f"     {k}: {v}")
    if d['p_value'] is not None:
        print(f"     p_value: {d['p_value']:.6f}  "
              f"{'✅ 显著 (p<0.05)' if d['p_value'] < 0.05 else '❌ 不显著 (p≥0.05)'}")

    if d['effect_size']:
        print(f"\n  📐 效应量:")
        for k, v in d['effect_size'].items():
            if isinstance(v, float):
                print(f"     {k}: {v:.4f}")
            elif k != "interpretation":
                print(f"     {k}: {v}")
        print(f"     → {d['effect_size'].get('interpretation', '')}")

    print(f"\n  💬 {d['interpretation']}")
    print(f"{'='*60}\n")


# ===================================================================
# CLI 入口
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="统计方法执行器 — 自动执行 t 检验 / ANOVA / 回归 / 卡方等",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            示例:
              %(prog)s data_final.csv                           自动检测方法
              %(prog)s data_final.csv --method ttest -y score -x gender
              %(prog)s data_final.csv --method anova -y score -x education
              %(prog)s data_final.csv --method regression -y salary -x age education
              %(prog)s data_final.csv --method logistic -y is_pass -x age gender
              %(prog)s data_final.csv --method chi2 -y is_pass -x gender
              %(prog)s data_final.csv --method correlation
              %(prog)s data_final.csv --method describe
              %(prog)s data_final.csv --no-check
        """)
    )
    parser.add_argument("input", help="清洗后的 CSV 文件路径")
    parser.add_argument("--method", "-m", default=None,
                        help="统计方法: ttest/anova/regression/logistic/chi2/"
                             "correlation/describe/mannwhitney/kruskal")
    parser.add_argument("--target", "-y", default=None,
                        help="目标变量 (Y) 列名")
    parser.add_argument("--xvar", "-x", nargs="*", default=None,
                        help="自变量 (X) 列名, 用空格分隔")
    parser.add_argument("--no-check", action="store_true",
                        help="跳过假设前提检查")
    parser.add_argument("--output", "-o", default=None,
                        help="输出前缀 (默认: <输入名>_result)")
    parser.add_argument("--encoding", default="utf-8",
                        help="文件编码 (默认 utf-8)")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ 文件不存在: {args.input}")
        sys.exit(1)

    prefix = args.output or os.path.splitext(args.input)[0] + "_result"

    # 读取数据
    df = pd.read_csv(args.input, encoding=args.encoding)
    print(f"📖 已加载: {args.input} ({df.shape[0]} 行 × {df.shape[1]} 列)")
    type_map = build_type_map(df)

    # 确定 Y
    y_col = args.target
    if not y_col:
        y_col = _guess_y(df, type_map)
        if y_col:
            print(f"🎯 自动猜测 Y = '{y_col}' ({type_map.get(y_col, '?')})")

    # 确定 X
    x_vars = args.xvar
    if not x_vars and y_col:
        x_vars = [c for c in df.columns if c != y_col]

    # 确定方法
    method = args.method
    if method:
        method = resolve_method(method)
        if not method:
            print(f"❌ 未知方法 '{args.method}', 可选: {', '.join(METHOD_MAP.keys())}")
            sys.exit(1)
    elif y_col and x_vars:
        method, _ = auto_detect_method(df, type_map, y_col, x_vars)
        print(f"🎯 自动选择方法: {method}")
    else:
        print("❌ 无法确定分析方法. 请指定 --method 或 --target")
        sys.exit(1)

    # 执行
    if method == "describe":
        result = _describe(df, type_map, y_col or "", x_vars or [])
    elif method == "ttest":
        if not y_col or not x_vars:
            print("❌ t 检验需要指定 -y 和 -x")
            sys.exit(1)
        result = _ttest(df, y_col, x_vars[0], do_check=not args.no_check)
    elif method == "mannwhitney":
        if not y_col or not x_vars:
            print("❌ Mann-Whitney 需要指定 -y 和 -x")
            sys.exit(1)
        result = _mannwhitney(df, y_col, x_vars[0])
    elif method == "anova":
        if not y_col or not x_vars:
            print("❌ ANOVA 需要指定 -y 和 -x")
            sys.exit(1)
        result = _anova(df, y_col, x_vars[0], do_check=not args.no_check)
    elif method == "kruskal":
        if not y_col or not x_vars:
            print("❌ Kruskal-Wallis 需要指定 -y 和 -x")
            sys.exit(1)
        result = _kruskal(df, y_col, x_vars[0])
    elif method == "regression":
        if not y_col or not x_vars:
            print("❌ 回归需要指定 -y 和 -x")
            sys.exit(1)
        result = _linear_regression(df, y_col, x_vars, type_map,
                                     do_check=not args.no_check)
    elif method == "logistic":
        if not y_col or not x_vars:
            print("❌ 逻辑回归需要指定 -y 和 -x")
            sys.exit(1)
        result = _logistic(df, y_col, x_vars, type_map)
    elif method == "chi2":
        if not y_col or not x_vars:
            print("❌ 卡方检验需要指定 -y 和 -x")
            sys.exit(1)
        result = _chi2(df, y_col, x_vars[0])
    elif method == "correlation":
        result = _correlation(df, y_col, x_vars)
    else:
        print(f"❌ 未知方法: {method}")
        sys.exit(1)

    # 输出
    print_console(result)
    write_json(result, prefix + ".json")
    write_md(result, prefix + "_summary.md")

    return result


if __name__ == "__main__":
    main()
