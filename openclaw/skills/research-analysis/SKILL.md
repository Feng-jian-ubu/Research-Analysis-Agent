---
name: research-analysis
description: 科研数据 CSV/XLS/XLSX → 分析报告 → 交互式图表;当用户说"分析这个数据集""帮我分析一下结果""出一份数据报告""统计数据""画图""可视化""图表""plot""figure"等时使用。
---

# research-analysis — 科研数据清洗与分析报告

## 作用

接收用户提供的 CSV / XLS / XLSX 数据文件，经过加载识别 → 清洗 → 统计分析，输出一份结构化的科研数据分析报告。

## 工作流

### ① dataloader.py — 加载 & 变量类型识别

```bash
python3 dataloader.py <输入文件> [输出CSV]
```

- 支持 `.csv`、`.xlsx` 文件
- 自动识别每列类型：**numeric**（数值型）、**categorical**（分类型）、**datetime**（日期型）
- 输出为统一 CSV 格式
- 打印变量类型报告（含数据类型、唯一值数、缺失数、值示例）

**判定规则:**
| 特征 | 结果 |
|------|------|
| 连续浮点数/整数，唯一值多 | numeric |
| 仅 2 个值（0/1, M/F） | categorical |
| 少量离散值（≤10 唯一值） | categorical |
| datetime 类型 | datetime |

### ② datacleaner.py — 数据清洗

```bash
python3 datacleaner.py <输入CSV> [输出CSV]
```

- **数值列清洗**: 去空格、全角数字→半角、非数值置空
- **分类型列清洗**: 去空格、全角→半角、空字符串转 NaN
- **IQR 异常值检测**: 标记但不修改（系数可调，默认 1.5）
- **重复行检测**: 完全重复的行标记但不删除
- **缺失值统计报告**
- 所有异常逐条输出到 `anomalies.csv`
- **二次矫正**: 分类列中如果 ≥70% 的值可转数字，自动重判为数值型

### ③ methodselector.py — 统计方法自动推荐

```bash
python3 scripts/methodselector.py <清洗后的CSV> [选项]
```

自动分析数据结构并推荐统计方法。支持两种模式：

**模式 A — 用户指定目标变量 Y:**

| Y 类型 | X 情况 | 推荐方法 |
|--------|--------|---------|
| 连续 | 1 个二分类 X | **独立样本 t 检验** |
| 连续 | 1 个多分类 X (≥3 组) | **单因素 ANOVA** |
| 连续 | 1 个连续 X | **简单线性回归** |
| 连续 | 多个混合 X | **多元线性回归** |
| 二分类 | 任意 X | **逻辑回归** |
| 多分类 | 任意 X | **随机森林分类** |

**模式 B — 未指定 Y（自动猜测）:**
- 优先选最后一列、二分类列、含 target/score/label 关键词的列
- 全部数值 → 相关性矩阵 + PCA
- 全部分类 → 卡方检验 + 对应分析
- 混合类型 → 探索性分析

**假设前提自动检查（默认开启，`--no-check` 跳过）:**
- 正态性：Shapiro-Wilk 检验（分组时逐组检查）
- 方差齐性：Levene 检验
- 样本量评估：n<10 / n<30 / n<100 各档建议
- 不满足时自动推荐非参数替代方案（Mann-Whitney / Kruskal-Wallis / Spearman）

```bash
example:
  python3 scripts/methodselector.py data_final.csv                          # 自动猜测 Y
  python3 scripts/methodselector.py data_final.csv -y score                 # 指定 Y
  python3 scripts/methodselector.py data_final.csv -y score -x gender age   # 指定 X
  python3 scripts/methodselector.py data_final.csv -y score --full           # 显示完整 Python 代码
  python3 scripts/methodselector.py data_final.csv --no-check                # 跳过假设检查
```

### ④ resourceselector.py — 运算资源选择器（新增）

```bash
python3 scripts/resourceselector.py <清洗后的CSV> [选项]
```

在 `methodselector.py` 之后运行，读取数据文件元信息 + 方法推荐结果，
自动判断分析应在**本地**还是**HPC（交大鲲鹏集群）** 上执行。

**决策维度：**

| 维度 | HPC 条件 | 本地条件 |
|------|---------|---------|
| 数据行数 | > 50,000 行 | ≤ 50,000 行 |
| 文件大小 | > 100 MB | ≤ 100 MB |
| 推荐方法 | 随机森林 / XGBoost / SVM / 深度学习 | t 检验 / ANOVA / 回归 / 描述统计 |
| 特征数 | > 20 个 X 变量 | ≤ 20 个 X 变量 |
| 分类变量类别 | 某列类别 > 50 | 所有列类别 ≤ 50 |

输出决策文件 `resource_decision.json`，下游据其分叉：

```bash
# 自动模式（读取数据 + 自动检测 Y 和方法）
python3 scripts/resourceselector.py data_final.csv

# 指定 Y / 方法
python3 scripts/resourceselector.py data_final.csv -y score -x age gender -m regression
```

### ⑤-⑥ 运算分叉

```
resourceselector.py
        ↓
├── 本地路径 ────→ statisticsexecutor.py → figuregenerator.py
└── HPC 路径 ────→ hpcsubmit.py（上传 → 执行 → 下载）
        ↓
     reportgenerator.py（统一合并）
```

### ⑤ (本地路径) statisticsexecutor.py — 统计方法执行 & 报告生成

> 注意：当 resourceselector 判定为 `local` 时走此路径。

```bash
python3 scripts/statisticsexecutor.py <清洗后的CSV> [选项]
```

根据 methodselector 的推荐或手动指定方法，执行统计分析并输出完整结果。

**模式 A — 自动模式（无需指定方法）:**

```bash
python3 scripts/statisticsexecutor.py data_final.csv
```

内部自动调用 methodselector 的逻辑选择方法，一步出结果。

**模式 B — 手动指定方法:**

```bash
python3 scripts/statisticsexecutor.py data_final.csv -m ttest -y score -x gender
python3 scripts/statisticsexecutor.py data_final.csv -m anova -y salary -x education
python3 scripts/statisticsexecutor.py data_final.csv -m regression -y score -x age gender
python3 scripts/statisticsexecutor.py data_final.csv -m logistic -y is_pass -x age
python3 scripts/statisticsexecutor.py data_final.csv -m chi2 -y is_pass -x gender
python3 scripts/statisticsexecutor.py data_final.csv -m correlation
python3 scripts/statisticsexecutor.py data_final.csv -m describe
```

**支持的方法及输出内容:**

| 方法 | 参数 | 报告内容 |
|------|------|--------|
| `ttest` | -y连续 -x二分类 | 均值±标准差, t值, p值, Cohen's d + 95%CI, 假设检查 |
| `mannwhitney` | -y连续 -x二分类 | U值, 中位数, 秩双列相关系数 |
| `anova` | -y连续 -x多分类 | 均值±标准差, F值, p值, η², 假设检查, 自动 Welch 校正 |
| `kruskal` | -y连续 -x多分类 | H值, 中位数, ε² |
| `regression` | -y连续 -x任意 | R², adj.R², F检验, 系数表, 残差正态性检查 |
| `logistic` | -y二分类 -x任意 | 准确率, AUC-ROC, 系数+OR值 |
| `chi2` | -y分类 -x分类 | χ², 期望频数, Cramér's V |
| `correlation` | (全部数值) | Pearson r 矩阵, 带 p 值, 最强相关 Top10 |
| `describe` | (全部) | 描述统计: 均值/中位数/分位数/CI/频数 |

**输出文件 (默认 `<输入名>_result`):**

| 文件 | 格式 | 内容 |
|------|------|------|
| `<前缀>.json` | JSON | 结构化计算结果（可供程序读取） |
| `<前缀>_summary.md` | Markdown | 可读分析报告 |

**假设前提自动检查（`--no-check` 跳过）:**
- 正态性: Shapiro-Wilk
- 方差齐性: Levene
- 不满足时自动推荐或应用备选（Welch t-test / Kruskal-Wallis）

**效应量报告:**
| 方法 | 效应量 | 阈值解释 |
|------|--------|---------|
| t 检验 | Cohen's d + 95% Bootstrap CI | 0.2小 / 0.5中 / 0.8大 |
| ANOVA | η² (eta-squared) | 0.01小 / 0.06中 / 0.14大 |
| 回归 | R² / adj. R² | — |
| 逻辑回归 | AUC-ROC | >0.7良好 / >0.8优秀 |
| 卡方 | Cramér's V | 0.1小 / 0.3中 / 0.5大 |
| Mann-Whitney | 秩双列 r | 0.1小 / 0.3中 / 0.5大 |

## 报告结构

输出一份结构化的分析报告，包含以下章节：

### 1. 数据集概览
- 行数、列数
- 变量类型分布（数值型 x 列、分类型 x 列、日期型 x 列）
- 缺失值汇总表（列名 | 缺失数 | 缺失率）

### 2. 数值型变量分析
每个数值变量输出：
- 基本统计量: 均值、中位数、标准差、最小值、最大值、四分位数
- 缺失数和缺失率
- 异常值标记（IQR 方法，含异常值数量和占比）
- 分布形态描述（偏度、峰度）

### 3. 分类型变量分析
每个分类变量输出：
- 类别数量（唯一值数）
- 频数统计表（类别 | 频数 | 占比）
- 缺失数和缺失率

### 4. 相关性分析（可选/按需）
- 数值变量之间的 Pearson 相关系数矩阵
- 给出前 N 条最强的相关性（正/负）

### 5. 综合结论
- 数据质量评估
- 建议后续分析方向（回归、分类、聚类等）
- 异常值和缺失值处理建议

## 相关文件

| 文件 | 路径 |
|------|------|
| 数据加载器 | `scripts/dataloader.py` |
| 数据清洗器 | `scripts/datacleaner.py` |
| 方法推荐器 | `scripts/methodselector.py` |
| 资源选择器 | `scripts/resourceselector.py` |
| 决策输出 | `resource_decision.json` |
| 方法执行器 | `scripts/statisticsexecutor.py` |
| HPC 提交器 | `scripts/hpcsubmit.py` |
| 输出 CSV | `<输入名>_final.csv` |
| 异常日志 | `anomalies.csv` |
| 图表生成器 | `scripts/figuregenerator.py` |
| 图表输出目录 | `figures/` |
| 报告生成器 | `scripts/reportgenerator.py` |
| 报告输出目录 | `reports/` |

### ⑤ figuregenerator.py — 交互式图表生成

```bash
python3 scripts/figuregenerator.py <数据CSV> <results.json> [选项]
```

读取 `statisticsexecutor.py` 的输出 (`results.json`) 和原始数据 CSV 文件，
根据统计方法自动推荐图表类型，用 Plotly 生成**交互式 HTML 图表**
（悬停显示数值、滚轮缩放、平移、图例开关）。

**自动推荐规则：**

| 统计方法 | 自动推荐图表 |
|---------|------------|
| t 检验 / Mann-Whitney | `box` — 箱线图 + 散点叠加 |
| ANOVA / Kruskal-Wallis | `box` — 箱线图 |
| 线性回归 | `scatter_reg` — 散点图 + 回归线 + 95% 置信区间 |
| 多元回归 | `residual` — 残差诊断图 (残差 vs 拟合值 + 直方图) |
| 逻辑回归 | `roc` — ROC 曲线 |
| 相关性分析 | `heatmap` — 相关性热力图 |
| 卡方检验 | `bar_grouped` — 堆积柱状图 |
| 描述统计 | `histogram` — 直方图 + KDE 密度曲线 |

**三种使用模式：**

```bash
# ① 自动推荐 (根据 results.json 里的方法自动判断)
python3 scripts/figuregenerator.py data_final.csv result.json

# ② 指定类型
python3 scripts/figuregenerator.py data_final.csv result.json -t box
python3 scripts/figuregenerator.py data_final.csv result.json -t violin
python3 scripts/figuregenerator.py data_final.csv result.json -t heatmap
python3 scripts/figuregenerator.py data_final.csv result.json -t scatter_reg
python3 scripts/figuregenerator.py data_final.csv result.json -t residual
python3 scripts/figuregenerator.py data_final.csv result.json -t roc
python3 scripts/figuregenerator.py data_final.csv result.json -t histogram
python3 scripts/figuregenerator.py data_final.csv result.json -t qq
python3 scripts/figuregenerator.py data_final.csv result.json -t bar_grouped
python3 scripts/figuregenerator.py data_final.csv result.json -t pie

# ③ 全部生成
python3 scripts/figuregenerator.py data_final.csv result.json -t all

# 自定义输出前缀
python3 scripts/figuregenerator.py data_final.csv result.json -t scatter_reg -o experiment
```

**输出文件：**

| 文件 | 说明 |
|------|------|
| `figures/<前缀>_<类型>.html` | 交互式 HTML 图表（浏览器打开即可交互） |

**支持的全部图表类型：** `scatter_reg`, `box`, `violin`, `bar_grouped`, `residual`, `qq`, `heatmap`, `roc`, `histogram`, `pie`

### ⑥ (HPC 路径) hpcsubmit.py — 超算分析提交器

> 注意：当 `resourceselector` 判定为 `hpc` 时走此路径。

```bash
python3 scripts/hpcsubmit.py <数据CSV> <决策JSON>
```

全自动完成：**上传数据 + 上传脚本 → HPC 执行统计 → 下载结果**，输出与本地路径完全一致。

**工作流程：**

| 步骤 | 操作 |
|------|------|
| 1. 检查 | SSH 双跳测试 (pilogin → kplogin1)，Python 环境检查 |
| 2. 上传 | SCP 双跳上传数据 CSV + `statisticsexecutor.py` + `figuregenerator.py` |
| 3. 执行 | 在 kplogin1 上运行统计分析和图表生成 |
| 4. 下载 | SCP 双跳下载 results.json、summary.md、figures/*.png、figures/*.html |

**输出文件对齐（与本地路径完全一致）：**

| 文件 | 本地产生者 | HPC 产生者 |
|------|-----------|------------|
| `*_result.json` | statisticsexecutor.py | hpcsubmit.py (下载回来) |
| `*_summary.md` | statisticsexecutor.py | hpcsubmit.py (下载回来) |
| `figures/*.png` | figuregenerator.py | hpcsubmit.py (下载回来) |
| `figures/*.html` | figuregenerator.py | hpcsubmit.py (下载回来) |

```bash
# 用法示例
python3 scripts/hpcsubmit.py experiment_data_final.csv resource_decision.json
```

凭据来源（优先级）：
1. 环境变量 `HPC_USER` / `HPC_PASS`
2. `~/login_info_vpn.txt`（格式: `username:stu2188` / `passwd:ym56aPnEeT`）
3. 硬编码默认值

### ⑦ reportgenerator.py — 数据分析报告生成（学术风格）

读取 `statisticsexecutor.py` 的输出 (`results.json`) 和 `figuregenerator.py` 生成的图表，
输出一份完整的 Markdown 格式数据分析报告，包含：
- **人话解释**：p 值意义、效应量评价、模型拟合效果评估
- **嵌入 PNG 截图** + 交互式 HTML 链接
- **结构化 HTML 注释元数据**（便于后处理）
- **多 results.json 合并**：支持同时传入多个结果，合成为一份报告

```bash
python3 scripts/reportgenerator.py <results.json>... [选项]
```

**使用示例：**

```bash
# 单个结果
python3 scripts/reportgenerator.py result.json --data data_final.csv -o report

# 多个结果合并
python3 scripts/reportgenerator.py result1.json result2.json --data data_final.csv -o combined_report

# 自动发现图表（自动匹配 figures/ 下的 PNG 和 HTML）
python3 scripts/reportgenerator.py result.json --data data_final.csv \
    --figure-prefix data_final_figure -o report_with_figures

# 手动指定图表文件
python3 scripts/reportgenerator.py result.json --data data_final.csv \
    --figures "figures/exp_box.png" "figures/exp_box.html" -o report
```

**报告结构：**

| 章节 | 内容 |
|------|------|
| 摘要 | 一句话核心结论 |
| 1. 数据与方法 | 样本量、变量、方法、假设前提检验 |
| 2. 统计结果 | 人话解释 + 检验统计量 + 效应量 + 嵌入图表 |
| 3. 讨论 | 结果解读、样本量评估、局限性 |
| 4. 结论 | 综合结论 |
| 附录 | 完整 JSON 统计值明细 |

**输出文件：**

| 文件 | 说明 |
|------|------|
| `reports/<前缀>.md` | Markdown 报告（含 PNG 截图 + HTML 链接 + 元数据注释） |

## 完整流水线

### 新版流水线（带资源选择分叉）

```bash
# 从原始数据到最终报告，自动判断本地 / HPC
cd skills/research-analysis/scripts

# Step 1: 数据加载
python3 dataloader.py ../../experiment_data.xlsx

# Step 2: 数据清洗
python3 datacleaner.py experiment_data_cleaned.csv

# Step 3: 方法推荐（可选，methodselector 和 resourceselector 各自会做方法检测）
# python3 methodselector.py experiment_data_final.csv -y score

# Step 4: 资源选择 — 判断用本地还是 HPC
python3 resourceselector.py experiment_data_final.csv -y score -x age -m regression
# → 输出 resource_decision.json

# Step 5: 根据 decision 分叉
#   若 recommendation = local：
python3 statisticsexecutor.py experiment_data_final.csv -m regression -y score -x age
python3 figuregenerator.py experiment_data_final.csv experiment_data_final_result.json --png -t all

#   若 recommendation = hpc：
python3 hpcsubmit.py experiment_data_final.csv resource_decision.json

# Step 6: 报告生成（合并路径，无差别消费）
python3 reportgenerator.py experiment_data_final_result.json \
    --data experiment_data_final.csv \
    --figure-prefix experiment_data_final_figure \
    -o final_report
```

### 原版流水线（不经过 resourceselector / hpcsubmit，纯本地）

## 使用示例

```bash
# 完整流水线
cd scripts
python3 dataloader.py ../experiment_data.xlsx        # → ../experiment_data_cleaned.csv
python3 datacleaner.py ../experiment_data_cleaned.csv  # → ../experiment_data_final.csv + ../anomalies.csv

# 或从 skill 目录直接运行
cd ~/workspace
python3 skills/research-analysis/scripts/dataloader.py experiment_data.xlsx
python3 skills/research-analysis/scripts/datacleaner.py experiment_data_cleaned.csv

# 用户提供 CSV/XLSX 时，交给 AI 按以上两步处理并生成分析报告
```
