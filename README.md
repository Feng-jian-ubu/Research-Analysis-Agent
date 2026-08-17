# Research Analysis Agent

一个面向 CSV、XLS 和 XLSX 数据集的智能统计分析网页。

用户通过浏览器上传数据集并输入自然语言分析问题。后端调用大语言模型生成分析计划，随后使用本地 Python Skill 完成数据清洗和统计计算，最后再次调用大语言模型生成 Markdown 分析报告。

## 主要功能

- CSV、XLS、XLSX 文件上传
- 数据画像与数据预览
- 重复值和缺失值处理
- 描述性统计
- Pearson、Spearman、Kendall 相关分析
- 独立样本 t 检验
- 一元和多元 OLS 线性回归
- 自然语言分析计划
- Markdown 分析报告生成
- 网页端任务进度和统计结果展示

> 可视化模块的接口已经接入，但 `skills/visualization/figure_generator.py` 仍需完成后才能生成真实图表。

## 运行环境

- Python 3.11 或更高版本
- Node.js 20.19 或更高版本
- 可访问的 OpenAI 兼容大语言模型 API

## 项目结构

```text
research-analysis-agent/
├── backend/              FastAPI、Agent 编排和 LLM 客户端
├── frontend/             React + Vite 网页
├── skills/               数据、统计、可视化和报告 Skill
├── .env.example          后端环境变量示例
├── .gitignore
├── README.md
└── requirements.txt      Python 生产依赖
```

上传的数据、清洗结果、图表和报告会在运行时写入 `outputs/`，该目录不提交 GitHub。

## 本地启动

### 1. 配置后端

在项目根目录创建虚拟环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

复制环境变量示例：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少填写：

```dotenv
LLM_API_KEY=你的密钥
LLM_MODEL=你的模型名称
```

如果使用兼容 OpenAI API 的第三方服务，还需要填写 `LLM_BASE_URL`。

启动 FastAPI：

```powershell
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

后端健康检查地址：<http://127.0.0.1:8000/health>

### 2. 启动前端

另开一个终端：

```powershell
Set-Location frontend
npm install
npm run dev
```

浏览器访问：<http://127.0.0.1:5173>

开发环境下，Vite 会自动把 `/api` 请求代理到 `http://127.0.0.1:8000`。

## 部署说明

前端与后端需要分别部署：

- 后端启动命令：`uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
- 前端构建目录：`frontend/`
- 前端构建命令：`npm install && npm run build`
- 前端输出目录：`frontend/dist`

部署前端时设置：

```text
VITE_API_BASE_URL=https://你的后端域名/api/v1
```

部署后端时设置：

```text
LLM_API_KEY
LLM_MODEL
LLM_BASE_URL（使用第三方兼容接口时填写）
FRONTEND_ORIGINS=https://你的前端域名
```

多个前端域名使用英文逗号分隔。不要把真实 `.env` 或 API Key 提交到 GitHub。

## API

主要接口：

```text
POST /api/v1/datasets
GET  /api/v1/datasets/{dataset_id}/profile
POST /api/v1/analyses
GET  /api/v1/tasks/{task_id}
GET  /api/v1/analyses/{task_id}/result
GET  /api/v1/reports/{task_id}/download
```

启动后端后可通过 `/docs` 查看完整的 Swagger API 文档。
