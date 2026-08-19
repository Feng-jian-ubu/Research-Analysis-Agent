#!/bin/bash
# 科研数据分析平台 — 一键启动
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "📊 科研数据分析平台"
echo "===================="
echo ""

# 检查 Python 3
if ! command -v python3 &>/dev/null; then
  echo "❌ 未找到 Python 3，请先安装 python3"
  exit 1
fi

# 检查依赖
echo "📦 检查依赖…"
pip3 install -q -r requirements.txt 2>&1 | tail -1

# 启动
echo "🚀 启动服务…"
echo "   前端页面: http://localhost:8001"
echo "   API 文档: http://localhost:8001/docs"
echo ""

cd backend
python3 -c "
import sys; sys.path.insert(0, '.')
from main import app
import uvicorn
print('📊 服务已启动，按 Ctrl+C 停止')
uvicorn.run(app, host='0.0.0.0', port=8001, log_level='info')
"
