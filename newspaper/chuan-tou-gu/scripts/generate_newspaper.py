#!/usr/bin/env python3
"""
川投顧日報 - HTML 生成腳本
讀取 collect_data.py 產生的 JSON，用 LLM 翻譯新聞 + 生成分析
"""

import json
import os
import random
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# 設定目錄
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR
OUTPUT_DIR.mkdir(exist_ok=True)


def load_data(date_str):
    """載入 JSON 資料"""
    data_path = DATA_DIR / f"{date_str}.json"
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def call_llm_translate_news(news_list, max_items=10):
    """使用 agy CLI 翻譯新聞為繁體中文"""
    if not news_list:
        return []

    # 準備要翻譯的內容
    items_to_translate = news_list[:max_items]

    # 構建 prompt
    news_text = "\n\n".join([
        f"[{i+1}] 來源: {item['source']}\n標題: {item['title']}\n"
        f"摘要: {item.get('description', '')}"[:300]
        for i, item in enumerate(items_to_translate)
    ])

    prompt = f"""你是一位專業財經新聞編輯。請將以下英文財經新聞翻譯成繁體中文。

要求：
1. 標題要簡潔有力，符合台灣新聞風格
2. 摘要要翻譯成流暢的繁體中文（100字以內）
3. 保留原文連結和來源
4. 人名、公司名、股票代號保持原文
5. 數字、百分比、金額保持不變
6. 輸出格式必須是 JSON 陣列

新聞內容：
{news_text}

請輸出以下格式的 JSON（只輸出 JSON，不要其他文字）：
[
  {{
    "title_zh": "中文標題",
    "summary_zh": "中文摘要",
    "title_en": "原文標題",
    "url": "原文連結",
    "source": "來源"
  }}
]
"""

    try:
        # 使用 agy CLI
        result = subprocess.run(
            ["agy", "--print", "--model", "Claude Opus 4.6 (Thinking)"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            print(f"LLM 翻譯失敗: {result.stderr}")
            return fallback_news(items_to_translate)

        # 解析 JSON
        output = result.stdout.strip()
        # 尋找 JSON 部分
        json_start = output.find("[")
        json_end = output.rfind("]")
        if json_start >= 0 and json_end > json_start:
            json_str = output[json_start:json_end+1]
            translated = json.loads(json_str)
            return translated
        else:
            print("LLM 輸出無法解析為 JSON")
            return fallback_news(items_to_translate)

    except subprocess.TimeoutExpired:
        print("LLM 翻譯超時")
        return fallback_news(items_to_translate)
    except Exception as e:
        print(f"LLM 翻譯錯誤: {e}")
        return fallback_news(items_to_translate)


def fallback_news(news_list):
    """當 LLM 失敗時，回傳原文"""
    return [
        {
            "title_zh": item["title"],
            "summary_zh": item.get("description", "")[:200] or "（無摘要）",
            "title_en": item["title"],
            "url": item["url"],
            "source": item["source"]
        }
        for item in news_list
    ]


def call_llm_daily_analysis(market_data):
    """使用 agy CLI 生成每日市場分析"""
    indices = market_data.get("market_indices", [])
    sectors = market_data.get("sector_performance", [])
    hot_stocks = market_data.get("hot_stocks", [])

    # 構建市場數據摘要
    indices_text = "\n".join([
        f"- {i['name']} ({i['symbol']}): {i['price']} ({i['change_pct']}%)"
        for i in indices
    ])

    sectors_text = "\n".join([
        f"- {s['name']}: {s['change_pct']}%"
        for s in sectors[:5]
    ])

    stocks_text = "\n".join([
        f"- {s['symbol']} ({s['name']}): ${s['price']} ({s['change_pct']}%)"
        for s in hot_stocks[:5]
    ])

    prompt = f"""你是一位以川普說話風格聞名的投資顧問「川投顧」。請根據以下市場數據生成一段每日市場分析。

## 市場數據

### 大盤指數
{indices_text}

### 領漲/領跌板塊
{sectors_text}

### 熱門股票
{stocks_text}

## 要求

1. 用繁體中文撰寫
2. 語氣模仿川普：使用「偉大」、「沒有人見過」、「相信我」、「他們錯了」、「讓美國再次偉大」等詞彙
3. 分析要基於真實數據，不能編造
4. 長度約 200-300 字
5. 包含對大盤的點評、對熱門股的看法、以及對投資人的建議
6. 語氣要幽默但分析要專業

請直接輸出分析文字，不要有任何格式標記。
"""

    try:
        result = subprocess.run(
            ["agy", "--print", "--model", "Claude Opus 4.6 (Thinking)"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            print(f"LLM 分析失敗: {result.stderr}")
            return fallback_analysis()

        analysis = result.stdout.strip()
        # 移除可能的引號或格式標記
        analysis = analysis.strip('"').strip("'")
        return analysis

    except subprocess.TimeoutExpired:
        print("LLM 分析超時")
        return fallback_analysis()
    except Exception as e:
        print(f"LLM 分析錯誤: {e}")
        return fallback_analysis()


def fallback_analysis():
    """當 LLM 失敗時的回退分析"""
    return "今日市場波動較大，投資人應保持冷靜，關注基本面良好的優質股票。記住：低買高賣是永恆的真理。"


def get_trend_emoji(change_pct):
    """取得趨勢表情"""
    if change_pct > 3:
        return "🚀"
    elif change_pct > 1:
        return "📈"
    elif change_pct > 0:
        return "🟢"
    elif change_pct > -1:
        return "🔴"
    elif change_pct > -3:
        return "📉"
    else:
        return "💥"


def generate_html(data, translated_news, daily_analysis):
    """生成 HTML 日報"""
    date_info = data["date_info"]
    indices = data.get("market_indices", [])
    hot_stocks = data.get("hot_stocks", [])
    sectors = data.get("sector_performance", [])
    earnings = data.get("earnings", [])
    futures = data.get("futures", [])

    # 隨機選封面
    cover_num = random.randint(1, 5)

    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>川投顧日報 - {date_info["display"]}</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a2e;
            --bg-card-hover: #252540;
            --text-primary: #f0f0f5;
            --text-secondary: #a0a0b0;
            --text-muted: #6a6a7a;
            --accent-gold: #d4af37;
            --accent-gold-light: #f0d878;
            --accent-red: #ff4444;
            --accent-green: #00c853;
            --border: #2a2a3a;
            --border-hover: #3a3a50;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Noto Sans TC', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }}

        /* 封面 */
        .cover {{
            position: relative;
            height: 500px;
            background: linear-gradient(135deg, #1a1a2e 0%, #0f0f1a 50%, #1a0a0a 100%);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            overflow: hidden;
        }}

        .cover::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: url('images/cover-{cover_num}.png') center/cover;
            opacity: 0.4;
        }}

        .cover-content {{
            position: relative;
            z-index: 1;
        }}

        .cover h1 {{
            font-size: 3.5rem;
            font-weight: 900;
            color: var(--accent-gold);
            text-shadow: 0 0 40px rgba(212, 175, 55, 0.5);
            margin-bottom: 0.5rem;
        }}

        .cover .subtitle {{
            font-size: 1.3rem;
            color: var(--text-secondary);
            margin-bottom: 1rem;
        }}

        .cover .date {{
            font-size: 1rem;
            color: var(--text-muted);
        }}

        .cover .tagline {{
            margin-top: 1.5rem;
            padding: 0.5rem 2rem;
            background: rgba(212, 175, 55, 0.15);
            border: 1px solid rgba(212, 175, 55, 0.3);
            border-radius: 50px;
            color: var(--accent-gold-light);
            font-size: 0.95rem;
        }}

        /* 容器 */
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}

        /* 區塊標題 */
        .section {{
            margin-bottom: 3rem;
        }}

        .section-title {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid var(--border);
        }}

        .section-title .icon {{
            font-size: 1.8rem;
        }}

        /* 大盤指數卡片 */
        .indices-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}

        .index-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s;
        }}

        .index-card:hover {{
            border-color: var(--border-hover);
            transform: translateY(-4px);
        }}

        .index-card .name {{
            font-size: 0.9rem;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
        }}

        .index-card .price {{
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}

        .index-card .change {{
            font-size: 1rem;
            font-weight: 600;
        }}

        .positive {{ color: var(--accent-green); }}
        .negative {{ color: var(--accent-red); }}

        /* 期貨區塊 */
        .futures-bar {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            margin-bottom: 2rem;
        }}

        .future-pill {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 50px;
            padding: 0.5rem 1rem;
            font-size: 0.9rem;
        }}

        /* 板塊表格 */
        .sector-table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .sector-table th {{
            text-align: left;
            padding: 1rem;
            color: var(--text-muted);
            font-weight: 500;
            border-bottom: 2px solid var(--border);
        }}

        .sector-table td {{
            padding: 1rem;
            border-bottom: 1px solid var(--border);
        }}

        .sector-table tr:hover td {{
            background: var(--bg-card-hover);
        }}

        /* 熱門股票 */
        .stocks-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1rem;
        }}

        .stock-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s;
        }}

        .stock-card:hover {{
            border-color: var(--accent-gold);
        }}

        .stock-info .symbol {{
            font-weight: 700;
            font-size: 1.1rem;
        }}

        .stock-info .name {{
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        .stock-price {{
            text-align: right;
        }}

        .stock-price .price {{
            font-size: 1.2rem;
            font-weight: 700;
        }}

        /* 新聞 */
        .news-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}

        .news-item {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            transition: all 0.3s;
        }}

        .news-item:hover {{
            border-color: var(--border-hover);
        }}

        .news-item .source {{
            display: inline-block;
            padding: 0.2rem 0.6rem;
            background: rgba(212, 175, 55, 0.15);
            color: var(--accent-gold);
            border-radius: 4px;
            font-size: 0.75rem;
            margin-bottom: 0.5rem;
        }}

        .news-item .title-zh {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            line-height: 1.5;
        }}

        .news-item .title-zh a {{
            color: var(--text-primary);
            text-decoration: none;
        }}

        .news-item .title-zh a:hover {{
            color: var(--accent-gold);
        }}

        .news-item .summary-zh {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
            line-height: 1.6;
        }}

        .news-item .title-en {{
            font-size: 0.8rem;
            color: var(--text-muted);
            font-style: italic;
        }}

        /* 財報 */
        .earnings-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 0.75rem;
        }}

        .earnings-item {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }}

        .earnings-item .symbol {{
            font-weight: 700;
            color: var(--accent-gold);
            font-size: 1.1rem;
        }}

        .earnings-item .name {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin: 0.25rem 0;
        }}

        .earnings-item .eps {{
            font-size: 0.9rem;
            color: var(--text-secondary);
        }}

        .earnings-item .reported {{
            font-size: 0.85rem;
            color: var(--accent-green);
            margin-top: 0.25rem;
        }}

        /* 川普分析區塊 */
        .trump-analysis {{
            background: linear-gradient(135deg, rgba(212, 175, 55, 0.1), rgba(139, 69, 19, 0.1));
            border: 2px solid var(--accent-gold);
            border-radius: 20px;
            padding: 2rem;
            margin-bottom: 3rem;
        }}

        .trump-analysis h2 {{
            color: var(--accent-gold);
            font-size: 1.5rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .trump-analysis .content {{
            line-height: 1.8;
            color: var(--text-secondary);
            font-size: 1.05rem;
        }}

        .trump-analysis .content p {{
            margin-bottom: 1rem;
        }}

        /* 頁尾 */
        footer {{
            text-align: center;
            padding: 3rem 2rem;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.9rem;
        }}

        footer .disclaimer {{
            margin-top: 1rem;
            font-size: 0.8rem;
            opacity: 0.7;
        }}

        /* 響應式 */
        @media (max-width: 768px) {{
            .cover h1 {{ font-size: 2.5rem; }}
            .container {{ padding: 1rem; }}
            .indices-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <!-- 封面 -->
    <div class="cover">
        <div class="cover-content">
            <h1>🦅 川投顧日報</h1>
            <div class="subtitle">TRUMP FINANCIAL ADVISORY</div>
            <div class="date">{date_info["display"]} {date_info["weekday"]}</div>
            <div class="tagline">"讓美國再次偉大，讓你的投資組合也偉大！"</div>
        </div>
    </div>

    <div class="container">
        <!-- 川普分析 -->
        <div class="trump-analysis">
            <h2>🎯 川投顧每日金句</h2>
            <div class="content">
                <p>{daily_analysis}</p>
            </div>
        </div>

        <!-- 期貨 -->
        {generate_futures_html(futures)}

        <!-- 大盤指數 -->
        <section class="section">
            <h2 class="section-title"><span class="icon">📊</span> 美股大盤</h2>
            <div class="indices-grid">
'''

    # 大盤指數
    for idx in indices:
        emoji = get_trend_emoji(idx.get("change_pct", 0))
        trend_class = "positive" if idx.get("change_pct", 0) >= 0 else "negative"
        sign = "+" if idx.get("change_pct", 0) >= 0 else ""

        html += f'''
                <div class="index-card">
                    <div class="name">{idx["name"]} ({idx["symbol"]})</div>
                    <div class="price">{idx.get("price", "N/A")}</div>
                    <div class="change {trend_class}">{emoji} {sign}{idx.get("change", 0):.2f} ({sign}{idx.get("change_pct", 0):.2f}%)</div>
                </div>
'''

    html += '''
            </div>
        </section>

        <!-- 板塊表現 -->
        <section class="section">
            <h2 class="section-title"><span class="icon">🏭</span> 板塊表現</h2>
            <table class="sector-table">
                <thead>
                    <tr>
                        <th>排名</th>
                        <th>板塊</th>
                        <th>漲跌幅</th>
                        <th>價格</th>
                    </tr>
                </thead>
                <tbody>
'''

    for i, sector in enumerate(sectors[:10], 1):
        trend_class = "positive" if sector.get("change_pct", 0) >= 0 else "negative"
        sign = "+" if sector.get("change_pct", 0) >= 0 else ""

        html += f'''
                    <tr>
                        <td>{i}</td>
                        <td>{sector["name"]} ({sector["symbol"]})</td>
                        <td class="{trend_class}">{sign}{sector.get("change_pct", 0):.2f}%</td>
                        <td>${sector.get("price", 0):.2f}</td>
                    </tr>
'''

    html += '''
                </tbody>
            </table>
        </section>

        <!-- 熱門股票 -->
        <section class="section">
            <h2 class="section-title"><span class="icon">🔥</span> 熱門股票</h2>
            <div class="stocks-grid">
'''

    for stock in hot_stocks[:12]:
        trend_class = "positive" if stock.get("change_pct", 0) >= 0 else "negative"
        sign = "+" if stock.get("change_pct", 0) >= 0 else ""

        html += f'''
                <div class="stock-card">
                    <div class="stock-info">
                        <div class="symbol">{stock["symbol"]}</div>
                        <div class="name">{stock.get("name", "")}</div>
                    </div>
                    <div class="stock-price">
                        <div class="price">${stock.get("price", 0):.2f}</div>
                        <div class="change {trend_class}">{sign}{stock.get("change_pct", 0):.2f}%</div>
                    </div>
                </div>
'''

    html += '''
            </div>
        </section>

        <!-- 財經新聞 -->
        <section class="section">
            <h2 class="section-title"><span class="icon">📰</span> 財經新聞</h2>
            <div class="news-list">
'''

    # 顯示翻譯後的新聞
    for item in translated_news[:10]:
        html += f'''
                <div class="news-item">
                    <span class="source">{item.get("source", "News")}</span>
                    <div class="title-zh"><a href="{item["url"]}" target="_blank">{item.get("title_zh", item.get("title_en", ""))}</a></div>
                    <div class="summary-zh">{item.get("summary_zh", "")}</div>
                    <div class="title-en">{item.get("title_en", "")}</div>
                </div>
'''

    html += '''
            </div>
        </section>

        <!-- 今日財報 -->
        <section class="section">
            <h2 class="section-title"><span class="icon">📈</span> 今日財報焦點</h2>
            <div class="earnings-grid">
'''

    for earn in earnings[:12]:
        reported_html = ""
        if earn.get("reported_eps"):
            reported_html = f'<div class="reported">實際 EPS: {earn["reported_eps"]}'
            if earn.get("surprise_pct"):
                reported_html += f' ({earn["surprise_pct"]})'
            reported_html += '</div>'

        html += f'''
                <div class="earnings-item">
                    <div class="symbol">{earn["symbol"]}</div>
                    <div class="name">{earn.get("name", "")}</div>
                    <div class="eps">EPS 預估: {earn.get("eps_estimate", "-") or "-"}</div>
                    {reported_html}
                </div>
'''

    html += '''
            </div>
        </section>
    </div>

    <footer>
        <p>川投顧日報 | 自動生成於 ''' + datetime.now().strftime("%Y-%m-%d %H:%M") + '''</p>
        <p class="disclaimer">⚠️ 本報僅供參考，不構成投資建議。投資有風險，決策需謹慎。</p>
    </footer>
</body>
</html>
'''

    return html


def generate_futures_html(futures):
    """生成期貨 HTML"""
    if not futures:
        return ""

    html = '<section class="section">\n'
    html += '<h2 class="section-title"><span class="icon">📉</span> 美股期貨</h2>\n'
    html += '<div class="futures-bar">\n'

    for f in futures:
        trend_class = "positive" if f.get("change_pct", 0) >= 0 else "negative"
        sign = "+" if f.get("change_pct", 0) >= 0 else ""
        html += f'<div class="future-pill {trend_class}">{f["name"]}: {f["price"]} ({sign}{f["change_pct"]:.2f}%)</div>\n'

    html += '</div>\n</section>\n'
    return html


def main():
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"=== 川投顧日報生成: {date_str} ===")

    # 載入資料
    data = load_data(date_str)

    # 合併所有新聞，優先有 description 的
    all_news = []
    for source, items in data.get("news", {}).items():
        all_news.extend(items)

    # 排序：有 description 的優先
    all_news.sort(key=lambda x: (not x.get("has_description", False), x.get("source", "")))

    # 去重（依標題）
    seen_titles = set()
    unique_news = []
    for item in all_news:
        title = item.get("title", "")
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_news.append(item)

    print(f"去重後新聞: {len(unique_news)} 則")

    # 選擇要翻譯的新聞（優先有 description 的）
    news_to_translate = unique_news[:15]

    # 使用 LLM 翻譯新聞
    print("正在翻譯新聞...")
    translated_news = call_llm_translate_news(news_to_translate, max_items=10)

    # 使用 LLM 生成每日分析
    print("正在生成每日分析...")
    daily_analysis = call_llm_daily_analysis(data)

    # 生成 HTML
    html = generate_html(data, translated_news, daily_analysis)

    # 儲存
    date_info = data["date_info"]
    date_dir = OUTPUT_DIR / date_info["date_str"]
    output_path = date_dir / "index.html"
    date_dir.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"已生成: {output_path}")

    # 複製封面圖片到日期目錄
    covers_dir = BASE_DIR / "covers"
    images_dir = date_dir / "images"
    images_dir.mkdir(exist_ok=True)
    for i in range(1, 6):
        src = covers_dir / f"cover-{i}.png"
        dst = images_dir / f"cover-{i}.png"
        if src.exists():
            import shutil
            shutil.copy2(src, dst)

    # 同時儲存到最新版本
    latest_path = OUTPUT_DIR / "latest.html"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 複製封面到 latest 所在目錄（相對路徑需要）
    latest_images_dir = OUTPUT_DIR / "images"
    latest_images_dir.mkdir(exist_ok=True)
    for i in range(1, 6):
        src = covers_dir / f"cover-{i}.png"
        dst = latest_images_dir / f"cover-{i}.png"
        if src.exists():
            shutil.copy2(src, dst)

    print(f"已更新: {latest_path}")

    return output_path


if __name__ == "__main__":
    main()
