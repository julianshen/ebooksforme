#!/usr/bin/env python3
"""
JPOP流行報 - LLM 生成腳本
使用 OpenAI/Anthropic API 生成真實的 JPOP 週報
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

# 嘗試導入必要的庫
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# 設定目錄
OUTPUT_DIR = Path("/tmp/ebooksforme/newspaper/jpop")

def get_date_info():
    """取得日期資訊"""
    now = datetime.now()
    
    # 計算期數（以2026年第1週為基準）
    week_number = now.isocalendar()[1]
    
    return {
        "date_str": now.strftime("%Y-%m-%d"),
        "display_date": f"{now.year}年{now.month}月{now.day}日",
        "week_number": week_number,
        "year": now.year,
        "month": now.month,
        "day": now.day
    }

def build_prompt(date_info):
    """構建 LLM prompt"""
    
    prompt = f"""你是 JPOP流行報 的自動化編輯系統。請生成一份豐富的日本流行音樂週報 HTML 內容。

## 日期資訊
- 報紙日期：{date_info['display_date']}
- 第 {date_info['week_number']} 期

## 角色設定
- 你是專業的日本流行音樂編輯
- 用繁體中文撰寫，歌曲原名保留日文
- 內容必須真實，不能虛構

## 重要規則
1. **所有內容必須真實**：不能虛構歌曲、新聞、演唱會資訊
2. **Spotify 連結必須是 track 連結**：格式為 `https://open.spotify.com/track/xxxxx`，不是 artist 連結
3. **YouTube 連結必須真實**：必須是實際存在的影片 URL，格式為 `https://www.youtube.com/watch?v=xxxxx`
4. **所有內容繁體中文**：歌曲原名保留日文
5. **新聞必須標註來源**：音樂Natalie / Billboard Japan / Oricon / Model Press
6. **演唱會資訊必須真實**：日期、地點、售票資訊都要準確

## 需要生成的內容區塊

請生成以下 section（只需要 <section> 標籤內的內容，不需要外層的 html/head/body）：

### 1. Highlight Artist
- 當週焦點歌手（選擇一位當週有話題的歌手）
- 真實簡介
- Spotify artist 連結（這裡可以是 artist 連結）
- YouTube 頻道連結
- Official 官網連結

### 2. New Songs（5-8首）
每首歌曲必須包含：
- 歌曲名（日文原名）
- 歌手名
- 中文簡介
- **Spotify track 連結**（必須是 track 連結，不是 artist）
- **YouTube 影片連結**（必須是實際存在的影片）

### 3. Music News（4-6則）
每則新聞必須包含：
- 標題（繁體中文）
- 來源標註（音樂Natalie / Billboard Japan / Oricon / Model Press）
- 原文連結（真實可點擊的 URL）

### 4. Japan Concerts
- 日本演唱會資訊表格
- 日期、歌手、場地、售票連結

### 5. Taiwan Concerts
- 台灣場次資訊表格
- 日期、歌手、場地、售票連結

## CSS 類名參考
- section, section-header, section-title
- highlight, highlight-content, highlight-links
- song-grid, song-card, song-title, song-artist, song-links
- news-grid, news-card, news-title, news-source
- concert-table

## 輸出格式
請直接輸出 section 的 HTML 內容，不需要其他包裝。

請確保：
1. 所有連結真實可點擊
2. Spotify 連結必須是 track 連結
3. YouTube 連結必須是實際存在的影片
4. 繁體中文
5. 歌曲原名保留日文
"""
    
    return prompt

def call_openai(prompt):
    """呼叫 OpenAI API"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("未設定 OPENAI_API_KEY")
        return None
    
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是專業的日本流行音樂編輯。請用繁體中文生成 JPOP 週報的 HTML 內容。所有數據必須真實，連結必須可點擊。Spotify 連結必須是 track 連結（不是 artist）。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=8000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API 錯誤：{e}")
        return None

def call_anthropic(prompt):
    """呼叫 Anthropic API"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("未設定 ANTHROPIC_API_KEY")
        return None
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text
    except Exception as e:
        print(f"Anthropic API 錯誤：{e}")
        return None

def generate_content(date_info):
    """使用 LLM 生成內容"""
    prompt = build_prompt(date_info)
    
    # 嘗試 OpenAI
    if HAS_OPENAI and os.environ.get("OPENAI_API_KEY"):
        print("嘗試使用 OpenAI API...")
        content = call_openai(prompt)
        if content:
            return content
    
    # 嘗試 Anthropic
    if HAS_ANTHROPIC and os.environ.get("ANTHROPIC_API_KEY"):
        print("嘗試使用 Anthropic API...")
        content = call_anthropic(prompt)
        if content:
            return content
    
    print("無法使用 LLM API，請設定 OPENAI_API_KEY 或 ANTHROPIC_API_KEY")
    return None

def generate_html(content, date_info):
    """生成完整 HTML"""
    
    template = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JPOP流行報 - {date_info['display_date']} 第{date_info['week_number']}期</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&family=Noto+Serif+TC:wght@600;900&display=swap" rel="stylesheet">
    <style>
        :root {{
            --accent: #ff2a6d;
            --bg: #0f0f1a;
            --card: #1a1a2e;
            --text: #e0e0e0;
            --muted: #a0a0b0;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Noto Sans TC', 'Hiragino Sans', 'Meiryo', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            min-height: 100vh;
        }}
        .container {{ max-width: 960px; margin: 0 auto; padding: 20px; }}
        header {{
            text-align: center;
            padding: 30px 0;
            border-bottom: 3px solid var(--accent);
            margin-bottom: 30px;
        }}
        header h1 {{
            font-size: 2.8rem;
            margin: 0;
            color: var(--accent);
            letter-spacing: 4px;
            text-shadow: 0 0 10px rgba(255,42,109,0.4);
        }}
        header .date {{ color: var(--muted); font-size: 1rem; margin-top: 8px; }}
        section {{ margin-bottom: 40px; }}
        h2 {{
            font-size: 1.6rem;
            border-left: 6px solid var(--accent);
            padding-left: 14px;
            margin: 30px 0 18px;
            color: #fff;
        }}
        .highlight {{
            background: linear-gradient(135deg, #1a1a2e 0%, #2a0f1a 100%);
            border: 1px solid #331122;
            border-radius: 14px;
            padding: 24px;
        }}
        .highlight h3 {{ margin-top: 0; color: var(--accent); font-size: 1.4rem; }}
        .links {{ margin-top: 12px; }}
        .links a {{
            display: inline-block;
            margin-right: 14px;
            background: rgba(255,255,255,0.08);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.9rem;
            color: #4fc3f7;
            text-decoration: none;
        }}
        .links a:hover {{ text-decoration: underline; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 18px;
        }}
        .card {{
            background: var(--card);
            border-radius: 12px;
            padding: 18px;
            border: 1px solid #2a2a3e;
            transition: transform .2s;
        }}
        .card:hover {{ transform: translateY(-4px); border-color: var(--accent); }}
        .card h4 {{ margin: 0 0 8px; color: #fff; font-size: 1.1rem; }}
        .card .artist {{ color: var(--accent); font-size: 0.9rem; margin-bottom: 6px; }}
        .card p {{ font-size: 0.95rem; color: var(--muted); margin: 0 0 10px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #2a2a3e;
        }}
        th {{ color: var(--accent); font-weight: 700; }}
        footer {{
            text-align: center;
            padding: 20px;
            color: var(--muted);
            font-size: 0.85rem;
            border-top: 1px solid #2a2a3e;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>JPOP流行報</h1>
            <div class="date">{date_info['display_date']} · 第{date_info['week_number']}期</div>
        </header>
        
        {content}
        
        <footer>
            Issue Date: {date_info['date_str']} · All links and info accurate as of issue date
        </footer>
    </div>
</body>
</html>"""
    
    return template

def main():
    """主函數"""
    print("=" * 50)
    print("JPOP流行報 - LLM 自動生成")
    print("=" * 50)
    
    # 取得日期資訊
    date_info = get_date_info()
    print(f"\n日期：{date_info['display_date']}")
    print(f"期數：第 {date_info['week_number']} 期")
    
    # 生成內容
    print("\n正在使用 LLM 生成內容...")
    content = generate_content(date_info)
    
    if not content:
        print("生成失敗！")
        sys.exit(1)
    
    # 生成完整 HTML
    print("正在生成 HTML...")
    html = generate_html(content, date_info)
    
    # 儲存檔案
    output_dir = OUTPUT_DIR / date_info['date_str']
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "index.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ 已儲存：{output_file}")
    print(f"檔案大小：{len(html)} 字元")
    
    # 複製到 GitHub repo
    repo_dir = Path("/tmp/ebooksforme")
    repo_output_dir = repo_dir / "newspaper" / "jpop" / date_info['date_str']
    repo_output_dir.mkdir(parents=True, exist_ok=True)
    
    import shutil
    shutil.copy2(output_file, repo_output_dir / "index.html")
    print(f"✅ 已複製到：{repo_output_dir / 'index.html'}")
    
    # Git 提交
    print("\n正在 Git 提交...")
    os.chdir(repo_dir)
    os.system("git add -A")
    os.system(f'git commit -m "JPOP流行報: {date_info["date_str"]} 自動生成" || echo "無變更需要提交"')
    os.system("git push")
    
    print("\n" + "=" * 50)
    print("✅ 完成！")
    print(f"URL: https://julianshen.github.io/ebooksforme/newspaper/jpop/{date_info['date_str']}/")
    print("=" * 50)

if __name__ == "__main__":
    main()
