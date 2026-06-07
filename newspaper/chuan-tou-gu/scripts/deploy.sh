#!/bin/bash
# 川投顧日報 - 部署腳本
# 每日 11:00 執行：生成日報並部署到 GitHub Pages

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
REPO_DIR="/tmp/ebooksforme"
DATE_STR=$(date +%Y-%m-%d)

echo "========================================"
echo "川投顧日報 - 每日部署"
echo "日期: $DATE_STR"
echo "時間: $(date '+%H:%M:%S')"
echo "========================================"

# 1. 生成日報
echo ""
echo "[1/4] 生成日報..."
cd "$SCRIPT_DIR"

# 檢查是否有 API key
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "警告: 未設定 OPENAI_API_KEY 或 ANTHROPIC_API_KEY"
    echo "請先設定環境變數:"
    echo "  export OPENAI_API_KEY='your-key'"
    echo "  export ANTHROPIC_API_KEY='your-key'"
    exit 1
fi

# 執行生成腳本
python3 generate_with_llm.py

# 2. 複製到 repo
echo ""
echo "[2/4] 複製到 GitHub repo..."
cp -r "$BASE_DIR/$DATE_STR" "$REPO_DIR/newspaper/chuan-tou-gu/"

# 3. Git 提交
echo ""
echo "[3/4] Git 提交..."
cd "$REPO_DIR"
git add -A
git commit -m "川投顧日報: $DATE_STR 自動生成" || echo "無變更需要提交"

# 4. 推送到 GitHub
echo ""
echo "[4/4] 推送到 GitHub..."
git push

echo ""
echo "========================================"
echo "✅ 部署完成!"
echo "URL: https://julianshen.github.io/ebooksforme/newspaper/chuan-tou-gu/$DATE_STR/"
echo "========================================"
