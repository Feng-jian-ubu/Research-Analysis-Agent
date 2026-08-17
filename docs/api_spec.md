# Research Analysis Agent REST API 规范

## 1. 文档说明

本文档描述当前 React 前端与 FastAPI 后端实际使用的 REST API 合同。接口实现发生变更时，应同步更新本文档、Pydantic Schema 和前端调用代码。

- 文档版本：`2.1`
- API 前缀：`/api/v1`
- 数据格式：除文件上传和文件下载外，均为 JSON
- 时间格式：ISO 8601，当前后端使用 `Asia/Singapore` 时区

## 2. 接口清单

| 方法 | 路径 | 功能 | 成功状态码 |
|---|---|---|---:|
| `GET` | `/health` | 后端健康检查 | `200` |
| `POST` | `/api/v1/datasets` | 上传数据集并生成画像 | `201` |
| `GET` | `/api/v1/datasets/{dataset_id}/profile` | 获取数据集画像 | `200` |
| `POST` | `/api/v1/analyses` | 创建分析任务 | `202` |
| `GET` | `/api/v1/tasks/{task_id}` | 查询任务状态 | `200` |
| `GET` | `/api/v1/analyses/{task_id}/result` | 获取完整分析结果 | `200` |
| `GET` | `/api/v1/reports/{task_id}/download` | 下载 Markdown 报告 | `200` |
| `GET` | `/api/v1/figures/{task_id}/{file_name}` | 获取 PNG 图表 | `200` |

## 3. 前端业务流程

```text
UploadPage
  → POST /datasets
  → 获得 dataset_id
AnalysisPage
  → GET /datasets/{dataset_id}/profile
  → POST /analyses
  → 获得 task_id
ResultPage
  → 每 2 秒 GET /tasks/{task_id}
  → status=completed 后停止轮询
AnalysisResult
  → GET /analyses/{task_id}/result
  → 展示分析计划、统计摘要、表格和图表
  → 按需下载 Markdown 报告
```

创建任务接口只负责建立任务并启动后台分析，不会在响应中返回完整分析结果。

## 4. 通用约定

### 4.1 标识符

- 数据集标识格式：`ds_` 加 8 位十六进制字符，例如 `ds_8f42c1a2`。
- 任务标识格式：`task_` 加 12 位十六进制字符，例如 `task_04b92aaed831`。
- 标识符均由后端生成，前端只负责保存和回传。

### 4.2 错误响应

当前后端使用 FastAPI 默认错误格式：

```json
{
  "detail": "数据集不存在。"
}
```

Pydantic 请求校验失败时，`detail` 为校验错误数组。前端优先显示 `response.data.detail`，未收到后端响应时显示 Axios 的本地错误信息。

后台分析失败不改变已经返回的 `POST /analyses` 响应。失败信息通过任务状态接口返回：

```json
{
  "status": "failed",
  "error": {
    "message": "具体错误信息"
  }
}
```

当前实现尚未统一返回业务 `error_code`，客户端不得依赖该字段必定存在。

### 4.3 跨域

后端默认允许：

```text
http://localhost:5173
http://127.0.0.1:5173
```

部署时通过 `FRONTEND_ORIGINS` 配置允许来源，多个地址使用英文逗号分隔。

## 5. 公共数据结构

### 5.1 `AnalysisPlan`

Planner 返回的计划由原始问题和有序 Skill 步骤组成：

```json
{
  "question": "温度与产量是否存在相关关系？",
  "steps": [
    {
      "skill_name": "data_cleaner",
      "params": {
        "columns": ["temperature", "yield"],
        "drop_duplicates": true,
        "missing_strategy": "drop_required",
        "required_columns": ["temperature", "yield"],
        "output_format": "csv"
      }
    },
    {
      "skill_name": "correlation",
      "params": {
        "columns": ["temperature", "yield"],
        "method": "pearson",
        "alpha": 0.05
      }
    },
    {
      "skill_name": "figure_generator",
      "params": {
        "analysis_type": "correlation",
        "columns": ["temperature", "yield"]
      }
    },
    {
      "skill_name": "report_generator",
      "params": {
        "output_format": "markdown"
      }
    }
  ]
}
```

Planner 可选择的分析 Skill 为：

```text
data_cleaner
descriptive
correlation
t_test
regression
figure_generator
report_generator
```

当前版本不支持 ANOVA。

### 5.2 `ResultTable`

```json
{
  "table_id": "correlation_matrix",
  "title": "相关系数矩阵",
  "columns": ["variable", "temperature", "yield"],
  "rows": [
    {
      "variable": "temperature",
      "temperature": 1.0,
      "yield": 0.85
    }
  ],
  "notes": []
}
```

`rows` 是对象数组，每个对象以 `columns` 中的字段名作为键。`table_id`、`title` 和 `notes` 可以缺省。

### 5.3 `Figure`

```json
{
  "figure_id": "correlation_heatmap",
  "title": "变量相关系数热力图",
  "type": "heatmap",
  "url": "/api/v1/figures/task_04b92aaed831/correlation_heatmap.png",
  "alt_text": "变量相关系数热力图"
}
```

图表接口只向前端返回受控 URL，不返回服务器内部绝对路径。

## 6. 上传数据集

### 6.1 请求

```http
POST /api/v1/datasets
Content-Type: multipart/form-data
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `file` | File | 是 | `.csv`、`.xls` 或 `.xlsx` |
| `sheet_name` | string | 否 | Excel 工作表名称；默认读取第一个工作表 |

前端当前限制文件最大为 20 MiB。后端当前只校验扩展名，尚未独立执行 20 MiB 大小限制。

### 6.2 成功响应

```json
{
  "dataset_id": "ds_8f42c1a2",
  "status": "ready",
  "file_name": "experiment.csv",
  "file_type": "csv",
  "sheet_name": null,
  "file_size": 2048,
  "row_count": 120,
  "column_count": 3,
  "duplicate_row_count": 0,
  "total_missing": 2,
  "columns": [
    {
      "name": "yield",
      "data_type": "numeric",
      "pandas_dtype": "float64",
      "missing_count": 2,
      "missing_ratio": 0.016667,
      "unique_count": 118,
      "sample_values": [25.3, 27.1, 23.8]
    }
  ],
  "preview": [
    {"yield": 25.3}
  ],
  "created_at": "2026-08-17T10:31:00+08:00"
}
```

### 6.3 获取画像

```http
GET /api/v1/datasets/{dataset_id}/profile
```

成功响应与上传响应相同。数据集不存在时返回 `404`：

```json
{"detail": "数据集不存在。"}
```

## 7. 创建分析任务

### 7.1 请求

```http
POST /api/v1/analyses
Content-Type: application/json
```

```json
{
  "dataset_id": "ds_8f42c1a2",
  "question": "分析温度与产量之间的相关关系。",
  "options": {
    "alpha": 0.05
  }
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `dataset_id` | string | 是 | 非空 |
| `question` | string | 是 | 去除首尾空白后长度为 2～1000 |
| `options.alpha` | number | 否 | `0 < alpha < 1`，默认 `0.05` |

### 7.2 成功响应

状态码：`202 Accepted`

```json
{
  "task_id": "task_04b92aaed831",
  "dataset_id": "ds_8f42c1a2",
  "status": "pending",
  "progress": 0,
  "message": "分析任务已创建。",
  "status_url": "/api/v1/tasks/task_04b92aaed831",
  "result_url": "/api/v1/analyses/task_04b92aaed831/result",
  "created_at": "2026-08-17T10:32:00+08:00"
}
```

数据集不存在时返回 `404`。请求字段错误时返回 `422`。

## 8. 查询任务状态

```http
GET /api/v1/tasks/{task_id}
```

### 8.1 状态值

| 状态 | 含义 |
|---|---|
| `pending` | 任务已创建 |
| `profiling` | Schema 保留的数据画像状态；当前分析流程通常不会进入 |
| `planning` | 正在调用 Planner 生成分析计划 |
| `running` | 正在清洗、统计或生成图表 |
| `reporting` | 正在生成 Markdown 报告 |
| `completed` | 分析完成 |
| `failed` | 后台执行失败 |

当前主要状态流转为：

```text
pending → planning → running → reporting → completed
                 ↘          ↘           ↘ failed
```

### 8.2 运行中响应

```json
{
  "task_id": "task_04b92aaed831",
  "dataset_id": "ds_8f42c1a2",
  "status": "running",
  "progress": 48,
  "current_step": "正在执行相关分析",
  "plan": {
    "question": "分析温度与产量之间的相关关系。",
    "steps": [
      {
        "skill_name": "correlation",
        "params": {
          "columns": ["temperature", "yield"],
          "method": "pearson"
        }
      }
    ]
  },
  "error": null,
  "result_url": null,
  "created_at": "2026-08-17T10:32:00+08:00",
  "updated_at": "2026-08-17T10:32:04+08:00"
}
```

### 8.3 完成响应

完成后状态接口仍不返回完整统计结果，只提供 `result_url`：

```json
{
  "task_id": "task_04b92aaed831",
  "dataset_id": "ds_8f42c1a2",
  "status": "completed",
  "progress": 100,
  "current_step": "分析完成",
  "plan": {
    "question": "分析温度与产量之间的相关关系。",
    "steps": [
      {
        "skill_name": "correlation",
        "params": {
          "columns": ["temperature", "yield"],
          "method": "pearson"
        }
      }
    ]
  },
  "error": null,
  "result_url": "/api/v1/analyses/task_04b92aaed831/result",
  "created_at": "2026-08-17T10:32:00+08:00",
  "updated_at": "2026-08-17T10:32:15+08:00"
}
```

### 8.4 失败响应体

任务执行失败时，查询接口仍返回 `200`：

```json
{
  "task_id": "task_04b92aaed831",
  "dataset_id": "ds_8f42c1a2",
  "status": "failed",
  "progress": 20,
  "current_step": "分析任务执行失败",
  "plan": null,
  "error": {
    "message": "大语言模型返回格式不合法。"
  },
  "result_url": null,
  "created_at": "2026-08-17T10:32:00+08:00",
  "updated_at": "2026-08-17T10:32:02+08:00"
}
```

## 9. 获取完整分析结果

```http
GET /api/v1/analyses/{task_id}/result
```

只有 `completed` 状态可以获取结果；未完成时返回 `409`，任务不存在时返回 `404`。

### 9.1 成功响应

```json
{
  "task_id": "task_04b92aaed831",
  "dataset_id": "ds_8f42c1a2",
  "status": "completed",
  "question": "分析温度与产量之间的相关关系。",
  "analysis_plan": {
    "question": "分析温度与产量之间的相关关系。",
    "steps": [
      {
        "skill_name": "correlation",
        "params": {
          "columns": ["temperature", "yield"],
          "method": "pearson"
        }
      }
    ]
  },
  "profile_result": {
    "row_count": 120,
    "column_count": 3
  },
  "cleaning_result": {
    "summary": {}
  },
  "statistical_results": [
    {
      "skill_name": "correlation",
      "summary": {
        "method": "pearson",
        "alpha": 0.05,
        "variable_count": 2
      },
      "tables": [
        {
          "title": "相关系数矩阵",
          "columns": ["variable", "temperature", "yield"],
          "rows": [
            {
              "variable": "temperature",
              "temperature": 1.0,
              "yield": 0.85
            }
          ]
        }
      ]
    }
  ],
  "figures": [
    {
      "title": "变量相关系数热力图",
      "url": "/api/v1/figures/task_04b92aaed831/correlation_heatmap.png",
      "alt_text": "变量相关系数热力图"
    }
  ],
  "report_download_url": "/api/v1/reports/task_04b92aaed831/download",
  "completed_at": "2026-08-17T10:32:15+08:00"
}
```

`statistical_results` 按执行顺序保存一个或多个统计 Skill 的结果。前端不得假设所有任务只有一个顶层 `summary` 或一个顶层 `tables`。

## 10. 图表和报告

### 10.1 获取图表

```http
GET /api/v1/figures/{task_id}/{file_name}
```

- 仅允许字母、数字、下划线和连字符组成的 `.png` 文件名。
- 文件必须出现在当前任务结果的图表白名单中。
- 前端使用结果接口返回的 `url`，不自行拼接服务器文件路径。

### 10.2 下载报告

```http
GET /api/v1/reports/{task_id}/download
```

成功时返回 `text/markdown` 文件。任务未完成返回 `409`，报告不存在返回 `404`。

报告由 `report_generator` 将结构化分析结果提交给大语言模型生成。统计数值来自本地 Python Skill，大语言模型只负责组织和解释，不应重新计算或修改统计结果。

## 11. 前端调用约定

所有请求统一封装在：

```text
frontend/src/api/client.js
```

| 页面或组件 | 使用接口 |
|---|---|
| `FileUploader` | `POST /datasets` |
| `DatasetProfile` | `GET /datasets/{dataset_id}/profile` |
| `AnalysisPage` | `POST /analyses` |
| `useTaskPolling`、`AnalysisProgress` | `GET /tasks/{task_id}` |
| `AnalysisResult` | `GET /analyses/{task_id}/result` |
| `ChartViewer` | 使用结果接口返回的图表 URL |
| `ReportDownload` | `GET /reports/{task_id}/download` |

开发环境中，Vite 将 `/api` 代理到 `http://127.0.0.1:8000`。部署时通过 `VITE_API_BASE_URL` 配置完整 API 基础地址。

## 12. 当前实现限制

1. 数据集与任务状态保存在进程内存中，后端重启后会丢失。
2. 多 worker 部署时，不同进程之间不会共享任务状态。
3. 上传文件、清洗结果、图表和报告保存在本地 `outputs/` 目录。
4. 后端尚未执行上传文件大小上限，20 MiB 限制目前只在前端校验。
5. 当前没有暂停、取消、重新执行或删除任务接口。
6. 当前统计方法不包含 ANOVA。

## 13. 版本变更记录

| 版本 | 日期 | 说明 |
|---|---|---|
| `2.1` | 2026-08-17 | 同步当前计划结构、任务状态、完整结果结构和前端 `AnalysisResult` 展示流程 |
| `1.0` | 2026-08-09 | 初始 API 合同 |
