# 📊 科研数据分析平台

科研数据上传 → 自动分析 → 图表生成 → 报告下载的一站式网页应用。

基于 OpenClaw [research-analysis](https://github.com/openclaw) 流水线（dataloader → datacleaner → methodselector → statisticsexecutor → figuregenerator → reportgenerator）。

## 快速启动

```bash
cd ~/workspace/research-web
./start.sh
```

浏览器打开 **http://localhost:8001**

## 使用流程

1. **上传数据**：拖拽或点击上传 CSV / Excel 文件
2. **配置参数**：选择分析方法、目标变量(Y)、自变量(X)，或全自动推荐
3. **等待分析**：实时进度展示（数据加载 → 清洗 → 分析 → 图表 → 报告）
4. **查看结果**：报告预览、交互式图表、一键下载

## 项目结构

```
research-web/
├── start.sh                  # 一键启动脚本
├── requirements.txt          # Python 依赖
├── README.md
├── .gitignore
├── backend/
│   ├── main.py               # FastAPI 入口
│   ├── config.py             # 配置（端口8001、路径、限制）
│   ├── routers/
│   │   ├── upload.py         # POST /api/upload
│   │   ├── analysis.py       # POST /api/analyze, GET /api/tasks
│   │   └── download.py       # GET /api/download, /api/files
│   └── services/
│       ├── task_manager.py   # 任务状态管理（UUID + 文件）
│       └── pipeline.py       # 流水线编排（异步 subprocess）
├── frontend/
│   ├── index.html            # 主页面
│   ├── css/style.css         # 浅色专业风样式
│   └── js/
│       ├── config.js         # API 地址
│       ├── upload.js         # 拖拽上传
│       ├── analysis.js       # 分析配置 + 进度轮询 + 结果加载
│       ├── results.js        # Tab切换 + Toast + 历史记录
│       └── main.js           # 初始化
├── uploads/                  # 上传文件（不追踪）
└── outputs/tasks/            # 分析结果（不追踪）
```

## API 总览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传文件（CSV/XLSX/XLS，≤200MB） |
| POST | `/api/analyze/{task_id}` | 启动分析 |
| GET | `/api/tasks/{task_id}` | 查询任务状态 |
| GET | `/api/tasks` | 历史任务列表 |
| GET | `/api/download/{task_id}/report.md` | 下载报告 |
| GET | `/api/download/{task_id}/result.json` | 下载 JSON 结果 |
| GET | `/api/download/{task_id}/summary.md` | 下载摘要 |
| GET | `/api/download/{task_id}/data.csv` | 下载清洗后数据 |
| GET | `/api/download/{task_id}/figures.zip` | 下载全部图表 |
| GET | `/api/files/{task_id}` | 列出输出文件 |
| GET | `/api/health` | 健康检查 |

## 流水线步骤

```
上传 → dataloader → datacleaner → methodselector → statisticsexecutor → figuregenerator → reportgenerator → 完成
```

- **dataloader**：加载 CSV/XLSX，自动识别变量类型（数值/分类/日期）
- **datacleaner**：清洗数据（格式修复、IQR 异常检测、缺失值统计）
- **methodselector**：未指定方法时自动推荐最优统计方法
- **statisticsexecutor**：执行 t 检验 / ANOVA / 回归 / 卡方等
- **figuregenerator**：生成 Plotly 交互式 HTML 图表
- **reportgenerator**：生成学术风格 Markdown 报告

## 技术栈

- **后端**: Python FastAPI (port 8001)
- **前端**: 纯 HTML + CSS + JS（零构建工具）
- **任务队列**: 文件状态 + 前端轮询（无需 Celery/Redis）
- **图表**: Plotly 交互式 HTML
