# Research Analysis Agent Skill 输入输出规范（第二版）

## 1. 文档目的

本文档规定第二版 Research Analysis Agent 中各 Skill 脚本的职责、输入参数和输出结构，作为 Agent 调用、后端开发和测试的统一依据。

第二版采用简化设计：默认输入合法、文件可正常读取、统计计算可正常完成，因此各 Skill 只返回实际业务结果，不设计 `status`、`warnings`、`error` 等字段。

---

## 2. 第二版 Skill 范围

```text
skills/
├── data/
│   ├── __init__.py
│   ├── loader.py
│   ├── profiler.py
│   └── cleaner.py
├── statistics/
│   ├── __init__.py
│   ├── descriptive.py
│   ├── correlation.py
│   ├── t_test.py
│   └── regression.py
├── visualization/
│   ├── __init__.py
│   └── figure_generator.py
└── report/
    ├── __init__.py
    └── report_generator.py
```

第二版不设置 `selector/` 文件夹。分析方法直接由 Planner 确定，`skill_router.py` 根据 Planner 给出的 `skill_name` 调用对应 Skill。

`report/` 文件夹只保留 `report_generator.py`，不再单独设置结果解释脚本。未出现在上述目录中的 Skill 均不属于第二版范围。

---

## 3. 基本调用约定

所有公开 Skill 统一提供 `run()` 函数：

```python
def run(request: dict) -> dict:
    pass
```

输入通常包含以下字段：

```json
{
  "task_id": "task_xxx",
  "skill_name": "data_profiler",
  "data_path": "outputs/uploads/task_xxx/data.csv",
  "params": {}
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | `string` | 当前任务的唯一标识，需要生成文件时使用 |
| `skill_name` | `string` | Planner 指定的 Skill 名称 |
| `data_path` | `string` | 当前 Skill 使用的数据文件路径 |
| `params` | `object` | 当前 Skill 的专用参数 |

不同 Skill 只返回自己需要的结果字段，主要包括：

| 字段 | 类型 | 说明 |
|---|---|---|
| `summary` | `object` | 核心统计结果或执行摘要 |
| `tables` | `array` | 结构化表格结果 |
| `figures` | `array` | 生成的图表信息 |
| `artifacts` | `array` | 清洗后数据或报告等文件信息 |

没有对应结果时可以不返回该字段，不要求使用空数组占位。

---

## 4. 数据处理模块

### 4.1 `data/loader.py`

#### 职责

识别 CSV、XLS 或 XLSX 文件，并将文件读取为 pandas `DataFrame`，供后端后续处理使用。

#### 输入

```json
{
  "task_id": "task_xxx",
  "skill_name": "data_loader",
  "data_path": "outputs/uploads/task_xxx/data.xlsx",
  "params": {
    "sheet_name": 0,
    "encoding": null,
    "delimiter": null
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `sheet_name` | `string \| integer` | `0` | Excel 工作表名称或序号 |
| `encoding` | `string \| null` | `null` | CSV 文件编码；非 CSV 文件不使用 |
| `delimiter` | `string \| null` | `null` | CSV 分隔符；非 CSV 文件不使用 |

#### 输出

```python
{
    "dataframe": df,
    "summary": {
        "file_type": "csv",
        "row_count": 120,
        "column_count": 8,
        "columns": ["yield", "fertilizer", "temperature"]
    }
}
```

其中 `dataframe` 是后端内部使用的 pandas `DataFrame` 对象，不直接放入 REST API 的 JSON 响应。

---

### 4.2 `data/profiler.py`

#### 职责

读取数据文件并生成数据画像，包括行列数量、字段类型、缺失情况、唯一值数量、重复行数量和前几行预览。

#### 输入

```json
{
  "task_id": "task_xxx",
  "skill_name": "data_profiler",
  "data_path": "outputs/uploads/task_xxx/data.csv",
  "params": {
    "sample_rows": 5,
    "top_categories": 10
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `sample_rows` | `integer` | `5` | 预览的行数 |
| `top_categories` | `integer` | `10` | 分类字段最多统计的高频类别数 |

#### 输出

```json
{
  "summary": {
    "row_count": 120,
    "column_count": 3,
    "duplicate_rows": 2,
    "total_missing": 7,
    "columns": [
      {
        "name": "yield",
        "inferred_type": "numeric",
        "dtype": "float64",
        "non_null_count": 118,
        "missing_count": 2,
        "missing_rate": 0.0167,
        "unique_count": 104
      }
    ],
    "preview": []
  }
}
```

重复行指所有列的值均相同的记录。Profiler 只统计重复行，不删除数据。

---

### 4.3 `data/cleaner.py`

#### 职责

根据 Planner 给出的参数处理重复记录和缺失值，并保存清洗后的数据集。

#### 输入

```json
{
  "task_id": "task_xxx",
  "skill_name": "data_cleaner",
  "data_path": "outputs/uploads/task_xxx/data.csv",
  "params": {
    "columns": ["yield", "fertilizer"],
    "drop_duplicates": true,
    "missing_strategy": "drop_required",
    "required_columns": ["yield", "fertilizer"],
    "output_format": "csv"
  }
}
```

| 参数 | 类型 | 说明 |
|---|---|---|
| `columns` | `array[string]` | 本次需要保留或处理的字段 |
| `drop_duplicates` | `boolean` | 是否删除完全重复的记录 |
| `missing_strategy` | `string` | 缺失值处理方法 |
| `required_columns` | `array[string]` | 当前分析必须使用的字段 |
| `output_format` | `string` | 输出文件格式，第二版使用 `csv` |

`missing_strategy` 支持：

| 取值 | 处理方式 |
|---|---|
| `drop_required` | 只删除 `required_columns` 中存在缺失值的行 |
| `drop_rows` | 删除任意字段存在缺失值的行 |
| `mean` | 数值字段使用均值填补 |
| `median` | 数值字段使用中位数填补 |
| `mode` | 使用众数填补 |
| `none` | 不处理缺失值 |

#### 输出

```json
{
  "summary": {
    "input_rows": 120,
    "output_rows": 115,
    "duplicates_removed": 2,
    "rows_removed_for_missing": 3,
    "values_imputed": 0,
    "operations": [
      "删除 2 行完全重复记录",
      "删除分析必需字段含缺失值的 3 行记录"
    ]
  },
  "artifacts": [
    {
      "name": "cleaned_data",
      "type": "csv",
      "path": "outputs/uploads/task_xxx/cleaned.csv"
    }
  ]
}
```

Cleaner 之后的统计分析、可视化和报告生成均使用清洗后的数据或由清洗后数据产生的结果。

---

## 5. 统计分析模块

### 5.1 `statistics/descriptive.py`

#### 职责

对指定数值变量和分类变量进行描述性统计。

#### 输入

```json
{
  "data_path": "outputs/uploads/task_xxx/cleaned.csv",
  "params": {
    "columns": ["yield", "temperature", "fertilizer"],
    "include_percentiles": true
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `columns` | `array[string]` | 无 | 需要统计的字段 |
| `include_percentiles` | `boolean` | `true` | 是否返回四分位数 |

数值变量返回 `count`、`mean`、`std`、`min`、`q1`、`median`、`q3`、`max`；分类变量返回 `count`、`unique`、`mode`、`mode_frequency`。

#### 输出

```json
{
  "tables": [
    {
      "name": "descriptive_statistics",
      "title": "描述性统计结果",
      "columns": [
        "variable", "type", "count", "mean", "std",
        "min", "q1", "median", "q3", "max", "unique",
        "mode", "mode_frequency"
      ],
      "rows": [
        {
          "variable": "age",
          "type": "numeric",
          "count": 98,
          "mean": 20.43,
          "std": 1.76,
          "min": 18,
          "q1": 19,
          "median": 20,
          "q3": 22,
          "max": 24,
          "unique": null,
          "mode": null,
          "mode_frequency": null
        }
      ]
    }
  ]
}
```

---

### 5.2 `statistics/correlation.py`

#### 职责

计算多个数值变量之间的相关系数矩阵。

#### 输入

```json
{
  "data_path": "outputs/uploads/task_xxx/cleaned.csv",
  "params": {
    "columns": ["temperature", "yield"],
    "method": "pearson",
    "alpha": 0.05,
    "missing": "pairwise",
    "min_periods": 3
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `columns` | `array[string]` | 无 | 参与相关分析的数值字段 |
| `method` | `string` | `pearson` | `pearson`、`spearman` 或 `kendall` |
| `alpha` | `float` | `0.05` | 显著性水平 |
| `missing` | `string` | `pairwise` | 两变量计算时使用共同非缺失样本 |
| `min_periods` | `integer` | `3` | 每对变量计算所需的最少有效样本数 |

#### 输出

```json
{
  "summary": {
    "method": "pearson",
    "alpha": 0.05,
    "variable_count": 3
  },
  "tables": [
    {
      "name": "correlation_matrix",
      "title": "相关系数矩阵",
      "columns": ["variable", "height", "weight", "score"],
      "rows": [
        {"variable": "height", "height": 1.0, "weight": 0.72, "score": 0.31},
        {"variable": "weight", "height": 0.72, "weight": 1.0, "score": 0.25},
        {"variable": "score", "height": 0.31, "weight": 0.25, "score": 1.0}
      ]
    }
  ]
}
```

第二版只返回相关系数矩阵，不单独返回 p 值矩阵。

---

### 5.3 `statistics/t_test.py`

#### 职责

比较两个独立组的数值型目标变量均值是否存在显著差异。

#### 输入

```json
{
  "data_path": "outputs/uploads/task_xxx/cleaned.csv",
  "params": {
    "target_column": "yield",
    "group_column": "fertilizer",
    "groups": ["A", "B"],
    "equal_var": "auto",
    "alternative": "two-sided",
    "alpha": 0.05
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `target_column` | `string` | 无 | 数值型目标变量 |
| `group_column` | `string` | 无 | 分组变量 |
| `groups` | `array[string]` | 无 | 需要比较的两个类别 |
| `equal_var` | `boolean \| string` | `auto` | `auto` 时先进行 Levene 检验，再选择普通 t 检验或 Welch t 检验 |
| `alternative` | `string` | `two-sided` | `two-sided`、`less` 或 `greater` |
| `alpha` | `float` | `0.05` | 显著性水平 |

#### 输出

```json
{
  "summary": {
    "test": "welch_t_test",
    "group_1": "A",
    "group_2": "B",
    "mean_1": 21.4,
    "mean_2": 24.1,
    "mean_difference": -2.7,
    "t_statistic": -3.52,
    "degrees_of_freedom": 55.8,
    "p_value": 0.0009,
    "alpha": 0.05,
    "significant": true,
    "cohens_d": -0.91
  }
}
```

第二版 t 检验只返回 `summary`，不单独返回表格。

---

### 5.4 `statistics/regression.py`

#### 职责

使用一个或多个数值型解释变量建立 OLS 线性回归模型。第二版暂不自动处理分类解释变量。

#### 输入

```json
{
  "data_path": "outputs/uploads/task_xxx/cleaned.csv",
  "params": {
    "target_column": "yield",
    "feature_columns": ["temperature", "rainfall"],
    "add_constant": true,
    "alpha": 0.05,
    "standardize": false
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `target_column` | `string` | 无 | 数值型因变量 |
| `feature_columns` | `array[string]` | 无 | 数值型解释变量 |
| `add_constant` | `boolean` | `true` | 是否加入截距项 |
| `alpha` | `float` | `0.05` | 置信区间和显著性判断使用的水平 |
| `standardize` | `boolean` | `false` | 是否在拟合前标准化解释变量 |

#### 输出

```json
{
  "summary": {
    "model": "ols",
    "n_observations": 115,
    "r_squared": 0.68,
    "adjusted_r_squared": 0.66,
    "f_statistic": 38.2,
    "f_p_value": 0.000001,
    "rmse": 2.14,
    "aic": 318.4,
    "bic": 329.1
  },
  "tables": [
    {
      "name": "coefficients",
      "title": "回归系数",
      "columns": [
        "variable", "coefficient", "standard_error", "t_value",
        "p_value", "confidence_interval_lower", "confidence_interval_upper"
      ],
      "rows": []
    },
    {
      "name": "model_metrics",
      "title": "回归模型整体指标",
      "columns": [
        "r_squared", "adjusted_r_squared", "rmse", "aic", "bic",
        "f_statistic", "f_p_value"
      ],
      "rows": [
        {
          "r_squared": 0.68,
          "adjusted_r_squared": 0.66,
          "rmse": 2.14,
          "aic": 318.4,
          "bic": 329.1,
          "f_statistic": 38.2,
          "f_p_value": 0.000001
        }
      ]
    }
  ]
}
```

---

## 6. 可视化模块

### 6.1 `visualization/figure_generator.py`

#### 职责

根据 Planner 指定的分析类型和字段，从清洗后的数据中生成对应图表并保存为图片。

#### 输入

```json
{
  "task_id": "task_xxx",
  "skill_name": "figure_generator",
  "data_path": "outputs/uploads/task_xxx/cleaned.csv",
  "params": {
    "analysis_type": "correlation",
    "chart_type": null,
    "columns": ["temperature", "yield"],
    "target_column": null,
    "group_column": null,
    "feature_columns": [],
    "title": null,
    "dpi": 150
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `analysis_type` | `string` | 无 | `descriptive`、`correlation`、`t_test` 或 `regression` |
| `chart_type` | `string \| null` | `null` | 指定图表类型；为空时按分析类型选择 |
| `columns` | `array[string]` | `[]` | 普通绘图字段 |
| `target_column` | `string \| null` | `null` | 目标变量 |
| `group_column` | `string \| null` | `null` | 分组变量 |
| `feature_columns` | `array[string]` | `[]` | 回归解释变量 |
| `title` | `string \| null` | `null` | 自定义图表标题 |
| `dpi` | `integer` | `150` | 图片分辨率 |

默认图表对应关系：

| `analysis_type` | 默认图表 |
|---|---|
| `descriptive` | 数值变量直方图或分类变量条形图 |
| `correlation` | 散点图或相关系数热力图 |
| `t_test` | 两组箱线图 |
| `regression` | 回归拟合图或残差图 |

#### 输出

```json
{
  "figures": [
    {
      "name": "correlation_heatmap",
      "chart_type": "heatmap",
      "title": "变量相关系数热力图",
      "path": "outputs/figures/task_xxx/correlation_heatmap.png",
      "mime_type": "image/png"
    }
  ]
}
```

---

## 7. 报告生成模块

### 7.1 `report/report_generator.py`

#### 职责

汇总用户问题、数据画像、清洗记录、Planner 的分析计划、统计结果和图表，并将这些真实结构化信息提交给大语言模型生成 Markdown 分析报告。该脚本不重新执行统计计算，也不调用单独的结果解释 Skill。

报告生成阶段的大语言模型只负责组织语言、解释指标和总结结论。所有统计数值必须来自 `statistical_results`，不得由模型重新计算、修改或补充。

#### 输入

```json
{
  "task_id": "task_xxx",
  "skill_name": "report_generator",
  "params": {
    "question": "不同肥料组的产量是否存在差异？",
    "profile_result": {},
    "cleaning_result": {},
    "analysis_plan": {},
    "statistical_results": [],
    "figures": [],
    "output_format": "markdown"
  }
}
```

| 参数 | 类型 | 说明 |
|---|---|---|
| `question` | `string` | 用户原始分析问题 |
| `profile_result` | `object` | `data_profiler` 的结果 |
| `cleaning_result` | `object` | `data_cleaner` 的结果 |
| `analysis_plan` | `object` | Planner 生成的分析计划 |
| `statistical_results` | `array[object]` | 已执行统计 Skill 的结果列表 |
| `figures` | `array[object]` | `figure_generator` 生成的图表列表 |
| `output_format` | `string` | 第二版固定为 `markdown` |

#### 报告结构

1. 分析问题
2. 数据集概况
3. 数据清洗说明
4. 分析计划与方法
5. 统计分析结果
6. 可视化图表
7. 分析结论

其中“分析结论”由大语言模型严格依据已有统计结果撰写。例如，模型可以根据已经计算出的 `p_value`、`alpha` 和 `significant` 字段组织自然语言结论，但不能生成输入中不存在的统计数值。系统不另设 `result_interpreter.py`。

#### 输出

```json
{
  "artifacts": [
    {
      "name": "analysis_report",
      "type": "markdown",
      "path": "outputs/reports/task_xxx/report.md"
    }
  ]
}
```

---

## 8. Skill Router 注册表

`backend/agent/skill_router.py` 只注册第二版实际存在的 Skill：

```python
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
```

Planner 只能从上述注册名称中选择 Skill。Router 按计划顺序调用相应模块，并把前一步产生的数据路径或结果传给下一步。

典型调用顺序如下：

```text
data_loader
    ↓
data_profiler
    ↓
data_cleaner
    ↓
Planner 指定的统计 Skill
    ↓
figure_generator
    ↓
report_generator
```

---

## 9. 第二版范围说明

- 只支持 CSV、XLS 和 XLSX 数据文件。
- 数据清洗只处理重复值和缺失值。
- 统计分析只保留描述性统计、相关分析、独立样本 t 检验和线性回归。
- 线性回归只接收数值型解释变量。
- 分析方法由 Planner 直接决定，不使用 `method_selector.py`。
- 报告生成通过统一的 `backend/llm/client.py` 调用大语言模型，但不依赖 `result_interpreter.py`。
- 不设置计算资源选择和 HPC 提交 Skill。
- 各 Skill 默认正常执行，只返回分析结果和生成文件信息。

---

## 10. 版本信息

- 文档版本：`2.1`
- 对应系统版本：Research Analysis Agent 第二版
- 更新日期：2026-08-17
