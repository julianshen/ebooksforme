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
echo "[1/4] 收集數據..."
cd "$REPO_DIR/newspaper/chuan-tou-gu"
python3 scripts/collect_data.py

# 2. 生成報紙（由 LLM 翻譯新聞 + 生成分析）
echo ""
echo "[2/4] 生成報紙..."
python3 scripts/generate_newspaper.py "$DATE_STR"

# 3. 更新圖書館 index.html
echo ""
echo "[3/4] 更新圖書館 index.html..."
INDEX_FILE="$REPO_DIR/index.html"
OLD_DATE=$(grep -oP 'chuan-tou-gu/\K\d{4}-\d{2}-\d{2}' "$INDEX_FILE" | head -1)
if [ -n "$OLD_DATE" ] && [ "$OLD_DATE" != "$DATE_STR" ]; then
    sed -i "s|chuan-tou-gu/$OLD_DATE|chuan-tou-gu/$DATE_STR|g" "$INDEX_FILE"
    sed -i "s|📅 $OLD_DATE|📅 $DATE_STR|g" "$INDEX_FILE"
    echo "  圖書館已更新: $OLD_DATE → $DATE_STR"
else
    echo "  圖書館無需更新 (已為 $DATE_STR)"
fi

# 4. Git 提交
echo ""
echo "[4/4] Git 提交..."
cd "$REPO_DIR"
git add -A
git commit -m "川投顧日報: $DATE_STR 自動生成" || echo "無變更需要提交"
echo "  正在拉取遠端變更..."
git pull --rebase --autostash || echo "⚠️ git pull 失敗，繼續嘗試 push"
git push

echo ""
echo "========================================"
echo "✅ 部署完成!"
echo "URL: https://julianshen.github.io/ebooksforme/newspaper/chuan-tou-gu/$DATE_STR/"
echo "========================================"
