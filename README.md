# Research Analysis Agent

一个面向 CSV、XLS 和 XLSX 数据集的智能统计分析网页。

用户通过浏览器上传数据集并输入自然语言分析问题。后端调用大语言模型生成分析计划，随后使用本地 Python Skill 完成数据清洗和统计计算，最后再次调用大语言模型生成 Markdown 分析报告。

网页使用流程分为三步：

1. 上传 CSV 或 Excel 数据集并查看数据画像。
2. 输入自然语言分析需求并创建后台任务。
3. 查看任务进度、分析计划、统计摘要、结果表格和图表，或下载完整 Markdown 报告。

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
- 网页端任务进度、分析计划、统计摘要、结果表格和图表展示
- Markdown 完整报告下载

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
├── docs/                 API、系统架构和 Skill 规范
├── outputs/              运行时上传文件、清洗结果、图表和报告
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

配置完成后，可以先直接运行 LLM 客户端进行连通性检查：

```powershell
python backend/llm/client.py
```

成功时会输出当前模型名称和模型回复；失败时会显示配置或接口调用错误。

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

## 结果展示流程

创建任务后，前端会进入结果页并每 2 秒查询一次任务状态。任务完成后，网页会自动请求完整结果接口并展示：

- 用户的原始分析问题
- Planner 生成的分析步骤
- 各统计 Skill 的核心指标
- 描述性统计、相关分析、t 检验或回归结果表格
- 后端生成的 PNG 图表
- Markdown 报告下载入口

任务执行失败时，结果页会展示后端返回的具体错误信息。

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

## 当前限制

- 当前支持描述性统计、相关分析、独立样本 t 检验和线性回归。
- 数据集元数据和任务状态保存在后端进程内存中，重启后端后会丢失。
- 多 worker 部署时，不同进程之间不会共享任务状态，当前建议使用单 worker。
- 上传文件和分析产物保存在本机 `outputs/` 目录，不适合无持久磁盘的部署环境。
- 前端限制上传文件最大为 20 MB；后端目前尚未独立执行同样的大小限制。

## 详细文档

- [REST API 规范](docs/api_spec.md)
- [系统架构说明](docs/architecture_v2.md)
- [Skill 输入输出规范](docs/skill_spec_v2.md)
