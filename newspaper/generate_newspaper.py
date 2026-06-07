#!/usr/bin/env python3
"""
日職每日報自動生成腳本
- 使用 collect_data 模組抓取 NPB 數據
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

# 從 collect_data 匯入數據收集功能
from collect_data import (
    TEAMS,
    get_date_info,
    fetch_standings,
    fetch_today_games,
    fetch_yesterday_games,
    fetch_leaders,
)

# 設定
NEWSPAPER_DIR = Path("/tmp/ebooksforme/newspaper")
GIT_DIR = Path("/tmp/ebooksforme")
NPB_BASE_URL = "https://npb.jp"


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


def fetch_team_news(max_per_team=3):
    """從 Google News RSS 爬取 NPB 球隊新聞"""
    import requests
    from bs4 import BeautifulSoup

    news = {}
    base_url = "https://news.google.com/rss/search"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    # 為每支球隊建立搜尋查詢（使用日文隊名）
    for team_key, team_info in TEAMS.items():
        query = f"{team_info['name_jp']} プロ野球"
        try:
            params = {"q": query, "hl": "ja", "gl": "JP"}
            resp = requests.get(base_url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.content, "xml")
            items = soup.find_all("item")

            team_news = []
            for item in items[:max_per_team]:
                title_el = item.find("title")
                source_el = item.find("source")
                link_el = item.find("link")

                title = title_el.text.strip() if title_el is not None else ""
                source = source_el.text.strip() if source_el is not None else ""
                link = link_el.text.strip() if link_el is not None else ""

                if not title:
                    continue

                team_news.append({
                    "title": title,
                    "source": source,
                    "link": link,
                })

            if team_news:
                news[team_key] = team_news
        except Exception as e:
            print(f"  News fetch failed for {team_key}: {e}")

    return news


def generate_html(info, games_data, standings_data, leaders_data, news_data=None):
    """生成電子報 HTML"""
    
    # ── 今日賽程卡片 ──
    today_games_html = ""
    if games_data and len(games_data) > 0:
        for game in games_data:
            home_key = game.get("home_team_key", "")
            away_key = game.get("away_team_key", "")
            home_logo = TEAMS.get(home_key, {}).get("logo", "")
            away_logo = TEAMS.get(away_key, {}).get("logo", "")
            home_name = game.get("home_team", "")
            away_name = game.get("away_team", "")
            home_score = game.get("home_score", "")
            away_score = game.get("away_score", "")
            stadium = game.get("stadium", "")
            status = game.get("status", "")

            if home_score or away_score:
                score_display = f"{away_score} - {home_score}"
            else:
                score_display = "vs"

            status_tag = f'<span class="game-status">{status}</span>' if status else ""
            today_games_html += f"""
            <div class="game-card">
                <div class="game-teams">
                    <div class="team-block away-block">
                        <img src="{away_logo}" alt="{away_name}" class="team-logo">
                        <span class="team-name">{away_name}</span>
                    </div>
                    <div class="score-display">{score_display}</div>
                    <div class="team-block home-block">
                        <img src="{home_logo}" alt="{home_name}" class="team-logo">
                        <span class="team-name">{home_name}</span>
                    </div>
                </div>
                <div class="game-meta">
                    <span>🏟 {stadium}</span>
                    {status_tag}
                </div>
            </div>"""
    else:
        today_games_html = """
            <div class="news-card">
                <span class="card-tag tag-game">賽程資訊</span>
                <p class="card-body">今日無安排比賽。</p>
            </div>"""

    # ── 戰績表 ──
    standings_html = ""
    if standings_data:
        for league_key, league_display in [("central", "中央聯盟"), ("pacific", "太平洋聯盟")]:
            teams = standings_data.get(league_key, [])
            if not teams:
                continue
            league_color = "var(--central)" if league_key == "central" else "var(--pacific)"
            rows = ""
            for t in teams:
                tk = t.get("team_key", "")
                logo_url = TEAMS.get(tk, {}).get("logo", "")
                rows += f"""
                <tr>
                    <td class="rank-cell">{t.get('rank', '')}</td>
                    <td class="team-cell"><img src="{logo_url}" alt="" class="standings-logo"> {t.get('team', '')}</td>
                    <td>{t.get('games', '')}</td>
                    <td>{t.get('wins', '')}</td>
                    <td>{t.get('losses', '')}</td>
                    <td>{t.get('draws', '')}</td>
                    <td>{t.get('pct', '')}</td>
                    <td>{t.get('gb', '')}</td>
                </tr>"""
            standings_html += f"""
            <h3 class="league-subtitle" style="color:{league_color};">◇ {league_display}</h3>
            <table class="standings-table">
                <thead><tr><th>順位</th><th>球隊</th><th>試合</th><th>勝</th><th>敗</th><th>分</th><th>率</th><th>差</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>"""
    else:
        standings_html = """
            <div class="news-card">
                <span class="card-tag tag-game">即時戰績</span>
                <p class="card-body">戰績資料暫時無法取得。</p>
            </div>"""

    # ── 個人排行榜 ──
    leaders_html = ""
    if leaders_data:
        leader_sections = [
            ("batting_avg_central", "打擊率", "中央聯盟"),
            ("batting_avg_pacific", "打擊率", "太平洋聯盟"),
            ("home_runs_central", "全壘打", "中央聯盟"),
            ("home_runs_pacific", "全壘打", "太平洋聯盟"),
            ("era_central", "防禦率", "中央聯盟"),
            ("era_pacific", "防禦率", "太平洋聯盟"),
            ("wins_central", "勝投", "中央聯盟"),
            ("wins_pacific", "勝投", "太平洋聯盟"),
        ]
        for key, stat_name, league_name in leader_sections:
            entries = leaders_data.get(key, [])
            if not entries:
                continue
            league_color = "var(--central)" if "central" in key else "var(--pacific)"
            rows = ""
            for e in entries[:5]:
                tk = e.get("team_key", "")
                logo_url = TEAMS.get(tk, {}).get("logo", "")
                rows += f"""
                <tr>
                    <td class="rank-cell">{e.get('rank', '')}</td>
                    <td class="player-cell">{e.get('player', '')}</td>
                    <td class="team-cell"><img src="{logo_url}" alt="" class="leaders-logo"> {e.get('team', '')}</td>
                    <td class="value-cell">{e.get('value', '')}</td>
                </tr>"""
            leaders_html += f"""
            <div class="leader-group">
                <h4 class="leader-subtitle" style="color:{league_color};">{league_name} {stat_name}</h4>
                <table class="leaders-table">
                    <thead><tr><th>#</th><th>選手</th><th>球隊</th><th>成績</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>"""
    else:
        leaders_html = """
            <div class="news-card">
                <span class="card-tag tag-game">排行榜</span>
                <p class="card-body">排行榜資料暫時無法取得。</p>
            </div>"""

    # ── 球隊新聞摘要 ──
    news_html = ""
    if news_data:
        # 依聯盟分組
        for league_key, league_display in [("central", "中央聯盟"), ("pacific", "太平洋聯盟")]:
            league_teams = [(k, v) for k, v in TEAMS.items() if v.get("league") == league_key]
            league_news_html = ""
            for team_key, team_info in league_teams:
                team_news = news_data.get(team_key, [])
                if not team_news:
                    continue
                logo_url = team_info.get("logo", "")
                items_html = ""
                for article in team_news:
                    title = article.get("title", "")
                    source = article.get("source", "")
                    link = article.get("link", "")
                    if link:
                        items_html += f"""
                        <li class="news-item">
                            <a href="{link}" target="_blank" rel="noopener" class="news-link">{title}</a>
                            <span class="news-source">— {source}</span>
                        </li>"""
                    else:
                        items_html += f"""
                        <li class="news-item">
                            <span class="news-title">{title}</span>
                            <span class="news-source">— {source}</span>
                        </li>"""
                if items_html:
                    league_news_html += f"""
                    <div class="team-news-block">
                        <div class="team-news-header">
                            <img src="{logo_url}" alt="{team_info['name']}" class="news-team-logo">
                            <span class="team-news-name">{team_info['name']}</span>
                        </div>
                        <ul class="team-news-list">{items_html}
                        </ul>
                    </div>"""
            if league_news_html:
                league_color = "var(--central)" if league_key == "central" else "var(--pacific)"
                news_html += f"""
                <h3 class="league-subtitle" style="color:{league_color};">◇ {league_display}</h3>
                <div class="news-grid">{league_news_html}
                </div>"""
    if not news_html:
        news_html = """
            <div class="news-card">
                <span class="card-tag tag-news">球隊新聞</span>
                <p class="card-body">今日球隊新聞暫時無法取得。</p>
            </div>"""

    # ── 合併主模板 ──
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
        /* ── 賽程卡片 ── */
        .game-card {{
            background: white;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 1rem;
            border: 1px solid #eee;
        }}
        .game-teams {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }}
        .team-block {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.3rem;
            flex: 1;
        }}
        .team-logo {{
            width: 48px;
            height: 48px;
            object-fit: contain;
        }}
        .team-name {{
            font-size: 0.9rem;
            font-weight: 700;
            text-align: center;
        }}
        .score-display {{
            font-size: 1.8rem;
            font-weight: 900;
            color: var(--ink);
            min-width: 4rem;
            text-align: center;
            font-family: 'Noto Serif TC', serif;
        }}
        .game-meta {{
            display: flex;
            justify-content: center;
            gap: 1.5rem;
            margin-top: 0.5rem;
            font-size: 0.8rem;
            color: var(--gray);
        }}
        .game-status {{
            display: inline-block;
            background: #fff3cd;
            color: #856404;
            padding: 0.1rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
        }}
        /* ── 戰績表 ── */
        .league-subtitle {{
            font-family: 'Noto Serif TC', serif;
            font-size: 1.1rem;
            font-weight: 700;
            margin: 1rem 0 0.5rem;
        }}
        .standings-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            margin-bottom: 1rem;
        }}
        .standings-table th {{
            background: var(--light-gray);
            padding: 0.5rem 0.4rem;
            text-align: center;
            font-weight: 700;
            border-bottom: 2px solid #ddd;
        }}
        .standings-table td {{
            padding: 0.4rem;
            text-align: center;
            border-bottom: 1px solid #eee;
        }}
        .standings-table .team-cell {{
            text-align: left;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }}
        .standings-logo {{
            width: 24px;
            height: 24px;
            object-fit: contain;
            vertical-align: middle;
        }}
        .rank-cell {{
            font-weight: 700;
            color: var(--gray);
        }}
        /* ── 排行榜 ── */
        .leader-group {{
            display: inline-block;
            width: 48%;
            vertical-align: top;
            margin-bottom: 0.5rem;
        }}
        .leader-group:nth-child(odd) {{
            margin-right: 2%;
        }}
        .leader-subtitle {{
            font-family: 'Noto Serif TC', serif;
            font-size: 0.95rem;
            font-weight: 700;
            margin: 0.75rem 0 0.3rem;
        }}
        .leaders-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem;
        }}
        .leaders-table th {{
            background: var(--light-gray);
            padding: 0.3rem 0.3rem;
            text-align: center;
            font-weight: 700;
            border-bottom: 2px solid #ddd;
        }}
        .leaders-table td {{
            padding: 0.3rem;
            text-align: center;
            border-bottom: 1px solid #eee;
        }}
        .leaders-table .team-cell {{
            text-align: left;
            display: flex;
            align-items: center;
            gap: 0.3rem;
            font-size: 0.75rem;
        }}
        .leaders-logo {{
            width: 18px;
            height: 18px;
            object-fit: contain;
            vertical-align: middle;
        }}
        .player-cell {{
            text-align: left !important;
            font-weight: 700;
        }}
        .value-cell {{
            font-weight: 900;
            color: var(--accent);
        }}
        /* ── 球隊新聞 ── */
        .news-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        .team-news-block {{
            background: white;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border: 1px solid #eee;
            flex: 1 1 280px;
            min-width: 0;
        }}
        .team-news-header {{
            display: flex;
            align-items: center;
            gap: 0.6rem;
            margin-bottom: 0.6rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--light-gray);
        }}
        .news-team-logo {{
            width: 28px;
            height: 28px;
            object-fit: contain;
        }}
        .team-news-name {{
            font-size: 1rem;
            font-weight: 800;
        }}
        .team-news-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .news-item {{
            font-size: 0.85rem;
            padding: 0.4rem 0;
            border-bottom: 1px solid #f0f0f0;
            line-height: 1.5;
        }}
        .news-item:last-child {{
            border-bottom: none;
        }}
        .news-link {{
            color: var(--ink);
            text-decoration: none;
            transition: color 0.15s;
        }}
        .news-link:hover {{
            color: var(--accent);
            text-decoration: underline;
        }}
        .news-title {{
            color: var(--ink);
        }}
        .news-source {{
            display: block;
            font-size: 0.75rem;
            color: var(--gray);
            margin-top: 0.15rem;
        }}
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
        .back-link:hover {{ background: #ff6b6b; }}
        @media (max-width: 600px) {{
            .title {{ font-size: 2rem; }}
            .content {{ padding: 1rem; }}
            .issue-info {{ flex-direction: column; gap: 0.5rem; }}
            .game-teams {{ flex-wrap: wrap; }}
            .leader-group {{ width: 100%; }}
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
                        本電子報於每日中午12:00自動生成，資料來源為 NPB 官方網站與 Google 新聞。<br>
                        由於自動化限制，部分內容可能無法即時更新，建議參考官方網站取得最新資訊。<br>
                        球隊新聞摘要為 Google 新聞自動搜集，僅供參考。
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
                {today_games_html}
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">📰 球隊新聞摘要</h2>
                    <span class="auto-badge">AUTO</span>
                </div>
                {news_html}
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">📊 戰績表</h2>
                </div>
                {standings_html}
            </div>
            
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">🏆 個人排行榜</h2>
                </div>
                {leaders_html}
            </div>
        </main>
        
        <footer class="footer">
            <p>📰 《日職每日報》自動生成版 · {info['today_display']}</p>
            <p>資料來源：NPB日本野球機構</p>
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
    info = get_date_info()
    print(f"今日日期: {info['today_display']}")
    
    # 2. 清除舊期數
    removed = clean_old_issues()
    print(f"清除舊期數: {len(removed)} 個")
    
    # 3. 建立今日期數目錄
    today_dir = NEWSPAPER_DIR / info["today"]
    today_dir.mkdir(parents=True, exist_ok=True)
    images_dir = today_dir / "images"
    images_dir.mkdir(exist_ok=True)
    
    # 4. 使用 collect_data 取得真實數據
    print("使用 collect_data 取得 NPB 數據...")
    try:
        games = fetch_today_games()
        print(f"  今日比賽: {len(games)} 場")
    except Exception as e:
        print(f"  取得今日比賽失敗: {e}")
        games = []
    
    try:
        standings = fetch_standings()
        central_count = len(standings.get("central", []))
        pacific_count = len(standings.get("pacific", []))
        print(f"  戰績表: 中央 {central_count} 隊, 太平洋 {pacific_count} 隊")
    except Exception as e:
        print(f"  取得戰績失敗: {e}")
        standings = {"central": [], "pacific": []}
    
    try:
        leaders = fetch_leaders()
        leader_count = sum(len(v) for v in leaders.values())
        print(f"  排行榜: {leader_count} 筆")
    except Exception as e:
        print(f"  取得排行榜失敗: {e}")
        leaders = {}
    
    # 5. 取得球隊新聞
    print("取得 NPB 球隊新聞...")
    try:
        news = fetch_team_news()
        news_count = sum(len(v) for v in news.values())
        print(f"  球隊新聞: {news_count} 篇")
    except Exception as e:
        print(f"  取得球隊新聞失敗: {e}")
        news = {}
    
    # 6. 生成 HTML（傳入真實數據）
    print("生成電子報 HTML...")
    html_content = generate_html(info, games, standings, leaders, news)
    
    # 7. 寫入檔案
    html_path = today_dir / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"已生成: {html_path}")
    
    # 8. 複製封面圖（如果有）
    cover_source = NEWSPAPER_DIR / "2026-06-07" / "images" / "cover.png"
    cover_target = images_dir / "cover.png"
    if cover_source.exists() and cover_source != cover_target:
        import shutil
        shutil.copy(cover_source, cover_target)
        print("已複製封面圖")
    
    # 9. 更新報架索引
    update_rack_index(info)
    
    # 10. 部署
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
