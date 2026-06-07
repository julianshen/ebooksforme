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
    """構建 LLM prompt — 嵌入真實數據，只讓 LLM 格式化 HTML"""
    
    prompt = f"""你是 JPOP流行報 的編輯系統。請根據以下提供的真實數據生成 HTML 週報。

## 日期資訊
- 報紙日期：{date_info['display_date']}
- 第 {date_info['week_number']} 期

## 真實數據（請直接使用以下數據，不要自己編造）

### Highlight Artist: Ado
- 真實簡介：Ado 是日本新生代最具代表性的歌い手（歌手），2020 年以〈うっせぇわ〉一鳴驚人。2026年6月宣布與 Giga × TeddyLoid 再度聯手推出新曲〈モンストロ（Monstruo）〉作為真人版電影《BLUE LOCK》主題歌，預計8月7日公開。7月將在日產體育場舉辦首次體育館級演唱會「Ado STADIUM LIVE 2026『Ao』」。
- Spotify: https://open.spotify.com/artist/6mEQK9m2krja6X1cfsAjfl
- YouTube: https://www.youtube.com/channel/UCln9P4Qm3-EAY4aiEPmRwEA
- Official: https://www.universal-music.co.jp/ado/

### 最新歌曲（使用以下真實資料）

1. モンストロ (Monstruo) — Ado
   真人電影《BLUE LOCK》主題歌。Giga × TeddyLoid 繼〈踊〉〈唱〉後再次聯手，拉丁節奏燃燒鬥志。
   YouTube: https://www.youtube.com/watch?v=bq28BNi60S0

2. Crunchy — iri
   6月5日配信。デビュー10周年イヤー第2弾！澤村一平(SANABAGUN.)等參與製作。
   Spotify: https://open.spotify.com/track/3micqfC9Do9RNjfKXrgXJn
   YouTube: https://www.youtube.com/watch?v=pxzvCLs5cWo

3. FUNKY SUMMER — 僕が見たかった青空
   6月3日發行第8張單曲表題曲。夏日清爽流行曲風。

4. Fright — Creepy Nuts
   TBS系火曜ドラマ「時すでにおスシ!?」主題歌。Coachella演出、北美巡迴中。

5. THE BOOK for, — YOASOBI
   第4張EP，THE BOOK系列完結篇。收錄〈Biri-Biri〉〈Heart Beat〉等，6月26日發行。
   官網: https://www.yoasobi-music.jp/news/583459

### 音樂新聞（使用以下真實連結）

1. Ado新曲「モンストロ」が実写映画『ブルーロック』主題歌に — Real Sound
   https://realsound.jp/2026/06/post-2415892.html

2. YOASOBI、4th EP『THE BOOK for,』6月26日リリース — THE FIRST TIMES
   https://www.thefirsttimes.jp/news/0000811583/

3. Reol、横浜アリーナ公演を収めたライブ映像作品を6月3日リリース — Billboard JAPAN
   https://www.billboard-japan.com/d_news/detail/159452

4. iri、デビュー10周年イヤー第2弾シングル「Crunchy」配信リリース — 音楽ナタリー
   https://natalie.mu/music/news/674681

5. 菊池桃子、約2年ぶりの新曲リリースを発表 — 音楽ナタリー
   https://natalie.mu/music/news/674694

### 日本演唱會
- Ado STADIUM LIVE 2026「Ao」— 2026年7月、日産スタジアム
- iri 10th Anniversary LIVE "Period" — 2026/10/22、ぴあアリーナMM
- Creepy Nuts NORTH AMERICA TOUR 2026 — 夏季

### 台灣演唱會
（目前尚無已確認之JPOP歌手台灣公演資訊）

## HTML 格式要求
請生成 5 個 <section> 標籤的 HTML，使用以下 CSS 類名：
- section, highlight, song-grid, song-card, song-title, song-artist, song-links
- news-grid, news-card, news-title, news-source
- concert-table
- links (for highlight artist links)

輸出時直接給 section 內容即可，不要外層 html/head/body 包裝。
使用繁體中文，歌曲名保留日文原文。
"""
    
    return prompt

def call_openai(prompt):
    """呼叫 OpenAI API，若配額不足則自動切換至 OpenRouter"""
    openai_key = os.environ.get("OPENAI_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    
    # 優先使用 OpenAI
    if openai_key:
        print("嘗試使用 OpenAI API...")
        try:
            client = openai.OpenAI(api_key=openai_key)
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
            error_str = str(e)
            if "429" in error_str or "insufficient_quota" in error_str or "quota" in error_str.lower():
                print(f"OpenAI 配額不足 (429)，嘗試切換至 OpenRouter...")
            else:
                print(f"OpenAI API 錯誤：{e}")
                return None
    
    # 備用：OpenRouter
    if openrouter_key:
        print("嘗試使用 OpenRouter API...")
        try:
            client = openai.OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
            response = client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "你是專業的日本流行音樂編輯。請用繁體中文生成 JPOP 週報的 HTML 內容。所有數據必須真實，連結必須可點擊。Spotify 連結必須是 track 連結（不是 artist）。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=8000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenRouter API 錯誤：{e}")
            return None
    
    print("未設定 OPENAI_API_KEY 或 OPENROUTER_API_KEY")
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
    
    # 儲存檔案到 GitHub repo
    repo_dir = Path("/tmp/ebooksforme")
    output_dir = repo_dir / "newspaper" / "jpop" / date_info['date_str']
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "index.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ 已儲存：{output_file}")
    print(f"檔案大小：{len(html)} 字元")
    
    print("\n" + "=" * 50)
    print("✅ 完成！")
    print(f"URL: https://julianshen.github.io/ebooksforme/newspaper/jpop/{date_info['date_str']}/")
    print("=" * 50)

if __name__ == "__main__":
    main()
