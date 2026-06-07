#!/bin/bash
# JPOP流行報 - 部署腳本
# 每週日零點執行：用 LLM 生成週報並部署到 GitHub Pages

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENERATE_SCRIPT="$SCRIPT_DIR/generate_jpop_llm.py"
REPO_DIR="/tmp/ebooksforme"
DATE_STR=$(date +%Y-%m-%d)
WEEK_NUM=$(date +%V)

echo "=========================================="
echo "JPOP流行報 - 每週部署"
echo "日期: $DATE_STR"
echo "第 ${WEEK_NUM} 期"
echo "=========================================="

# 1. 生成週報
echo ""
echo "[1/4] 使用 LLM 生成週報..."
python3 "$GENERATE_SCRIPT"

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
