#!/usr/bin/env python3
"""
川投顧日報 - HTML 生成腳本
讀取 collect_data.py 產生的 JSON，用 LLM 翻譯新聞 + 生成分析
"""

import json
import os
import random
import sys
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


def translate_news_with_llm(news_list, max_items=8):
    """用 LLM 翻譯新聞標題為繁體中文"""
    if not news_list:
        return []
    
    # 簡易翻譯：保留原文，加上 LLM 風格的翻譯註解
    # 實際執行時由外部 LLM 處理
    translated = []
    for item in news_list[:max_items]:
        translated.append({
            "title_en": item["title"],
            "title_zh": item["title"],  # 待 LLM 翻譯
            "url": item["url"],
            "source": item["source"]
        })
    return translated


def generate_trump_analysis(indices, sectors, hot_stocks):
    """生成川普風格分析（由 LLM 填充）"""
    # 這個函數會被 LLM 調用來生成內容
    return {
        "market_overview": "<!-- LLM: 生成川普風格市場總評 -->",
        "hot_picks": "<!-- LLM: 生成熱門股推薦 -->",
        "sector_commentary": "<!-- LLM: 生成板塊評論 -->"
    }


def get_trend_emoji(change_pct):
    """取得趨勢表情"""
    if change_pct > 2:
        return "🚀"
    elif change_pct > 0.5:
        return "📈"
    elif change_pct > 0:
        return "🟢"
    elif change_pct > -0.5:
        return "🔴"
    elif change_pct > -2:
        return "📉"
    else:
        return "💥"


def generate_html(data):
    """生成 HTML 日報"""
    date_info = data["date_info"]
    indices = data.get("market_indices", [])
    hot_stocks = data.get("hot_stocks", [])
    sectors = data.get("sector_performance", [])
    news = data.get("news", {})
    earnings = data.get("earnings", [])
    
    # 合併所有新聞
    all_news = []
    for source, items in news.items():
        all_news.extend(items)
    
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
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
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
        
        .news-item .title {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            line-height: 1.5;
        }}
        
        .news-item .title a {{
            color: var(--text-primary);
            text-decoration: none;
        }}
        
        .news-item .title a:hover {{
            color: var(--accent-gold);
        }}
        
        .news-item .title-en {{
            font-size: 0.85rem;
            color: var(--text-muted);
            font-style: italic;
        }}
        
        /* 財報 */
        .earnings-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
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
        }}
        
        .earnings-item .eps {{
            font-size: 0.85rem;
            color: var(--text-muted);
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
            <div class="content" id="llm-analysis">
                <!-- LLM_TRANSLATION_START -->
                <p>今日市場分析由川投顧親自把關。我們看到大盤走勢，有些股票表現得非常棒，真的非常好，可以說是歷史上最好的表現之一。</p>
                <p>記住：低買高賣，這是常識，但很多人沒有這種常識。我們要聰明投資，像我一樣聰明。</p>
                <!-- LLM_TRANSLATION_END -->
            </div>
        </div>
        
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
    
    for stock in hot_stocks[:10]:
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
    
    # 顯示新聞（待 LLM 翻譯）
    news_count = 0
    for item in all_news[:12]:
        if news_count >= 10:
            break
        news_count += 1
        
        html += f'''
                <div class="news-item">
                    <span class="source">{item.get("source", "News")}</span>
                    <div class="title"><a href="{item["url"]}" target="_blank">{item["title"]}</a></div>
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
    
    for earn in earnings[:8]:
        html += f'''
                <div class="earnings-item">
                    <div class="symbol">{earn["symbol"]}</div>
                    <div class="eps">EPS 預估: {earn.get("eps_estimate", "-")}</div>
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


def main():
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    print(f"=== 川投顧日報生成: {date_str} ===")
    
    # 載入資料
    data = load_data(date_str)
    
    # 生成 HTML
    html = generate_html(data)
    
    # 儲存
    date_info = data["date_info"]
    output_path = OUTPUT_DIR / date_info["date_str"] / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"已生成: {output_path}")
    
    # 同時儲存到最新版本
    latest_path = OUTPUT_DIR / "latest.html"
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"已更新: {latest_path}")
    
    return output_path


if __name__ == "__main__":
    main()
