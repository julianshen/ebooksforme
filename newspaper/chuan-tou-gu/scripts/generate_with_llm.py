#!/usr/bin/env python3
"""
川投顧日報 - LLM 生成腳本
使用 OpenAI/Anthropic API 生成川普風格的美股投資日報
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
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR

def get_date_info():
    """取得日期資訊"""
    now = datetime.now()
    
    # 如果是週末，使用上個交易日
    if now.weekday() == 5:  # 週六
        market_date = now - timedelta(days=1)
    elif now.weekday() == 6:  # 週日
        market_date = now - timedelta(days=2)
    else:
        market_date = now
    
    # 前一個交易日
    if market_date.weekday() == 0:  # 週一
        prev_date = market_date - timedelta(days=3)
    else:
        prev_date = market_date - timedelta(days=1)
    
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    
    return {
        "date_str": market_date.strftime("%Y-%m-%d"),
        "display_date": f"{market_date.year}年{market_date.month}月{market_date.day}日 {weekdays[market_date.weekday()]}",
        "prev_date_str": prev_date.strftime("%Y-%m-%d"),
        "year": market_date.year,
        "month": market_date.month,
        "day": market_date.day,
        "weekday": weekdays[market_date.weekday()]
    }

def build_prompt(date_info):
    """構建 LLM prompt"""
    
    prompt = f"""你是一位以川普說話風格聞名的投資顧問「川投顧」。請生成一份美股投資日報的 HTML 內容。

## 日期資訊
- 報紙日期：{date_info['display_date']}
- 數據截至：前一交易日（{date_info['prev_date_str']}）收盤

## 角色設定
- 你是川投顧，說話風格模仿川普：使用「偉大」、「沒有人見過」、「相信我」、「他們錯了」、「讓美國再次偉大」等詞彙
- 你是專業投資分析師，分析要專業但語氣要像川普
- 用繁體中文撰寫
- 每個段落都要帶有川普的個人風格

## 重要規則
1. **所有數據必須真實**：使用前一交易日的真實收盤數據
2. **新聞必須有來源**：每則新聞都要標註來源（Yahoo Finance / CNBC / Bloomberg / Reuters）
3. **股票小卡**：每則新聞下方要有提到的股票的漲跌小卡
4. **川普語錄**：包含川普在 Truth Social / X 的真實財經相關發言
5. **DJT 持股**：必須包含川普在 DJT 的持股資訊（114,787,498 股，41.45%）

## 需要生成的內容區塊

請生成以下 10 個 section（只需要 <section> 標籤內的內容，不需要外層的 html/head/body）：

### 1. id="market" - 大盤概況
- S&P 500、道瓊、納斯達克、羅素2000、VIX、10年期公債
- 使用 market-grid + market-card 佈局
- 川投顧大盤點評（川普風格）

### 2. id="sectors" - 板塊走勢
- 11個板塊的漲跌數據
- 使用 sector-grid + sector-item 佈局
- 資金動向分析

### 3. id="stocks" - 熱門股票
- NVDA、TSLA、AAPL、META、PLTR、DJT、AVGO、AMD、MU
- 使用 stock-grid + stock-card 佈局
- 每張卡片包含：代號、價格、漲跌幅、成交量、簡短分析

### 4. id="trump" - 川投顧語錄
- 川普在 Truth Social 的真實發言（附原文和中文翻譯）
- 使用 trump-quote 樣式
- 包含發言的影響分析

### 5. id="news" - 重點財經新聞（3-4則）
- 每則新聞使用 news-card 佈局
- 包含：標籤（tag-trump/tag-market/tag-earnings/tag-news）、標題、摘要、相關股票小卡、來源連結
- 新聞主題：就業數據、聯準會、AI股、地緣政治、財報

### 6. id="social" - 社群熱議
- X、Reddit、Truth Social 的熱門話題
- 使用 trend-item 佈局
- 包含熱度指標、討論數、相關股票

### 7. id="earnings" - 財報精選
- 最近一週重要財報
- 使用 stock-grid + stock-card 佈局
- 包含營收、EPS、展望、官方連結

### 8. id="djt" - DJT 持股與內幕交易
- DJT 股價、總股本（2.77億）、市值
- 川普持股：114,787,498 股（41.45%），約 $9.49 億
- Trump Revocable Trust：114,750,000 股
- 前十大機構投資者（BlackRock 2.98%、Vanguard 2.72% 等）
- 近期內幕交易
- 川投顧 DJT 點評

### 9. id="13f" - 13F 機構持倉
- Berkshire Hathaway 等機構最新持倉變化
- 使用 filing-table 表格
- 川投顧點評

### 10. id="analysis" - 精選分析
- 本週市場總結
- 下週展望
- 投資建議（減碼/觀察/防禦/避險/避開）
- 風險提醒
- 使用 analysis-box 佈局

## CSS 類名參考
- section, section-header, section-title, section-meta
- market-grid, market-card, market-name, market-value, market-change
- sector-grid, sector-item, sector-name, sector-change, sector-up, sector-down
- stock-grid, stock-card, stock-header, stock-symbol, stock-price, stock-name, stock-stats, stock-desc
- news-grid, news-card, news-content, card-tag, tag-trump, tag-market, tag-earnings, tag-news, card-title, card-body, source-link, news-source
- trends-container, trend-item, trend-x, trend-reddit, trend-truth, trend-icon, trend-content, trend-title, trend-desc, trend-stats
- filing-table
- analysis-box
- trump-quote
- up, down
- data-source

## 輸出格式
請直接輸出 10 個 <section> 標籤的 HTML 內容，不需要其他包裝。每個 section 必須有正確的 id 屬性。

請確保：
1. 數據真實準確
2. 語氣像川普
3. 繁體中文
4. 所有新聞有來源連結
5. DJT 持股資訊準確
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
                {"role": "system", "content": "你是一位專業的投資分析師，同時模仿川普的說話風格。請用繁體中文生成美股投資日報的 HTML 內容。所有數據必須真實，新聞必須有來源。"},
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
    <title>川投顧日報 - {date_info['date_str']}</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&family=Noto+Serif+TC:wght@600;900&display=swap" rel="stylesheet">
    <style>
        :root {{
            --paper: #fefefe;
            --ink: #1a1a2e;
            --accent: #e94560;
            --accent-light: #ff6b6b;
            --gold: #f4a261;
            --green: #2ecc71;
            --red: #e74c3c;
            --blue: #3498db;
            --purple: #9b5de5;
            --gray: #6c757d;
            --light-gray: #f8f9fa;
            --trump-gold: #d4af37;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Noto Sans TC', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: var(--paper);
            line-height: 1.7;
            min-height: 100vh;
        }}
        .newspaper {{
            max-width: 1000px;
            margin: 0 auto;
            background: var(--paper);
            color: var(--ink);
            box-shadow: 0 4px 30px rgba(0,0,0,0.3);
            min-height: 100vh;
        }}
        .masthead {{
            background: linear-gradient(180deg, #1a1a2e 0%, #0f3460 100%);
            color: white;
            padding: 1.5rem 2rem;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        .masthead::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: url('../images/cover.png') center/cover;
            opacity: 0.2;
        }}
        .masthead-content {{ position: relative; z-index: 1; }}
        .tagline {{
            font-size: 0.85rem;
            letter-spacing: 0.3em;
            text-transform: uppercase;
            color: var(--trump-gold);
            margin-bottom: 0.5rem;
        }}
        .title {{
            font-family: 'Noto Serif TC', serif;
            font-size: 3.5rem;
            font-weight: 900;
            letter-spacing: 0.15em;
            text-shadow: 3px 3px 0 rgba(212,175,55,0.3);
            margin-bottom: 0.5rem;
            color: var(--trump-gold);
        }}
        .subtitle {{
            font-size: 1.1rem;
            color: rgba(255,255,255,0.9);
            letter-spacing: 0.1em;
        }}
        .issue-info {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid rgba(212,175,55,0.3);
            font-size: 0.9rem;
        }}
        .cover-section {{ position: relative; }}
        .cover-image {{
            width: 100%;
            height: 350px;
            object-fit: cover;
            display: block;
        }}
        .cover-overlay {{
            position: absolute;
            bottom: 0;
            left: 0; right: 0;
            background: linear-gradient(transparent, rgba(26,26,46,0.95));
            padding: 3rem 2rem 1.5rem;
            color: white;
        }}
        .headline {{
            font-family: 'Noto Serif TC', serif;
            font-size: 2rem;
            font-weight: 900;
            margin-bottom: 0.5rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }}
        .headline-sub {{ font-size: 1.1rem; opacity: 0.9; }}
        .nav-bar {{
            background: var(--light-gray);
            padding: 1rem 2rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            justify-content: center;
            border-bottom: 3px solid var(--trump-gold);
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .nav-bar a {{
            color: var(--ink);
            text-decoration: none;
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 700;
            transition: all 0.2s;
            border: 2px solid transparent;
        }}
        .nav-bar a:hover {{ background: var(--trump-gold); color: white; }}
        .content {{ padding: 2rem; }}
        .section {{ margin-bottom: 2.5rem; }}
        .section-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 3px solid var(--trump-gold);
        }}
        .section-title {{
            font-family: 'Noto Serif TC', serif;
            font-size: 1.6rem;
            font-weight: 900;
            flex: 1;
            color: var(--ink);
        }}
        .section-meta {{ font-size: 0.8rem; color: var(--gray); }}
        .market-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        .market-card {{
            background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
            color: white;
            padding: 1.25rem;
            border-radius: 12px;
            text-align: center;
            border: 2px solid var(--trump-gold);
        }}
        .market-name {{ font-size: 0.9rem; color: rgba(255,255,255,0.7); margin-bottom: 0.5rem; }}
        .market-value {{ font-size: 1.8rem; font-weight: 900; margin-bottom: 0.25rem; }}
        .market-change {{ font-size: 1rem; font-weight: 700; }}
        .up {{ color: var(--green); }}
        .down {{ color: var(--red); }}
        .sector-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 0.75rem;
        }}
        .sector-item {{
            background: white;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            text-align: center;
            border-left: 4px solid var(--gray);
        }}
        .sector-name {{ font-size: 0.85rem; font-weight: 700; margin-bottom: 0.3rem; }}
        .sector-change {{ font-size: 1.1rem; font-weight: 900; }}
        .sector-up {{ border-left-color: var(--green); }}
        .sector-down {{ border-left-color: var(--red); }}
        .stock-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1rem;
        }}
        .stock-card {{
            background: white;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border-top: 4px solid var(--trump-gold);
            transition: transform 0.2s;
        }}
        .stock-card:hover {{ transform: translateY(-3px); }}
        .stock-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }}
        .stock-symbol {{ font-size: 1.3rem; font-weight: 900; color: var(--ink); }}
        .stock-price {{ font-size: 1.2rem; font-weight: 700; }}
        .stock-name {{ font-size: 0.85rem; color: var(--gray); margin-bottom: 0.5rem; }}
        .stock-stats {{
            display: flex;
            gap: 1rem;
            font-size: 0.8rem;
            color: var(--gray);
        }}
        .stock-desc {{
            font-size: 0.9rem;
            color: #444;
            margin-top: 0.5rem;
            line-height: 1.6;
        }}
        .news-grid {{ display: grid; gap: 1.25rem; }}
        .news-card {{
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border-left: 4px solid var(--blue);
            transition: transform 0.2s;
        }}
        .news-card:hover {{ transform: translateY(-2px); }}
        .news-card.trump {{ border-left-color: var(--trump-gold); }}
        .news-card.earnings {{ border-left-color: var(--purple); }}
        .news-content {{ padding: 1.25rem; }}
        .card-tag {{
            display: inline-block;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
        }}
        .tag-trump {{ background: #fff3e0; color: #e65100; }}
        .tag-market {{ background: #e3f2fd; color: #1565c0; }}
        .tag-earnings {{ background: #f3e5f5; color: #7b1fa2; }}
        .tag-news {{ background: #e8f5e9; color: #2e7d32; }}
        .card-title {{
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            color: var(--ink);
        }}
        .card-body {{ font-size: 0.95rem; color: #444; line-height: 1.7; }}
        .source-link {{
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            margin-top: 0.75rem;
            font-size: 0.8rem;
            color: var(--gray);
            text-decoration: none;
        }}
        .source-link:hover {{ color: var(--accent); }}
        .news-source {{
            display: inline-block;
            font-size: 0.75rem;
            color: var(--gray);
            margin-top: 0.5rem;
            padding: 0.2rem 0.5rem;
            background: var(--light-gray);
            border-radius: 4px;
        }}
        .trump-quote {{
            background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
            color: white;
            padding: 1.5rem;
            border-radius: 16px;
            margin-bottom: 1.5rem;
            position: relative;
            border: 3px solid var(--trump-gold);
        }}
        .trump-quote::before {{
            content: '💬';
            position: absolute;
            top: -15px;
            left: 20px;
            font-size: 2rem;
            background: var(--paper);
            padding: 0 10px;
            border-radius: 50%;
        }}
        .trump-quote h3 {{
            color: var(--trump-gold);
            margin-bottom: 0.75rem;
            font-size: 1.1rem;
        }}
        .trump-quote p {{
            font-style: italic;
            line-height: 1.8;
            font-size: 1rem;
        }}
        .trump-quote .meta {{
            margin-top: 0.75rem;
            font-size: 0.8rem;
            color: rgba(255,255,255,0.7);
        }}
        .trends-container {{ display: grid; gap: 1rem; }}
        .trend-item {{
            background: white;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border-left: 4px solid;
            display: flex;
            gap: 1rem;
            align-items: flex-start;
        }}
        .trend-x {{ border-left-color: #1da1f2; }}
        .trend-reddit {{ border-left-color: #ff4500; }}
        .trend-truth {{ border-left-color: var(--trump-gold); }}
        .trend-icon {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            flex-shrink: 0;
        }}
        .trend-content {{ flex: 1; }}
        .trend-title {{ font-size: 1rem; font-weight: 700; margin-bottom: 0.3rem; }}
        .trend-desc {{ font-size: 0.9rem; color: #444; margin-bottom: 0.5rem; }}
        .trend-stats {{ font-size: 0.8rem; color: var(--gray); }}
        .filing-table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        .filing-table th {{
            background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%);
            color: white;
            padding: 1rem;
            text-align: left;
            font-size: 0.9rem;
        }}
        .filing-table td {{
            padding: 0.85rem 1rem;
            border-bottom: 1px solid #eee;
            font-size: 0.9rem;
        }}
        .filing-table tr:hover {{ background: #f8f9fa; }}
        .analysis-box {{
            background: linear-gradient(135deg, #fff9e6 0%, #fff3cd 100%);
            border: 2px solid var(--trump-gold);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }}
        .analysis-box h3 {{
            color: var(--ink);
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .analysis-box p {{ color: #444; line-height: 1.8; }}
        .footer {{
            background: var(--light-gray);
            padding: 2rem;
            text-align: center;
            border-top: 3px solid var(--trump-gold);
        }}
        .footer p {{ color: var(--gray); font-size: 0.85rem; margin-bottom: 0.5rem; }}
        .back-link {{
            display: inline-block;
            margin-top: 1rem;
            padding: 0.75rem 1.5rem;
            background: var(--trump-gold);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 700;
            transition: background 0.2s;
        }}
        .back-link:hover {{ background: #b8941f; }}
        .data-source {{
            font-size: 0.75rem;
            color: var(--gray);
            margin-top: 0.5rem;
            font-style: italic;
        }}
        @media (max-width: 600px) {{
            .title {{ font-size: 2.2rem; }}
            .headline {{ font-size: 1.4rem; }}
            .content {{ padding: 1rem; }}
            .issue-info {{ flex-direction: column; gap: 0.5rem; }}
            .nav-bar {{ padding: 0.5rem; }}
            .nav-bar a {{ font-size: 0.75rem; padding: 0.3rem 0.6rem; }}
            .market-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .stock-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="newspaper">
        <header class="masthead">
            <div class="masthead-content">
                <div class="tagline">Trump's Financial Daily Intelligence</div>
                <h1 class="title">川投顧日報</h1>
                <p class="subtitle">川普動漫化投資顧問 · 美股每日情報 · 專業分析</p>
                <div class="issue-info">
                    <span>📅 {date_info['display_date']}</span>
                    <span>🕐 數據截至前一交易日收盤</span>
                    <span>📰 川投顧出品</span>
                </div>
            </div>
        </header>
        
        <section class="cover-section">
            <img src="../images/cover.png" alt="川投顧封面" class="cover-image">
            <div class="cover-overlay">
                <h2 class="headline">川投顧：「讓美國再次偉大，讓投資人再次富有！」</h2>
                <p class="headline-sub">每日美股情報 · 專業分析 · 川普視角</p>
            </div>
        </section>
        
        <nav class="nav-bar">
            <a href="#market">大盤概況</a>
            <a href="#sectors">板塊走勢</a>
            <a href="#stocks">熱門股票</a>
            <a href="#trump">川投顧語錄</a>
            <a href="#news">財經新聞</a>
            <a href="#social">社群熱議</a>
            <a href="#earnings">財報精選</a>
            <a href="#djt">DJT持股</a>
            <a href="#13f">13F報告</a>
            <a href="#analysis">精選分析</a>
        </nav>
        
        <main class="content">
{content}
        </main>
        
        <footer class="footer">
            <p>📰 《川投顧日報》{date_info['date_str']} · {date_info['display_date']}</p>
            <p>數據來源：Yahoo Finance / CNBC / Bloomberg / Reuters / SEC EDGAR / Ape Wisdom / Truth Social</p>
            <p>⚠️ 本報僅供參考，不構成投資建議。投資有風險，入市須謹慎。</p>
            <p>🕐 每日 11:00 更新 · 川投顧與您同在，讓美國再次偉大！</p>
            <a href="/ebooksforme/" class="back-link">← 返回圖書館報架</a>
        </footer>
    </div>
</body>
</html>"""
    
    return template

def main():
    """主函數"""
    date_info = get_date_info()
    print(f"生成川投顧日報：{date_info['date_str']}")
    
    # 使用 LLM 生成內容
    content = generate_content(date_info)
    
    if not content:
        print("LLM 生成失敗")
        sys.exit(1)
    
    # 清理內容（移除可能的 markdown 代碼塊標記）
    content = re.sub(r'^```html\s*', '', content)
    content = re.sub(r'\s*```\s*$', '', content)
    
    # 生成完整 HTML
    html = generate_html(content, date_info)
    
    # 儲存檔案
    output_path = OUTPUT_DIR / date_info['date_str'] / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"已儲存：{output_path}")
    
    # 更新最新連結
    latest_link = OUTPUT_DIR / "latest.html"
    latest_link.write_text(f'<meta http-equiv="refresh" content="0; url={date_info["date_str"]}/">', encoding="utf-8")
    
    # 更新歷史列表（可選）
    update_archive(date_info)
    
    return output_path

def update_archive(date_info):
    """更新歷史列表"""
    archive_file = OUTPUT_DIR / "archive.html"
    
    # 簡單的歷史列表
    if not archive_file.exists():
        archive_content = """<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><title>川投顧日報 - 歷史存檔</title></head>
<body>
<h1>📰 川投顧日報歷史存檔</h1>
<ul>
"""
    else:
        with open(archive_file, "r", encoding="utf-8") as f:
            archive_content = f.read()
        # 移除結尾標籤
        archive_content = archive_content.replace("</ul>\n</body>\n</html>", "")
    
    # 添加新條目
    new_entry = f'  <li><a href="{date_info["date_str"]}/">{date_info["display_date"]}</a></li>\n'
    
    if new_entry not in archive_content:
        archive_content += new_entry
    
    archive_content += """</ul>
</body>
</html>"""
    
    with open(archive_file, "w", encoding="utf-8") as f:
        f.write(archive_content)

if __name__ == "__main__":
    main()
