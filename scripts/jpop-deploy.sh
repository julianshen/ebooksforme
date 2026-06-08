#!/bin/bash
# JPOP流行報 - 部署腳本
# 每週日零點執行：用 LLM 生成週報並部署到 GitHub Pages
# 如果當日已有手動生成的版本則不覆蓋

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENERATE_SCRIPT="$SCRIPT_DIR/generate_jpop_llm.py"
REPO_DIR="/home/julianshen/projects/ebooksforme"
DATE_STR=$(date +%Y-%m-%d)
WEEK_NUM=$(date +%V)
TARGET_DIR="$REPO_DIR/newspaper/jpop/$DATE_STR"
TARGET_FILE="$TARGET_DIR/index.html"

echo "=========================================="
echo "JPOP流行報 - 每週部署"
echo "日期: $DATE_STR"
echo "第 ${WEEK_NUM} 期"
echo "=========================================="

# 如果今天已有手動生成的版本，跳過
if [ -f "$TARGET_FILE" ] && [ $(stat -c%s "$TARGET_FILE") -gt 12000 ]; then
    echo "✅ 今日已有手動生成的完整版本（$([ -f $TARGET_FILE ] && stat -c%s $TARGET_FILE || echo 0) bytes），跳過自動生成。"
    echo "自動生成的內容品質較低，保留手動版本。"
    exit 0
fi

# 1. 生成週報
echo ""
echo "[1/4] 使用 LLM 生成週報..."
python3 "$GENERATE_SCRIPT"

# 檢查生成是否成功
if [ ! -f "$TARGET_FILE" ]; then
    echo "❌ 生成失敗！"
    exit 1
fi

# 2. 保留最多 6 期
echo ""
echo "[2/4] 清理舊期數..."
cd "$REPO_DIR/newspaper/jpop"
ISSUES=$(ls -d 2*/ 2>/dev/null | sort -r || true)
COUNT=$(echo "$ISSUES" | grep -v "^$" | wc -l)
if [ "$COUNT" -gt 6 ]; then
    TO_DELETE=$(echo "$ISSUES" | tail -n $((COUNT - 6)))
    echo "刪除 $((COUNT - 6)) 期舊報紙："
    echo "$TO_DELETE"
    rm -rf $TO_DELETE
fi

# 3. Git 提交
echo ""
echo "[3/4] Git 提交..."
cd "$REPO_DIR"
git add -A
git commit -m "JPOP流行報: $DATE_STR 第${WEEK_NUM}期 自動生成" || echo "無變更需要提交"

# 4. 推送到 GitHub
echo ""
echo "[4/4] 推送到 GitHub..."
git push

echo ""
echo "=========================================="
echo "✅ 部署完成!"
echo "URL: https://julianshen.github.io/ebooksforme/newspaper/jpop/$DATE_STR/"
echo "=========================================="
