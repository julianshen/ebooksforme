#!/usr/bin/env python3
"""
日職每日報自動生成腳本
- 抓取 NPB 官方數據
- 生成 HTML 電子報
- 清除超過14天的舊期數
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

# 設定
NEWSPAPER_DIR = Path("/home/julianshen/projects/ebooksforme/newspaper")
GIT_DIR = Path("/home/julianshen/projects/ebooksforme")
NPB_BASE_URL = "https://npb.jp"
BASEBALL_DATA_URL = "https://baseballdata.jp"

# 球隊資料
TEAMS = {
    "giants": {"name": "讀賣巨人", "name_jp": "Yomiuri Giants", "official_url": "https://www.giants.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_g_l.gif", "stadium": "東京巨蛋", "league": "central"},
    "tigers": {"name": "阪神虎", "name_jp": "Hanshin Tigers", "official_url": "https://hanshintigers.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_t_l.gif", "stadium": "甲子園", "league": "central"},
    "carp": {"name": "廣島東洋鯉魚", "name_jp": "Hiroshima Carp", "official_url": "https://www.carp.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_c_l.gif", "stadium": "馬自達球場", "league": "central"},
    "baystars": {"name": "橫濱DeNA灣星", "name_jp": "Yokohama DeNA BayStars", "official_url": "https://www.baystars.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_db_l.gif", "stadium": "橫濱球場", "league": "central"},
    "swallows": {"name": "東京養樂多燕子", "name_jp": "Tokyo Yakult Swallows", "official_url": "https://www.yakult-swallows.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_s_l.gif", "stadium": "神宮球場", "league": "central"},
    "dragons": {"name": "中日龍", "name_jp": "Chunichi Dragons", "official_url": "https://www.dragons.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_d_l.gif", "stadium": "萬特力巨蛋", "league": "central"},
    "hawks": {"name": "福岡軟銀鷹", "name_jp": "Fukuoka SoftBank Hawks", "official_url": "https://www.softbankhawks.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_h_l.gif", "stadium": "雅虎巨蛋", "league": "pacific"},
    "fighters": {"name": "北海道日本火腿鬥士", "name_jp": "Hokkaido Nippon-Ham Fighters", "official_url": "https://www.fighters.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_f_l.gif", "stadium": "札幌巨蛋", "league": "pacific"},
    "eagles": {"name": "東北樂天金鷲", "name_jp": "Tohoku Rakuten Golden Eagles", "official_url": "https://www.rakuteneagles.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_e_l.gif", "stadium": "宮城球場", "league": "pacific"},
    "lions": {"name": "埼玉西武獅", "name_jp": "Saitama Seibu Lions", "official_url": "https://www.seibulions.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_l_l.gif", "stadium": "西武巨蛋", "league": "pacific"},
    "buffaloes": {"name": "歐力士猛牛", "name_jp": "Orix Buffaloes", "official_url": "https://www.buffaloes.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_b_l.gif", "stadium": "京瓷巨蛋", "league": "pacific"},
    "marines": {"name": "千葉羅德海洋", "name_jp": "Chiba Lotte Marines", "official_url": "https://www.marines.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_m_l.gif", "stadium": "ZOZO海洋球場", "league": "pacific"},
}


def get_today_info():
    """取得今日日期資訊"""
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    
    return {
        "today": today.strftime("%Y-%m-%d"),
        "today_display": today.strftime("%Y年%m月%d日"),
        "today_weekday": ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][today.weekday()],
        "yesterday": yesterday.strftime("%Y-%m-%d"),
        "yesterday_display": yesterday.strftime("%Y年%m月%d日"),
        "tomorrow": tomorrow.strftime("%Y-%m-%d"),
        "tomorrow_display": tomorrow.strftime("%Y年%m月%d日"),
        "year": today.year,
        "month": today.month,
        "day": today.day,
    }


def fetch_npb_schedule(date_str):
    """抓取 NPB 賽程"""
    # 將 YYYY-MM-DD 轉換為 YYYY/MM/DD 格式
    parts = date_str.split('-')
    url = f"{NPB_BASE_URL}/scores/{parts[0]}/{parts[1]}{parts[2]}/"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return None


def fetch_baseball_data():
    """抓取 Baseball Data 統計數據"""
    try:
        response = requests.get(BASEBALL_DATA_URL, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching baseball data: {e}")
        return None


def clean_old_issues():
    """清除超過14天的舊期數"""
    cutoff_date = datetime.now() - timedelta(days=14)
    removed = []
    
    for item in NEWSPAPER_DIR.iterdir():
        if item.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", item.name):
            issue_date = datetime.strptime(item.name, "%Y-%m-%d")
            if issue_date < cutoff_date:
                # 移除舊期數
                import shutil
                shutil.rmtree(item)
                removed.append(item.name)
                print(f"Removed old issue: {item.name}")
    
    return removed


def generate_html(info, games_data, standings_data, leaders_data):
    """生成電子報 HTML"""
    
    # 簡化版 HTML 模板（實際使用時會更完整）
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>日職每日報 - {info['today_display']} 自動生成版</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&family=Noto+Serif+TC:wght@600;900&display=swap" rel="stylesheet">
    <style>
        :root {{
            --paper: #fefefe;
            --ink: #1a1a2e;
            --accent: #e94560;
            --gold: #f4a261;
            --blue: #2a9d8f;
            --gray: #6c757d;
            --light-gray: #f8f9fa;
            --central: #0066cc;
            --pacific: #e60012;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Noto Sans TC', sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
            color: var(--ink);
            line-height: 1.7;
            min-height: 100vh;
        }}
        .newspaper {{
            max-width: 900px;
            margin: 0 auto;
            background: var(--paper);
            box-shadow: 0 4px 30px rgba(0,0,0,0.12);
            min-height: 100vh;
        }}
        .masthead {{
            background: linear-gradient(180deg, var(--ink) 0%, #16213e 100%);
            color: white;
            padding: 1.5rem 2rem;
            text-align: center;
        }}
        .tagline {{
            font-size: 0.85rem;
            letter-spacing: 0.3em;
            text-transform: uppercase;
            color: var(--gold);
            margin-bottom: 0.5rem;
        }}
        .title {{
            font-family: 'Noto Serif TC', serif;
            font-size: 3.2rem;
            font-weight: 900;
            letter-spacing: 0.1em;
            text-shadow: 3px 3px 0 rgba(233,69,96,0.3);
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            font-size: 1rem;
            color: rgba(255,255,255,0.8);
            letter-spacing: 0.15em;
        }}
        .issue-info {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid rgba(255,255,255,0.2);
            font-size: 0.9rem;
        }}
        .content {{ padding: 2rem; }}
        .section {{ margin-bottom: 2.5rem; }}
        .section-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 3px solid var(--ink);
        }}
        .section-title {{
            font-family: 'Noto Serif TC', serif;
            font-size: 1.5rem;
            font-weight: 900;
            flex: 1;
        }}
        .auto-badge {{
            display: inline-block;
            background: var(--accent);
            color: white;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
        }}
        .news-card {{
            background: white;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border-left: 4px solid var(--accent);
            margin-bottom: 1rem;
        }}
        .card-tag {{
            display: inline-block;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
        }}
        .tag-game {{ background: #e3f2fd; color: #1565c0; }}
        .tag-news {{ background: #fce4ec; color: #c2185b; }}
        .card-title {{
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
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
        .footer {{
            background: var(--light-gray);
            padding: 2rem;
            text-align: center;
            border-top: 3px solid var(--ink);
        }}
        .footer p {{ color: var(--gray); font-size: 0.85rem; margin-bottom: 0.5rem; }}
        .back-link {{
            display: inline-block;
            margin-top: 1rem;
            padding: 0.75rem 1.5rem;
            background: var(--accent);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 700;
        }}
        .back-link:hover {{ background: var(--accent-light); }}
        @media (max-width: 600px) {{
            .title {{ font-size: 2rem; }}
            .content {{ padding: 1rem; }}
            .issue-info {{ flex-direction: column; gap: 0.5rem; }}
        }}
    </style>
</head>
<body>
    <div class="newspaper">
        <header class="masthead">
            <div class="tagline">Nippon Professional Baseball Daily</div>
            <h1 class="title">日職每日報</h1>
            <p class="subtitle">日本職棒每日新聞 · 中文摘要 · 自動生成</p>
            <div class="issue-info">
                <span>📅 {info['today_display']} {info['today_weekday']}</span>
                <span>🤖 自動生成版</span>
                <span>⚾ 日本職棒</span>
            </div>
        </header>
        
        <main class="content">
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">🤖 自動生成說明</h2>
                    <span class="auto-badge">AUTO</span>
                </div>
                <div class="news-card">
                    <span class="card-tag tag-news">系統通知</span>
                    <h3 class="card-title">本報由自動化系統生成</h3>
                    <p class="card-body">
                        本電子報於每日中午12:00自動生成，資料來源為 NPB 官方網站及 Baseball Data。<br>
                        由於自動化限制，部分內容可能無法即時更新，建議參考官方網站取得最新資訊。<br>
                        球隊新聞摘要需人工整理，自動化版本暫時僅提供賽程與戰績資訊。
                    </p>
                    <p class="card-body" style="margin-top: 1rem;">
                        <strong>今日日期：</strong>{info['today_display']} {info['today_weekday']}<br>
                        <strong>昨日日期：</strong>{info['yesterday_display']}<br>
                        <strong>明日日期：</strong>{info['tomorrow_display']}<br>
                        <strong>生成時間：</strong>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    </p>
                </div>
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">📅 今日賽程 ({info['today_display']})</h2>
                </div>
                <div class="news-card">
                    <span class="card-tag tag-game">賽程資訊</span>
                    <p class="card-body">
                        請參考 <a href="{NPB_BASE_URL}/scores/{info['today'].replace('-', '')}/" target="_blank">NPB 官方賽程頁面</a> 取得今日最新賽程與比數。
                    </p>
                </div>
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">📊 戰績表</h2>
                </div>
                <div class="news-card">
                    <span class="card-tag tag-game">即時戰績</span>
                    <p class="card-body">
                        請參考 <a href="{BASEBALL_DATA_URL}" target="_blank">Baseball Data 戰績頁面</a> 取得最新戰績與排名。
                    </p>
                </div>
            </div>
        </main>
        
        <footer class="footer">
            <p>📰 《日職每日報》自動生成版 · {info['today_display']}</p>
            <p>資料來源：NPB日本野球機構、Baseball Data</p>
            <p>⚾ 本報僅留存最近兩週版本 · 自動生成時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <a href="/ebooksforme/" class="back-link">← 返回圖書館報架</a>
        </footer>
    </div>
</body>
</html>"""
    
    return html


def deploy_to_github():
    """部署到 GitHub Pages"""
    try:
        os.chdir(GIT_DIR)
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-m", f"日職每日報自動更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Deployed to GitHub Pages successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e}")
        return False


def main():
    """主程式"""
    print(f"=== 日職每日報自動生成開始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    # 1. 取得日期資訊
    info = get_today_info()
    print(f"今日日期: {info['today_display']}")
    
    # 2. 清除舊期數
    removed = clean_old_issues()
    print(f"清除舊期數: {len(removed)} 個")
    
    # 3. 建立今日期數目錄
    today_dir = NEWSPAPER_DIR / info["today"]
    today_dir.mkdir(parents=True, exist_ok=True)
    images_dir = today_dir / "images"
    images_dir.mkdir(exist_ok=True)
    
    # 4. 抓取數據（簡化版，實際使用時會更完整）
    print("抓取 NPB 數據...")
    schedule_html = fetch_npb_schedule(info["today"])
    baseball_data = fetch_baseball_data()
    
    # 5. 生成 HTML
    print("生成電子報 HTML...")
    html_content = generate_html(info, None, None, None)
    
    # 6. 寫入檔案
    html_path = today_dir / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"已生成: {html_path}")
    
    # 7. 複製封面圖（如果有）
    cover_source = NEWSPAPER_DIR / "2026-06-07" / "images" / "cover.png"
    cover_target = images_dir / "cover.png"
    if cover_source.exists() and cover_source != cover_target:
        import shutil
        shutil.copy(cover_source, cover_target)
        print("已複製封面圖")
    
    # 8. 更新報架索引
    update_rack_index(info)
    
    # 9. 部署
    print("部署到 GitHub Pages...")
    deploy_to_github()
    
    print(f"=== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")


def update_rack_index(info):
    """更新報架索引頁面"""
    # 取得所有期數
    issues = []
    for item in NEWSPAPER_DIR.iterdir():
        if item.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", item.name):
            issues.append(item.name)
    
    issues.sort(reverse=True)
    
    # 生成索引 HTML
    issues_html = ""
    for issue in issues[:14]:  # 只顯示最近14天
        date_obj = datetime.strptime(issue, "%Y-%m-%d")
        display_date = date_obj.strftime("%Y年%m月%d日")
        weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
        
        issues_html += f"""
            <div class="issue-card">
                <div class="issue-date">{display_date} 星期{weekday}</div>
                <div class="issue-title">日職每日報</div>
                <a href="newspaper/{issue}/" class="issue-link">閱讀本期 →</a>
            </div>
        """
    
    index_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>報架 - 日職每日報</title>
    <style>
        body {{
            font-family: 'Noto Sans TC', sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
            margin: 0;
            padding: 2rem;
            min-height: 100vh;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        h1 {{
            text-align: center;
            color: #1a1a2e;
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            text-align: center;
            color: #6c757d;
            margin-bottom: 2rem;
        }}
        .issues-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 1.5rem;
        }}
        .issue-card {{
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .issue-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.1);
        }}
        .issue-date {{
            font-size: 0.9rem;
            color: #6c757d;
            margin-bottom: 0.5rem;
        }}
        .issue-title {{
            font-size: 1.3rem;
            font-weight: 900;
            color: #1a1a2e;
            margin-bottom: 1rem;
        }}
        .issue-link {{
            display: inline-block;
            padding: 0.5rem 1rem;
            background: #e94560;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 700;
            transition: background 0.2s;
        }}
        .issue-link:hover {{
            background: #ff6b6b;
        }}
        .back-link {{
            display: inline-block;
            margin-top: 2rem;
            padding: 0.75rem 1.5rem;
            background: #1a1a2e;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 700;
        }}
        .info {{
            background: #fff3e0;
            border-left: 4px solid #f4a261;
            padding: 1rem;
            margin-bottom: 2rem;
            border-radius: 0 8px 8px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📰 報架</h1>
        <p class="subtitle">日職每日報 · 僅留存最近兩週版本</p>
        
        <div class="info">
            <strong>自動更新說明：</strong>本報每日中午12:00自動生成，自動清除超過14天的舊期數。
            <br>最後更新：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
        
        <div class="issues-grid">
            {issues_html}
        </div>
        
        <div style="text-align: center; margin-top: 2rem;">
            <a href="/ebooksforme/" class="back-link">← 返回圖書館</a>
        </div>
    </div>
</body>
</html>"""
    
    index_path = NEWSPAPER_DIR / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"已更新報架索引: {index_path}")


if __name__ == "__main__":
    main()
