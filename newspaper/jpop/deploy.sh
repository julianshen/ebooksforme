#!/bin/bash
# JPOP流行報自動部署腳本
# 每週日零點執行：收集數據 → 生成 HTML → Git push

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GIT_DIR="/tmp/ebooksforme"
VENV_PYTHON="/tmp/ebooksforme/newspaper/.venv/bin/python3"

echo "========================================"
echo "JPOP流行報自動生成開始: $(date)"
echo "========================================"

# 1. 收集數擶
echo "[1/3] 收集數據..."
cd "$SCRIPT_DIR"
"$VENV_PYTHON" collect_data.py

# 2. 生成 HTML
echo "[2/3] 生成 HTML..."
"$VENV_PYTHON" generate_newspaper.py

# 3. 部署到 GitHub Pages
echo "[3/3] 部署到 GitHub..."
cd "$GIT_DIR"
git add -A
git commit -m "JPOP流行報自動更新: $(date +%Y-%m-%d)" || true
git push

echo "========================================"
echo "完成: $(date)"
echo "========================================"
