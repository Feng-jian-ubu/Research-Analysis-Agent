# Research Analysis Web

科研数据分析网页应用。上传 CSV/XLSX 数据文件，自动或手动选择分析方法，生成统计分析报告和交互式图表，支持一键下载。

## 快速启动

```bash
cd ~/workspace/research-web

# 安装依赖
pip3 install -r requirements.txt

# 启动服务
cd backend && python3 main.py
```

打开浏览器访问 http://localhost:8001

## 架构

```
backend/          — FastAPI 后端
  main.py         — 入口
  config.py       — 配置
  routers/        — API 路由
  services/       — 核心逻辑（流水线编排、任务管理）
frontend/         — 纯静态前端
  index.html      — 主页面
  css/style.css   — 样式
  js/             — JS 模块
uploads/          — 上传文件暂存
outputs/          — 分析结果输出
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传数据文件 |
| POST | `/api/analyze/{task_id}` | 启动分析 |
| GET | `/api/tasks/{task_id}` | 查询任务状态 |
| GET | `/api/download/{task_id}/{file}` | 下载文件 |
| GET | `/api/tasks` | 历史任务列表 |
