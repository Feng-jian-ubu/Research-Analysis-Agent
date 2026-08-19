#!/usr/bin/env python3
"""
figuregenerator.py — 科研数据交互式图表生成器

从 statisticsexecutor.py 的输出 (results.json) 和原始数据 (_final.csv) 读取结果，
根据统计方法自动推荐或手动指定图表类型，用 Plotly 生成交互式 HTML 图表。

用法:
  # 自动推荐图表 (根据 results.json 中的方法判断)
  python3 figuregenerator.py data_final.csv results.json

  # 手动指定图表类型
  python3 figuregenerator.py data_final.csv results.json --type box
  python3 figuregenerator.py data_final.csv results.json --type scatter_reg
  python3 figuregenerator.py data_final.csv results.json --type heatmap
  python3 figuregenerator.py data_final.csv results.json --type roc

  # 指定输出
  python3 figuregenerator.py data_final.csv results.json -o my_chart
"""

import os
import sys
import json
import argparse
import math
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from scipy import stats as sp_stats

try:
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_curve, auc
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


# ===================================================================
# 路径配置
# ===================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
SKILL_DIR = SCRIPT_DIR.parent
FIGURES_DIR = SKILL_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


# ===================================================================
# 读取输入
# ===================================================================

def load_results(json_path: str) -> dict:
    """读取 statisticsexecutor.py 输出的 results.json."""
    if not os.path.exists(json_path):
        print(f"❌ 未找到 results.json: {json_path}")
        sys.exit(1)
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_data(csv_path: str) -> pd.DataFrame:
    """读取清洗后的 CSV 数据."""
    if not os.path.exists(csv_path):
        print(f"❌ 未找到数据文件: {csv_path}")
        sys.exit(1)
    return pd.read_csv(csv_path, encoding="utf-8")


# ===================================================================
# 自动推荐图表类型
# ===================================================================

TYPES_AVAILABLE = [
    "scatter_reg", "box", "violin", "bar_grouped", "residual",
    "qq", "heatmap", "roc", "histogram", "pie",
]

def auto_recommend(results: dict) -> str:
    """根据统计方法自动推荐最佳图表类型."""
    method = results.get("method", "").lower()

    if "t检验" in method or "mann-whitney" in method:
        return "box"
    if "anova" in method or "kruskal" in method or "welch" in method:
        return "box"
    if "线性回归" in method or method == "线性回归":
        return "scatter_reg"
    if "逻辑回归" in method or "logistic" in method:
        return "roc"
    if "相关" in method or "correlation" in method:
        return "heatmap"
    if "卡方" in method or "chi2" in method or "chisq" in method:
        return "bar_grouped"
    if "描述统计" in method or "describe" in method:
        return "histogram"

    # 从数据特征推断
    y_col = results.get("y_col", "")
    x_vars = results.get("x_vars", [])
    stat = results.get("statistics", {})
    effect = results.get("effect_size", {})

    if "auc_roc" in effect or "auc" in stat:
        return "roc"
    if "R_squared" in stat or "adjusted_R_squared" in stat:
        return "scatter_reg"
    if "matrix" in stat or "pairs" in stat:
        return "heatmap"
    if "F_statistic" in stat:
        return "box"
    if "t_statistic" in stat:
        return "box"
    if y_col and x_vars:
        return "box"

    return "histogram"


# ===================================================================
# 图表构建
# ===================================================================

def _build_annotation(results: dict, x: float = 0.02, y: float = 0.98) -> list:
    """从 results.json 构建统计标注."""
    texts = []
    p_val = results.get("p_value")
    if p_val is not None:
        sig = "显著" if p_val < 0.05 else "不显著"
        texts.append(f"p = {p_val:.4f} ({sig})")

    effect = results.get("effect_size", {})
    for k, v in effect.items():
        if k == "interpretation":
            texts.append(f"效应强度: {v}")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            texts.append(f"{k} = {v:.4f}")

    if not texts:
        return []

    return [
        dict(
            xref="paper", yref="paper",
            x=x, y=y,
            text="<br>".join(texts),
            showarrow=False,
            font=dict(size=12),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#ccc",
            borderwidth=1,
            align="left",
        )
    ]


def _find_cat_x(df: pd.DataFrame, x_vars: list) -> Optional[str]:
    """从 x_vars 中找第一个分类变量."""
    for c in x_vars:
        if c in df.columns and df[c].nunique() <= 30:
            return c
    return None


def _find_num_x(df: pd.DataFrame, x_vars: list) -> list:
    """找 x_vars 中的连续数值变量."""
    return [c for c in x_vars if c in df.columns
            and pd.api.types.is_numeric_dtype(df[c])
            and df[c].nunique() > 10]


def make_scatter_reg(df: pd.DataFrame, results: dict,
                     y_col: str, x_vars: list) -> go.Figure:
    """
    散点图 + 回归线 + 95% 置信区间。
    主要用于简单线性回归（1个连续X）。
    """
    if not y_col or not x_vars:
        fig = go.Figure()
        fig.update_layout(title="无法绘图: 缺少变量信息")
        return fig

    numeric_x = _find_num_x(df, x_vars)
    if not numeric_x:
        return make_box(df, results, y_col, x_vars)

    x_col = numeric_x[0]
    clean = df[[x_col, y_col]].dropna()
    if len(clean) < 5:
        return make_box(df, results, y_col, x_vars)

    x, y = clean[x_col].values, clean[y_col].values
    fig = go.Figure()

    # 绘制散点
    fig.add_trace(go.Scatter(
        x=x, y=y,
        mode="markers",
        name="数据点",
        marker=dict(color="#4C72B0", size=6, opacity=0.65),
        hovertemplate=f"{x_col}=%{{x}}<br>{y_col}=%{{y}}<extra></extra>"
    ))

    # 分类变量分组着色
    cat_cols = [c for c in x_vars if c in df.columns and c not in numeric_x
                and df[c].nunique() <= 10]
    if cat_cols:
        cat_col = cat_cols[0]
        colors = px.colors.qualitative.Plotly
        for i, (grp, sub) in enumerate(df.groupby(cat_col, observed=True)):
            sd = sub.dropna(subset=[x_col, y_col])
            if len(sd) < 2:
                continue
            fig.add_trace(go.Scatter(
                x=sd[x_col], y=sd[y_col],
                mode="markers",
                name=str(grp),
                marker=dict(color=colors[i % len(colors)], size=5, opacity=0.5),
                hovertemplate=f"{cat_col}={grp}<br>{x_col}=%{{x}}<br>{y_col}=%{{y}}<extra></extra>"
            ))
        fig.update_layout(showlegend=True)

    # 回归线 + 置信区间
    n = len(x)
    A = np.vstack([x, np.ones(n)]).T
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    r_val = float(np.corrcoef(x, y)[0, 1])

    x_sorted = np.sort(x)
    y_pred = slope * x_sorted + intercept

    # 置信区间 (95%)
    if n >= 5:
        y_fitted = slope * x + intercept
        sse = float(np.sum((y - y_fitted) ** 2))
        mse = sse / (n - 2) if n > 2 else 0
        x_mean = float(x.mean())
        se_fit = np.sqrt(mse * (1.0 / n + (x_sorted - x_mean) ** 2 / np.sum((x - x_mean) ** 2)))
        t_val = sp_stats.t.ppf(0.975, n - 2)
        ci_upper = y_pred + t_val * se_fit
        ci_lower = y_pred - t_val * se_fit

        fig.add_trace(go.Scatter(
            x=np.concatenate([x_sorted, x_sorted[::-1]]),
            y=np.concatenate([ci_upper, ci_lower[::-1]]),
            fill="toself",
            fillcolor="rgba(76, 114, 176, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="95% 置信区间",
            showlegend=True,
            hoverinfo="skip",
        ))

    fig.add_trace(go.Scatter(
        x=x_sorted, y=y_pred,
        mode="lines",
        name=f"回归线 (r={r_val:.3f})",
        line=dict(color="#C44E52", width=2.5),
        hovertemplate=f"预测{y_col}=%{{y:.2f}}<extra></extra>"
    ))

    r2 = r_val ** 2
    fig.update_layout(
        title=f"{y_col} vs {x_col} — 散点图与回归线",
        xaxis_title=x_col,
        yaxis_title=y_col,
        template="plotly_white",
        hovermode="closest",
        annotations=[
            dict(
                xref="paper", yref="paper",
                x=0.02, y=0.98,
                text=f"r = {r_val:.4f}<br>R² = {r2:.4f}",
                showarrow=False,
                font=dict(size=12),
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="#ccc",
                borderwidth=1,
            )
        ],
    )
    return fig


def make_box(df: pd.DataFrame, results: dict,
             y_col: str, x_vars: list) -> go.Figure:
    """箱线图 (+ 散点抖动叠加)，适用于 t 检验 / ANOVA / Mann-Whitney."""
    if not y_col:
        fig = go.Figure()
        fig.update_layout(title="无法绘图: 缺少目标变量")
        return fig

    x_col = _find_cat_x(df, x_vars)

    if x_col is None:
        # 单变量箱线图
        vals = df[y_col].dropna()
        fig = go.Figure()
        fig.add_trace(go.Box(
            y=vals, name=y_col, boxmean="sd",
            marker_color="#4C72B0",
            hovertemplate=f"{y_col}=%{{y}}<extra></extra>"
        ))
        fig.update_layout(
            title=f"{y_col} 箱线图",
            yaxis_title=y_col, template="plotly_white",
        )
        return fig

    clean = df[[x_col, y_col]].dropna()
    fig = go.Figure()
    colors = px.colors.qualitative.Plotly

    for i, (grp_name, grp_data) in enumerate(clean.groupby(x_col, observed=True)):
        vals = grp_data[y_col]
        if len(vals) < 2:
            continue
        grp_str = str(grp_name)
        ci = colors[i % len(colors)]

        fig.add_trace(go.Box(
            y=vals, name=grp_str,
            boxmean="sd",
            marker_color=ci,
            line=dict(width=1.5),
            boxpoints=False,
            hovertemplate=f"{x_col}={grp_str}<br>{y_col}=%{{y}}<extra></extra>",
        ))

        # 叠加散点 (抖动)
        np.random.seed(42)
        jitter = np.random.uniform(-0.15, 0.15, len(vals))
        fig.add_trace(go.Scatter(
            x=[i] * len(vals) + jitter,
            y=vals,
            mode="markers",
            marker=dict(color=ci, size=5, opacity=0.5,
                        line=dict(color="rgba(0,0,0,0.2)", width=1)),
            showlegend=False,
            hovertemplate=f"{x_col}={grp_str}<br>{y_col}=%{{y}}<extra></extra>",
        ))
        i += 1

    fig.update_layout(
        title=f"{x_col} vs {y_col} — 分组箱线图",
        xaxis_title=x_col,
        yaxis_title=y_col,
        template="plotly_white",
        showlegend=False,
        hovermode="closest",
        annotations=_build_annotation(results),
    )
    return fig


def make_violin(df: pd.DataFrame, results: dict,
                y_col: str, x_vars: list) -> go.Figure:
    """小提琴图，适用于 t 检验 / ANOVA."""
    if not y_col:
        fig = go.Figure()
        fig.update_layout(title="无法绘图: 缺少目标变量")
        return fig

    x_col = _find_cat_x(df, x_vars)

    fig = go.Figure()
    if x_col is None:
        vals = df[y_col].dropna()
        fig.add_trace(go.Violin(
            y=vals, name=y_col,
            box_visible=True, meanline_visible=True,
            points="all", pointpos=-0.3, jitter=0.1,
            marker_color="#4C72B0",
        ))
    else:
        for grp_name, grp_data in df.groupby(x_col, observed=True):
            vals = grp_data[y_col].dropna()
            if len(vals) < 2:
                continue
            fig.add_trace(go.Violin(
                y=vals, name=str(grp_name),
                box_visible=True, meanline_visible=True,
                points="all", pointpos=-0.3, jitter=0.1,
                scalemode="width",
                hovertemplate=f"{x_col}={grp_name}<br>{y_col}=%{{y}}<extra></extra>",
            ))

    fig.update_layout(
        title=f"{x_col or y_col} 小提琴图",
        xaxis_title=x_col or "",
        yaxis_title=y_col,
        template="plotly_white",
        violinmode="group" if x_col else None,
        annotations=_build_annotation(results),
    )
    return fig


def make_bar_grouped(df: pd.DataFrame, results: dict,
                     y_col: str, x_vars: list) -> go.Figure:
    """分组柱状图 (+ 误差线)，适用于 ANOVA；或堆积柱状图用于卡方."""
    if not y_col:
        return make_histogram(df, results)

    x_col = x_vars[0] if x_vars else None
    if x_col is None or x_col not in df.columns:
        return make_histogram(df, results)

    # 如果 y 是分类 → 堆积柱状图（列联表）
    if not pd.api.types.is_numeric_dtype(df[y_col]):
        ct = pd.crosstab(df[x_col], df[y_col])
        fig = go.Figure()
        for col_name in ct.columns:
            fig.add_trace(go.Bar(
                name=str(col_name),
                x=ct.index.astype(str),
                y=ct[col_name],
                hovertemplate=f"{x_col}=%{{x}}<br>{y_col}={col_name}<br>频数=%{{y}}<extra></extra>",
            ))
        fig.update_layout(
            title=f"{x_col} vs {y_col} — 堆积柱状图",
            xaxis_title=x_col, yaxis_title="频数",
            barmode="stack", template="plotly_white",
        )
        return fig

    # y 是数值 → 均值柱状图 + 标准误误差线
    clean = df[[x_col, y_col]].dropna()
    stats_df = clean.groupby(x_col, observed=True)[y_col].agg(["mean", "std", "count"])
    stats_df = stats_df.reset_index()
    stats_df.columns = [x_col, "mean", "std", "count"]
    stats_df["se"] = stats_df["std"] / np.sqrt(stats_df["count"])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=stats_df[x_col].astype(str),
        y=stats_df["mean"],
        error_y=dict(type="data", array=stats_df["se"], visible=True, thickness=1.5),
        marker_color="#4C72B0",
        marker_line=dict(width=1, color="#333"),
        hovertemplate=(
            f"{x_col}=%{{x}}<br>"
            f"均值=%{{y:.3f}}<br>"
            f"SD={stats_df['std'].iloc[0]:.3f}<br>"
            f"n={stats_df['count'].iloc[0]}"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title=f"{x_col} vs {y_col} — 均值柱状图 (误差线=标准误)",
        xaxis_title=x_col,
        yaxis_title=f"{y_col} 均值",
        template="plotly_white",
        annotations=_build_annotation(results),
    )
    return fig


def make_residual(df: pd.DataFrame, results: dict,
                  y_col: str, x_vars: list) -> go.Figure:
    """残差诊断图 (残差 vs 拟合值 + 残差直方图)."""
    if not HAS_SKLEARN:
        fig = go.Figure()
        fig.update_layout(title="需要 scikit-learn: pip install scikit-learn")
        return fig
    if not y_col or not x_vars:
        fig = go.Figure()
        fig.update_layout(title="无法绘制残差图: 缺少变量")
        return fig

    numeric_x = _find_num_x(df, x_vars)
    cat_x = [c for c in x_vars if c in df.columns and c not in numeric_x
             and df[c].nunique() <= 10]

    clean = df[x_vars + [y_col]].dropna()
    if len(clean) < 10:
        fig = go.Figure()
        fig.update_layout(title="样本量不足 (< 10)，无法绘制残差图")
        return fig

    X = clean[numeric_x].copy() if numeric_x else pd.DataFrame(index=clean.index)
    if cat_x:
        X = pd.concat([X, pd.get_dummies(clean[cat_x], drop_first=True)], axis=1)
    y = clean[y_col].values

    model = LinearRegression()
    model.fit(X, y)
    y_pred = model.predict(X)
    residuals = y - y_pred

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("残差 vs 拟合值", "残差分布直方图"))

    fig.add_trace(go.Scatter(
        x=y_pred, y=residuals,
        mode="markers",
        marker=dict(color="#4C72B0", size=6, opacity=0.6),
        hovertemplate="拟合值=%{x:.3f}<br>残差=%{y:.3f}<extra></extra>"
    ), row=1, col=1)
    fig.add_hline(y=0, line=dict(color="red", dash="dash", width=1.5), row=1, col=1)

    fig.update_xaxes(title_text="拟合值", row=1, col=1)
    fig.update_yaxes(title_text="残差", row=1, col=1)

    # 直方图
    nbins = min(30, max(5, len(residuals) // 5))
    fig.add_trace(go.Histogram(
        x=residuals, nbinsx=nbins,
        marker_color="#4C72B0", opacity=0.7,
        hovertemplate="残差=%{x:.3f}<br>频数=%{y}<extra></extra>"
    ), row=1, col=2)
    fig.update_xaxes(title_text="残差", row=1, col=2)
    fig.update_yaxes(title_text="频数", row=1, col=2)

    sw_p = sp_stats.shapiro(residuals[:5000])[1] if len(residuals) < 5000 else 0.5
    fig.update_layout(
        title=f"回归残差诊断 (Shapiro-Wilk p = {sw_p:.4f})",
        template="plotly_white", showlegend=False, height=450,
    )
    return fig


def make_qq(df: pd.DataFrame, results: dict,
            y_col: str, x_vars: list) -> go.Figure:
    """Q-Q 图 (残差正态性)."""
    if not HAS_SKLEARN:
        fig = go.Figure()
        fig.update_layout(title="需要 scikit-learn")
        return fig
    if not y_col or not x_vars:
        fig = go.Figure()
        fig.update_layout(title="无法绘制 Q-Q 图")
        return fig

    numeric_x = _find_num_x(df, x_vars)
    cat_x = [c for c in x_vars if c in df.columns and c not in numeric_x
             and df[c].nunique() <= 10]
    clean = df[x_vars + [y_col]].dropna()
    if len(clean) < 10:
        fig = go.Figure()
        fig.update_layout(title="样本量不足")
        return fig

    X = clean[numeric_x].copy() if numeric_x else pd.DataFrame(index=clean.index)
    if cat_x:
        X = pd.concat([X, pd.get_dummies(clean[cat_x], drop_first=True)], axis=1)
    y = clean[y_col].values
    model = LinearRegression()
    model.fit(X, y)
    residuals = y - model.predict(X)

    pp_result = sp_stats.probplot(residuals, dist="norm", plot=None)
    (osm, osr) = pp_result[0]
    slope, intercept = pp_result[1][0], pp_result[1][1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=osm, y=osr, mode="markers",
        marker=dict(color="#4C72B0", size=6, opacity=0.7),
        name="样本分位数",
        hovertemplate="理论分位数=%{x:.3f}<br>样本分位数=%{y:.3f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=osm, y=slope * osm + intercept, mode="lines",
        name="理论正态线",
        line=dict(color="#C44E52", width=2, dash="dash"),
    ))

    fig.update_layout(
        title="Q-Q 图 (残差正态性检验)",
        xaxis_title="理论分位数",
        yaxis_title="样本分位数",
        template="plotly_white", hovermode="closest",
    )
    return fig


def make_heatmap(df: pd.DataFrame, results: dict,
                 y_col: str, x_vars: list) -> go.Figure:
    """Pearson 相关性热力图."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) < 2:
        fig = go.Figure()
        fig.update_layout(title="数值变量不足 2 个，无法绘制热力图")
        return fig

    corr_mat = df[numeric_cols].corr()
    labels = [[f"{corr_mat.iloc[i, j]:.2f}"
               for j in range(len(corr_mat.columns))]
              for i in range(len(corr_mat.columns))]

    fig = go.Figure(data=go.Heatmap(
        z=corr_mat.values,
        x=corr_mat.columns,
        y=corr_mat.columns,
        text=labels,
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorscale="RdBu_r",
        zmin=-1, zmax=1,
        colorbar=dict(title="Pearson r"),
        hovertemplate="%{x} ↔ %{y}<br>r = %{z:.4f}<extra></extra>",
    ))

    fig.update_layout(
        title="Pearson 相关系数热力图",
        template="plotly_white",
        width=max(400, 40 * len(numeric_cols) + 100),
        height=max(400, 40 * len(numeric_cols) + 100),
        xaxis=dict(side="bottom", tickangle=-45),
    )
    return fig


def make_roc(df: pd.DataFrame, results: dict,
             y_col: str, x_vars: list) -> go.Figure:
    """ROC 曲线 (逻辑回归)."""
    if not HAS_SKLEARN:
        fig = go.Figure()
        fig.update_layout(title="需要 scikit-learn")
        return fig
    if not y_col or not x_vars:
        fig = go.Figure()
        fig.update_layout(title="无法绘制 ROC 曲线")
        return fig

    numeric_x = _find_num_x(df, x_vars)
    cat_x = [c for c in x_vars if c in df.columns and c not in numeric_x
             and df[c].nunique() <= 10]
    clean = df[x_vars + [y_col]].dropna()
    if len(clean) < 20 or clean[y_col].nunique() != 2:
        fig = go.Figure()
        fig.update_layout(title="样本量不足 (< 20) 或 Y 不是二分类")
        return fig

    X = clean[numeric_x].copy() if numeric_x else pd.DataFrame(index=clean.index)
    if cat_x:
        X = pd.concat([X, pd.get_dummies(clean[cat_x], drop_first=True)], axis=1)
    y = clean[y_col].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42)
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)
    y_score = model.predict_proba(X_test)[:, 1]
    fpr, tpr, _ = roc_curve(y_test, y_score)
    roc_auc = auc(fpr, tpr)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=fpr, y=tpr, mode="lines",
        name=f"ROC (AUC = {roc_auc:.3f})",
        line=dict(color="#4C72B0", width=2.5),
        hovertemplate="FPR=%{x:.3f}<br>TPR=%{y:.3f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode="lines",
        name="随机猜想 (AUC = 0.5)",
        line=dict(color="#aaa", width=1.5, dash="dash"),
    ))

    auc_text = results.get("effect_size", {}).get("interpretation", "")
    fig.update_layout(
        title=f"ROC 曲线 (AUC = {roc_auc:.3f})",
        xaxis_title="伪阳性率 (FPR)",
        yaxis_title="真阳性率 (TPR)",
        template="plotly_white",
        hovermode="closest",
        width=600, height=500,
        xaxis=dict(range=[-0.02, 1.02]),
        yaxis=dict(range=[-0.02, 1.02]),
    )
    if auc_text:
        fig.add_annotation(
            xref="paper", yref="paper",
            x=0.6, y=0.3,
            text=f"AUC 评价: {auc_text}",
            showarrow=False, font=dict(size=13),
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#ccc", borderwidth=1,
        )
    return fig


def make_histogram(df: pd.DataFrame, results: dict,
                   y_col: str = "", x_vars: list = None) -> go.Figure:
    """直方图 + KDE 曲线 (描述统计)."""
    x_vars = x_vars or []

    if y_col and y_col in df.columns and pd.api.types.is_numeric_dtype(df[y_col]):
        cols = [y_col]
    else:
        cols = df.select_dtypes(include=[np.number]).columns[:4].tolist()

    if not cols:
        cat_cols = [c for c in x_vars if c in df.columns] or \
                   df.select_dtypes(include=["object", "category"]).columns[:1].tolist()
        if cat_cols:
            return make_pie(df, cat_cols[0])
        fig = go.Figure()
        fig.update_layout(title="没有数值变量")
        return fig

    n = len(cols)
    fig = make_subplots(rows=n, cols=1,
                        subplot_titles=cols,
                        vertical_spacing=0.15 / max(1, n - 1))

    for i, col in enumerate(cols):
        vals = df[col].dropna()
        if len(vals) < 2:
            continue
        nbins = min(50, max(8, int(math.sqrt(len(vals)) * 2)))

        fig.add_trace(go.Histogram(
            x=vals, nbinsx=nbins,
            name=col, marker_color="#4C72B0",
            opacity=0.7, histnorm="probability density",
            hovertemplate=f"{col}=%{{x}}<br>密度=%{{y:.4f}}<extra></extra>",
        ), row=i + 1, col=1)

        # KDE 曲线
        kde_x = np.linspace(vals.min(), vals.max(), 200)
        kde = sp_stats.gaussian_kde(vals)(kde_x) if len(vals) >= 5 else np.zeros_like(kde_x)
        fig.add_trace(go.Scatter(
            x=kde_x, y=kde, mode="lines",
            name=f"{col} KDE",
            line=dict(color="#C44E52", width=2),
            showlegend=False,
        ), row=i + 1, col=1)

        fig.update_xaxes(title_text=col, row=i + 1, col=1)
        fig.update_yaxes(title_text="密度", row=i + 1, col=1)

    fig.update_layout(
        title="变量分布直方图",
        template="plotly_white",
        showlegend=False,
        height=250 * n,
    )
    return fig


def make_pie(df: pd.DataFrame, col: str) -> go.Figure:
    """饼图 (分类变量)."""
    freq = df[col].value_counts()
    fig = go.Figure(data=[go.Pie(
        labels=freq.index.astype(str),
        values=freq.values,
        textinfo="percent+label",
        hole=0.3,
        hovertemplate="%{label}<br>频数=%{value} (%{percent})<extra></extra>",
    )])
    fig.update_layout(
        title=f"{col} 分布饼图",
        template="plotly_white",
    )
    return fig


# ===================================================================
# 图表类型映射表
# ===================================================================

CHART_MAKERS = {
    "scatter_reg": ("散点图+回归线", make_scatter_reg),
    "box": ("分组箱线图", make_box),
    "violin": ("小提琴图", make_violin),
    "bar_grouped": ("分组柱状图", make_bar_grouped),
    "residual": ("残差诊断图", make_residual),
    "qq": ("Q-Q 图", make_qq),
    "heatmap": ("相关性热力图", make_heatmap),
    "roc": ("ROC 曲线", make_roc),
    "histogram": ("直方图+KDE", make_histogram),
    "pie": ("饼图", lambda df, r, y, x: make_pie(df, y or x[0]) if (y or x) else go.Figure()),
}

# ===================================================================
# 保存
# ===================================================================

def save_figure(fig: go.Figure, output_prefix: str, chart_type: str,
                save_png: bool = False):
    """保存为交互式 HTML 文件，可选同时输出 PNG 截图 (通过 Playwright)."""
    html_name = f"{output_prefix}_{chart_type}.html"
    html_path = FIGURES_DIR / html_name
    png_path = FIGURES_DIR / f"{output_prefix}_{chart_type}.png"

    fig.write_html(
        str(html_path),
        include_plotlyjs="cdn",
        full_html=True,
        config=dict(
            scrollZoom=True,
            displayModeBar=True,
            modeBarButtonsToRemove=["sendDataToCloud"],
        ),
    )
    print(f"  ✅ HTML: {html_path}")

    if save_png:
        try:
            from playwright.sync_api import sync_playwright
            chrome_path = os.path.expanduser(
                "~/.playwright/chromium-1234/chrome-linux/chrome")
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    executable_path=chrome_path,
                    args=["--headless=new", "--disable-gpu", "--no-sandbox",
                          "--disable-dev-shm-usage", "--single-process"]
                )
                page = browser.new_page(viewport={"width": 1000, "height": 700})
                page.goto(f"file://{html_path.resolve()}", wait_until="networkidle")
                page.wait_for_timeout(500)
                page.screenshot(path=str(png_path), full_page=False)
                browser.close()
            size = os.path.getsize(str(png_path))
            print(f"  ✅ PNG:  {png_path} ({size // 1024} KB)")
        except Exception as e:
            print(f"  ⚠️ PNG 导出失败: {e}")

    return {"html": str(html_path), "png": str(png_path) if save_png else None}


# ===================================================================
# CLI 入口
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="🧪 FigureGenerator — 科研数据交互式图表生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            使用示例:
              %(prog)s data_final.csv results.json
              %(prog)s data_final.csv results.json --type box
              %(prog)s data_final.csv results.json --type heatmap
              %(prog)s data_final.csv results.json --type roc
              %(prog)s data_final.csv results.json --type scatter_reg -o experiment
              %(prog)s data_final.csv results.json --type residual
              %(prog)s data_final.csv results.json --type all
        """))
    parser.add_argument("data_csv", help="清洗后的原始数据 CSV 文件 (_final.csv)")
    parser.add_argument("results_json", help="statisticsexecutor.py 输出的 results.json")
    parser.add_argument("--type", "-t", default="auto",
                        help=f"图表类型: auto/{'/'.join(TYPES_AVAILABLE)}/all")
    parser.add_argument("--output", "-o", default=None,
                        help="输出文件名前缀 (默认: <data_csv>_figure)")
    parser.add_argument("--png", action="store_true",
                        help="同时导出 PNG 静态截图")

    args = parser.parse_args()

    # 加载数据
    df = load_data(args.data_csv)
    results = load_results(args.results_json)

    y_col = results.get("y_col", "")
    x_vars = results.get("x_vars", [])
    method = results.get("method", "")
    output_prefix = args.output or os.path.splitext(os.path.basename(args.data_csv))[0] + "_figure"

    # 确定图表类型
    chart_type = args.type.lower()
    if chart_type == "auto":
        chart_type = auto_recommend(results)
        print(f"🎯 自动推荐图表类型: {chart_type} ({CHART_MAKERS.get(chart_type, ['未知'])[0]})")

    if chart_type == "all":
        # 输出所有适用的图表
        print(f"📊 统计方法: {method}")
        print(f"📋 目标变量: {y_col}")
        print(f"📋 自变量: {x_vars}")
        print(f"📊 样本量: {results.get('sample_size', {})}")
        generated = []
        for ct in TYPES_AVAILABLE:
            try:
                maker_fn = CHART_MAKERS[ct][1]
                fig = maker_fn(df, results, y_col, x_vars)
                path = save_figure(fig, output_prefix, ct, save_png=args.png)
                generated.append(str(path))
            except Exception as e:
                print(f"  ⚠️ {ct}: {e}")
        print(f"\n✅ 共生成 {len(generated)} 个图表")
        return

    if chart_type not in CHART_MAKERS:
        print(f"❌ 未知图表类型 '{chart_type}'. 可用: {', '.join(TYPES_AVAILABLE)}")
        sys.exit(1)

    # 生成单个图表
    maker_fn = CHART_MAKERS[chart_type][1]
    chart_name = CHART_MAKERS[chart_type][0]
    print(f"🎨 正在绘制: {chart_name} ({chart_type})")
    print(f"   📊 方法: {method}")
    print(f"   🎯 Y: {y_col}")
    print(f"   📋 X: {', '.join(x_vars)}")

    fig = maker_fn(df, results, y_col, x_vars)
    paths = save_figure(fig, output_prefix, chart_type, save_png=args.png)
    html_path = paths.get("html", "")
    png_path = paths.get("png")
    print(f"\n✅ 已生成: {html_path}")
    if png_path:
        print(f"   🖼️ PNG:  {png_path}")
    print(f"💡 在浏览器中打开即可交互操作 (悬停/缩放/平移)")


if __name__ == "__main__":
    main()