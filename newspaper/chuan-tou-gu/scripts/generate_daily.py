#!/usr/bin/env python3
"""
川投顧日報 - 每日自動生成腳本
使用 LLM 生成川普風格的美股投資日報
每日 11:00 執行
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

# 設定目錄
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR
SCRIPT_DIR = Path(__file__).parent

def get_date_str():
    """取得今日日期字串"""
    now = datetime.now()
    # 如果是週末，使用上個交易日（週五）
    if now.weekday() == 5:  # 週六
        now = now - timedelta(days=1)
    elif now.weekday() == 6:  # 週日
        now = now - timedelta(days=2)
    return now.strftime("%Y-%m-%d")

def get_display_date():
    """取得顯示用日期"""
    now = datetime.now()
    if now.weekday() == 5:
        now = now - timedelta(days=1)
    elif now.weekday() == 6:
        now = now - timedelta(days=2)
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return f"{now.year}年{now.month}月{now.day}日 {weekdays[now.weekday()]}"

def get_prev_date_str():
    """取得前一個交易日日期"""
    now = datetime.now()
    if now.weekday() == 0:  # 週一，上個交易日是週五
        prev = now - timedelta(days=3)
    elif now.weekday() == 5:  # 週六
        prev = now - timedelta(days=1)
    elif now.weekday() == 6:  # 週日
        prev = now - timedelta(days=2)
    else:
        prev = now - timedelta(days=1)
    return prev.strftime("%Y-%m-%d")

def fetch_market_data():
    """取得市場數據（使用 yfinance 或 API）"""
    try:
        import yfinance as yf
        
        # 取得大盤數據
        tickers = {
            "^GSPC": "S&P 500",
            "^DJI": "道瓊工業",
            "^IXIC": "納斯達克",
            "^RUT": "羅素2000",
            "^VIX": "VIX",
            "^TNX": "10年期公債"
        }
        
        market_data = {}
        for symbol, name in tickers.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")
                if len(hist) >= 2:
                    latest = hist.iloc[-1]
                    prev = hist.iloc[-2]
                    change = latest["Close"] - prev["Close"]
                    change_pct = (change / prev["Close"]) * 100
                    market_data[name] = {
                        "value": round(latest["Close"], 2),
                        "change": round(change, 2),
                        "change_pct": round(change_pct, 2)
                    }
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
                continue
        
        # 取得熱門股票數據
        stocks = ["NVDA", "TSLA", "AAPL", "META", "PLTR", "DJT", "AVGO", "AMD", "MU"]
        stock_data = {}
        for symbol in stocks:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")
                info = ticker.info
                if len(hist) >= 2:
                    latest = hist.iloc[-1]
                    prev = hist.iloc[-2]
                    change = latest["Close"] - prev["Close"]
                    change_pct = (change / prev["Close"]) * 100
                    stock_data[symbol] = {
                        "name": info.get("longName", symbol),
                        "price": round(latest["Close"], 2),
                        "change": round(change, 2),
                        "change_pct": round(change_pct, 2),
                        "volume": int(latest.get("Volume", 0) or 0)
                    }
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
                continue
        
        return {"market": market_data, "stocks": stock_data}
    except ImportError:
        print("yfinance not installed, using fallback data")
        return None

def generate_llm_content(market_data, date_str, display_date):
    """使用 LLM 生成日報內容"""
    
    # 構建 prompt
    prompt = f"""你是一位以川普說話風格聞名的投資顧問「川投顧」。請生成一份美股投資日報，日期為 {display_date}。

## 角色設定
- 你是川投顧，說話風格模仿川普：使用「偉大」、「沒有人見過」、「相信我」、「他們錯了」、「讓美國再次偉大」等詞彙
- 你是專業投資分析師，分析要專業但語氣要像川普
- 用繁體中文撰寫
- 每個段落都要帶有川普的個人風格

## 今日市場數據（真實數據）
{json.dumps(market_data, ensure_ascii=False, indent=2) if market_data else "請根據今日實際市場狀況撰寫"}

## 需要包含的內容

### 1. 大盤概況
- S&P 500、道瓊、納斯達克、羅素2000、VIX、10年期公債收益率
- 川普風格點評

### 2. 板塊走勢
- 主要板塊漲跌（科技、金融、醫療保健、能源、通訊服務、非必需消費、必需消費、工業、原材料、公用事業、房地產）
- 資金動向分析

### 3. 熱門股票
- NVDA、TSLA、AAPL、META、PLTR、DJT、AVGO、AMD、MU 等
- 每隻股票要有：價格、漲跌幅、成交量、簡短分析
- 提到相關新聞

### 4. 川投顧語錄
- 川普在 Truth Social / X / 白宮記者會的財經相關發言
- 附原始連結（如果有的話）

### 5. 重點財經新聞（3-4則）
- 來自 Yahoo Finance / CNBC / Bloomberg / Reuters
- 每則新聞要有：標題、摘要、相關股票小卡、來源連結
- 新聞主題：就業數據、聯準會政策、AI股動態、地緣政治、財報等

### 6. 社群熱議
- X (Twitter)、Reddit (r/wallstreetbets)、Truth Social 的熱門話題
- 熱度指標、討論數、相關股票

### 7. 財報精選
- 最近一週重要財報（NVDA、AVGO、DJT 等）
- 營收、EPS、展望

### 8. DJT 持股與內幕交易
- DJT 股價、總股本、市值（請使用上方提供的真實數據）
- 川投顧點評

### 9. 13F 機構持倉
- Berkshire Hathaway 等機構的最新持倉變化

### 10. 精選分析
- 本週市場總結
- 下週展望
- 投資建議（減碼/觀察/防禦/避險/避開）
- 風險提醒

## 輸出格式
請輸出完整的 HTML 檔案內容（只需要 `<main class="content">` 到 `</main>` 之間的內容，不需要 head 和 body 標籤）。

使用以下 CSS class：
- section: 每個大區塊
- section-header: 區塊標題列
- section-title: 標題
- section-meta: 副標題/來源
- market-grid / market-card: 大盤數據卡片
- sector-grid / sector-item: 板塊數據
- stock-grid / stock-card: 股票卡片
- news-grid / news-card: 新聞卡片
- trend-item / trend-x / trend-reddit / trend-truth: 社群熱議
- filing-table: 表格
- analysis-box: 分析框
- trump-quote: 川普語錄框
- up / down: 漲跌顏色
- data-source: 資料來源註解

新聞卡片標籤 class：tag-trump / tag-market / tag-earnings / tag-news

請確保所有數據都是真實的，新聞有明確來源連結。
"""

    # 呼叫 LLM API（直接呼叫，不使用 subprocess）
    try:
        # 優先使用 OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        
        # 嘗試 OpenAI
        if openai_key:
            try:
                import openai
                print("使用 OpenAI API...")
                client = openai.OpenAI(api_key=openai_key, timeout=120)
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=8000
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"OpenAI failed: {e}")
        
        # 嘗試 Anthropic
        if anthropic_key:
            try:
                import anthropic
                print("使用 Anthropic API...")
                client = anthropic.Anthropic(api_key=anthropic_key)
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            except Exception as e:
                print(f"Anthropic failed: {e}")
        
        # 嘗試 OpenRouter
        if openrouter_key:
            try:
                import openai as openai_sdk
                print("使用 OpenRouter API...")
                client = openai_sdk.OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1", timeout=120)
                response = client.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=8000
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"OpenRouter failed: {e}")
        
        print("All LLM providers failed: no API key available")
        return None
    except Exception as e:
        print(f"Error generating LLM content: {e}")
        return None

def generate_html_template(content, date_str, display_date):
    """生成完整 HTML 模板"""
    
    template = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>川投顧日報 - {date_str}</title>
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
                    <span>📅 {display_date}</span>
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
            <p>📰 《川投顧日報》{date_str} · {display_date}</p>
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
    date_str = get_date_str()
    display_date = get_display_date()
    
    print(f"生成川投顧日報：{date_str}")
    
    # 取得市場數據
    market_data = fetch_market_data()
    
    # 生成 LLM 內容
    llm_content = generate_llm_content(market_data, date_str, display_date)
    
    if not llm_content:
        print("LLM 生成失敗，使用模板內容")
        # 使用預設模板
        llm_content = generate_fallback_content(date_str, display_date)
    
    # 生成完整 HTML
    html = generate_html_template(llm_content, date_str, display_date)
    
    # 儲存檔案
    output_path = OUTPUT_DIR / date_str / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"已儲存：{output_path}")
    
    # 更新最新連結
    latest_link = OUTPUT_DIR / "latest.html"
    latest_link.write_text(f'<meta http-equiv="refresh" content="0; url={date_str}/">', encoding="utf-8")
    
    return output_path

def generate_fallback_content(date_str, display_date):
    """生成預設內容（當 LLM 失敗時使用）"""
    return f"""            <section class="section" id="market">
                <div class="section-header">
                    <div class="section-title">📊 大盤概況</div>
                    <div class="section-meta">數據來源：Yahoo Finance · {display_date}收盤</div>
                </div>
                <div class="market-grid">
                    <div class="market-card">
                        <div class="market-name">S&P 500</div>
                        <div class="market-value">—</div>
                        <div class="market-change">數據更新中</div>
                    </div>
                </div>
                <p>請稍後重新整理頁面獲取最新數據。</p>
            </section>"""

if __name__ == "__main__":
    main()
