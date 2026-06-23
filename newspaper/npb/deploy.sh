#!/bin/bash
# 日職每日報自動部署腳本
# 每日中午12:00執行：收集數據 → 生成 HTML → Git push

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GIT_DIR="/home/julianshen/projects/ebooksforme"
VENV_PYTHON="/home/julianshen/projects/ebooksforme/newspaper/.venv/bin/python3"

# 載入 API 金鑰（OpenRouter 用於 LLM 翻譯）
if [ -f "$HOME/.hermes/.env" ]; then
    set -a; source "$HOME/.hermes/.env"; set +a
fi

echo "========================================"
echo "日職每日報自動生成開始: $(date)"
echo "========================================"

# 1. 收集數據
echo "[1/3] 收集數據..."
cd "$SCRIPT_DIR"
"$VENV_PYTHON" collect_data.py

# 2. 生成 HTML（含新聞 LLM 翻譯）
echo "[2/3] 生成 HTML..."
# 設定較長的 LLM timeout（每個批次 300s）
"$VENV_PYTHON" generate_newspaper.py

# 3. 部署到 GitHub Pages
echo "[3/3] 部署到 GitHub..."
cd "$GIT_DIR"
git add -A
git commit -m "日職每日報自動更新: $(date +%Y-%m-%d)" || true
git push

echo "========================================"
echo "完成: $(date)"
echo "========================================"
