#!/bin/bash
# 川投顧日報 - 部署腳本
# 每日 11:00 執行

set -e

REPO_DIR="/home/julianshen/projects/ebooksforme"
DATE_STR=$(date +%Y-%m-%d)

echo "========================================"
echo "川投顧日報 - 每日部署"
echo "日期: $DATE_STR"
echo "時間: $(date '+%H:%M:%S')"
echo "========================================"

# 1. 收集數據
echo ""
echo "[1/3] 收集數據..."
cd "$REPO_DIR/newspaper/chuan-tou-gu"
python3 scripts/collect_data.py

# 2. 生成報紙（由 LLM 翻譯新聞 + 生成分析）
echo ""
echo "[2/3] 生成報紙..."
python3 scripts/generate_newspaper.py "$DATE_STR"

# 3. Git 提交
echo ""
echo "[3/3] Git 提交..."
cd "$REPO_DIR"
git add -A
git commit -m "川投顧日報: $DATE_STR 自動生成" || echo "無變更需要提交"
git push

echo ""
echo "========================================"
echo "✅ 部署完成!"
echo "URL: https://julianshen.github.io/ebooksforme/newspaper/chuan-tou-gu/$DATE_STR/"
echo "========================================"
