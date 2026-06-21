#!/usr/bin/env python3
"""
日職每日報 - HTML 生成腳本 v2.0
暗色主題 + 封面輪用 + LLM 新聞翻譯摘要

讀取 collect_data.py 產生的 JSON，生成電子報 HTML
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
import urllib.request

# ============================================================
# 設定
# ============================================================
NEWSPAPER_DIR = Path("/home/julianshen/projects/ebooksforme/newspaper/npb")
GIT_DIR = Path("/home/julianshen/projects/ebooksforme")
COVERS_DIR = NEWSPAPER_DIR / "covers"

COVERS = ["cover-1.png", "cover-2.png", "cover-3.png", "cover-4.png", "cover-5.png"]

# LLM 模型的預設值 (在呼叫 agy 時使用)
LLM_MODEL = "Gemini 3.5 Flash (Medium)"

# 日文新聞來源名稱翻譯對照表
SOURCE_TRANSLATIONS = {
    "Yahoo!ニュース": "Yahoo!新聞",
    "ベースボールチャンネル": "棒球頻道",
    "サンスポ": "日刊體育",
    "スポーツナビ": "SportNavi",
    "日刊スポーツ": "日刊體育",
    "ｄメニューニュース": "d選單新聞",
    "インサイド": "Inside",
    "パ・リーグ.com": "太平洋聯盟官網",
    "阪神タイガース 公式サイト": "阪神虎官網",
    "横浜DeNAベイスターズ": "橫濱DeNA海灣之星",
    "福岡ソフトバンクホークス": "福岡軟銀鷹",
    "オリックス・バファローズ": "歐力士猛牛",
    "東北楽天ゴールデンイーグルス": "東北樂天金鷹",
    "中日ドラゴンズ オフィシャルウェブサイト": "中日龍官網",
    "読売巨人公式サイト": "讀賣巨人官網",
    "東京ヤクルトスワローズ": "東京養樂多燕子",
    "広島東洋カープ": "廣島東洋鯉魚",
    "北海道日本ハムファイターズ": "北海道日本火腿鬥士",
    "埼玉西武ライオンズ": "埼玉西武獅",
    "千葉ロッテマリーンズ": "千葉羅德海洋",
    "公式サイト": "官網",
    "webスポルティーバ": "Web Sportiva",
    "スポルティーバ": "Sportiva",
    "スポーツ報知": "報知體育",
    "Full-Count": "Full-Count",
    "Baseball King": "Baseball King",
    "スポニチ": "體育日本",
    "Sports Bull": "Sports Bull",
}


def translate_source(name: str) -> str:
    """翻譯日文新聞來源名稱為中文"""
    if not name:
        return ""
    name = name.strip()
    if name in SOURCE_TRANSLATIONS:
        return SOURCE_TRANSLATIONS[name]
    for jp, zh in SOURCE_TRANSLATIONS.items():
        if jp in name:
            name = name.replace(jp, zh)
    # 通用：「公式サイト」→「官網」
    name = name.replace('公式サイト', '官網')
    return name


# ============================================================
# HTML 安全輔助函數
# ============================================================
ALLOWED_SCHEMES = {"https", "http"}


def h(value) -> str:
    """HTML escape 文字內容（用於標籤內文字）"""
    return html.escape(str(value or ""), quote=False)


def attr(value) -> str:
    """HTML escape 屬性值（用於 href/src/alt 等）"""
    return html.escape(str(value or ""), quote=True)


def safe_url(value: str) -> str:
    """過濾 URL，只允許 http/https scheme"""
    value = str(value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in ALLOWED_SCHEMES:
        return ""
    return value


# ============================================================
# LLM 新聞翻譯
# ============================================================

# OpenRouter API 設定（比 agy/codex 快 20x）
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
# 模型優先順序: DeepSeek Chat V3（快+便宜）→ Gemini Flash（備援）
LLM_MODELS = [
    "deepseek/deepseek-chat-v3-0324",
    "google/gemini-2.0-flash-001",
]


def has_llm() -> bool:
    return bool(OPENROUTER_API_KEY) or shutil.which("agy") is not None or shutil.which("codex") is not None


def call_llm(prompt: str, timeout: int = 120) -> str | None:
    """呼叫 LLM 進行新聞翻譯/摘要 - 優先使用 OpenRouter API（最快），再 fallback 到 agy/codex"""
    import json as _json

    # 安全過濾：移除可能引發 prompt injection 的控制字元
    safe_prompt = prompt.replace("\x00", "").replace("\x1b", "")

    # 0) OpenRouter API（最快，1-3 秒回應）
    if OPENROUTER_API_KEY:
        for model in LLM_MODELS:
            try:
                data = _json.dumps({
                    "model": model,
                    "messages": [{"role": "user", "content": safe_prompt}],
                    "max_tokens": 4096,
                    "temperature": 0.3,
                }).encode()
                req = urllib.request.Request(
                    OPENROUTER_BASE_URL,
                    data=data,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    result = _json.loads(resp.read())
                content = result["choices"][0]["message"]["content"].strip()
                if content:
                    print(f"  [OpenRouter/{model.split('/')[-1]}] OK")
                    return content
            except Exception as e:
                print(f"  [OpenRouter/{model.split('/')[-1]}] 失敗: {e}")
                continue

    # 1) agy（備援 - 純文字模式）
    if shutil.which("agy"):
        try:
            proc = subprocess.Popen(
                ["agy", "--print", "--model", LLM_MODEL, "--print-timeout", f"{timeout}s"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "AGY_NO_TOOLS": "1"},
                cwd="/tmp",
            )
            stdout, stderr = proc.communicate(input=safe_prompt, timeout=timeout)
            if proc.returncode == 0 and stdout.strip():
                return stdout.strip()
        except Exception as e:
            print(f"  agy 失敗: {e}")

    # 2) codex CLI（最後備援）
    if shutil.which("codex"):
        try:
            result = subprocess.run(
                ["codex", "exec", "--", safe_prompt],
                capture_output=True, text=True, timeout=timeout,
                cwd="/tmp",
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            print(f"  codex 失敗: {e}")

    return None


def translate_news_batch(news_items: list[dict]) -> list[dict]:
    """
    使用 LLM 批次翻譯新聞標題 + 生成中文摘要。
    若 LLM 不可用，回傳原文。
    """
    if not news_items:
        return []

    if not has_llm():
        print("  [LLM 不可用] 新聞將顯示日文原文")
        for item in news_items:
            item["title_zh"] = item.get("title", "")
            item["summary_zh"] = item.get("summary", "")[:200]
        return news_items

    # 組合 prompt：一次處理最多 10 則
    batch_size = 10
    results = []

    for i in range(0, len(news_items), batch_size):
        batch = news_items[i:i + batch_size]
        news_text = ""
        for idx, item in enumerate(batch):
            news_text += f"\n[{idx}] 標題: {item.get('title', '')}\n"
            news_text += f"    來源: {item.get('source', '')}\n"
            news_text += f"    摘要: {item.get('summary', '')[:400]}\n"

        prompt = f"""你是一位專業的日本職棒新聞編輯。請將以下日文新聞翻譯成繁體中文，並為每則新聞生成 50-80 字的中文摘要。

要求：
1. 標題翻譯要準確且吸引人
2. 摘要要涵蓋新聞重點
3. 人名、球隊名使用台灣慣用譯名
4. 直接回傳格式化的結果，不要額外解釋

輸出格式（嚴格遵守）：
[0] 中文標題: <翻譯後標題>
[0] 摘要: <中文摘要>
[1] 中文標題: <翻譯後標題>
[1] 摘要: <中文摘要>
...

新聞內容：
{news_text}
"""
        print(f"  呼叫 LLM 翻譯新聞批次 {i//batch_size + 1}/{(len(news_items)-1)//batch_size + 1}...")
        response = call_llm(prompt, timeout=300)

        if response:
            # 解析回傳結果
            for idx, item in enumerate(batch):
                title_pattern = rf"\[{idx}\]\s*中文標題[:：]\s*(.+?)(?:\n|$)"
                summary_pattern = rf"\[{idx}\]\s*摘要[:：]\s*(.+?)(?:\n\[|\Z)"
                title_match = re.search(title_pattern, response, re.DOTALL)
                summary_match = re.search(summary_pattern, response, re.DOTALL)

                title_zh = title_match.group(1).strip() if title_match else item.get("title", "")
                summary_zh = summary_match.group(1).strip() if summary_match else item.get("summary", "")[:200]

                # Strip trailing source name from translated title
                for src in [item.get("source", ""), "Yahoo!ニュース", "サンスポ"]:
                    if src and title_zh.endswith(src):
                        title_zh = title_zh[:-len(src)].rstrip(" -").rstrip()
                        break
                item["title_zh"] = title_zh
                item["summary_zh"] = summary_zh
                results.append(item)
        else:
            # LLM 失敗，使用原文
            for item in batch:
                item["title_zh"] = item.get("title", "")
                item["summary_zh"] = item.get("summary", "")[:200]
                results.append(item)

    return results


# ============================================================
# HTML 生成
# ============================================================

def generate_html(data: dict, cover_file: str) -> str:
    info = data["date_info"]
    teams = data["teams"]
    yesterday_games = data.get("yesterday_games", [])
    today_games = data.get("today_games", [])
    tomorrow_games = data.get("tomorrow_games", [])
    standings = data.get("standings", {})
    leaders = data.get("leaders", {})
    interleague = data.get("interleague", {})
    focus_news = data.get("focus_news", {}).get("all", [])
    team_news = data.get("team_news", {})

    # ── 封面 ──
    cover_html = f'<div class="cover-banner"><img src="images/{attr(cover_file)}" alt="日職每日報封面"></div>' if cover_file else ""

    # ── 昨日戰報 ──
    yesterday_html = ""
    valid_yesterday = [g for g in yesterday_games if g.get("home_team") or g.get("away_team")] if yesterday_games else []
    if valid_yesterday:
        for game in valid_yesterday:
            home_key = game.get("home_team_key", "")
            away_key = game.get("away_team_key", "")
            home_logo = safe_url(teams.get(home_key, {}).get("logo", "")) if isinstance(teams, dict) else ""
            away_logo = safe_url(teams.get(away_key, {}).get("logo", "")) if isinstance(teams, dict) else ""
            home_name = h(game.get("home_team", ""))
            away_name = h(game.get("away_team", ""))
            home_score = h(game.get("home_score", ""))
            away_score = h(game.get("away_score", ""))
            stadium = h(game.get("stadium", ""))
            status = h(game.get("status", ""))
            winning_pitcher = h(game.get("winning_pitcher", ""))
            losing_pitcher = h(game.get("losing_pitcher", ""))
            attendance = h(game.get("attendance", ""))
            duration = h(game.get("duration", ""))

            score_display = f"{away_score} - {home_score}" if home_score or away_score else "vs"
            extra_info = ""
            if winning_pitcher:
                extra_info += f'<span class="pitcher-info">勝投: {winning_pitcher}</span>'
            if losing_pitcher:
                extra_info += f'<span class="pitcher-info">敗投: {losing_pitcher}</span>'
            if attendance:
                extra_info += f'<span class="attendance-info">入場: {attendance}人</span>'
            if duration:
                extra_info += f'<span class="duration-info">時間: {duration}</span>'

            status_tag = f'<span class="game-status">{status}</span>' if status else ""
            yesterday_html += f"""
            <div class="game-card">
                <div class="game-teams">
                    <div class="team-block away-block">
                        <img src="{attr(away_logo)}" alt="{attr(away_name)}" class="team-logo">
                        <span class="team-name">{away_name}</span>
                    </div>
                    <div class="score-display">{score_display}</div>
                    <div class="team-block home-block">
                        <img src="{attr(home_logo)}" alt="{attr(home_name)}" class="team-logo">
                        <span class="team-name">{home_name}</span>
                    </div>
                </div>
                <div class="game-meta">
                    <span>🏟 {stadium}</span>
                    {status_tag}
                </div>
                <div class="game-extra">{extra_info}</div>
            </div>"""
    else:
        yesterday_html = '<div class="news-card"><span class="card-tag tag-game">昨日戰報</span><p class="card-body">昨日無比賽資料。</p></div>'

    # ── 今日賽程 ──
    today_html = ""
    valid_today = [g for g in today_games if g.get("home_team") or g.get("away_team")] if today_games else []
    if valid_today:
        for game in valid_today:
            home_key = game.get("home_team_key", "")
            away_key = game.get("away_team_key", "")
            home_logo = safe_url(teams.get(home_key, {}).get("logo", "")) if isinstance(teams, dict) else ""
            away_logo = safe_url(teams.get(away_key, {}).get("logo", "")) if isinstance(teams, dict) else ""
            home_name = h(game.get("home_team", ""))
            away_name = h(game.get("away_team", ""))
            home_score = h(game.get("home_score", ""))
            away_score = h(game.get("away_score", ""))
            stadium = h(game.get("stadium", ""))
            status = h(game.get("status", ""))
            game_time = h(game.get("time", ""))

            score_display = f"{away_score} - {home_score}" if home_score and away_score and home_score != "*" else "vs"
            time_tag = f'<span class="game-time">⏰ {game_time}</span>' if game_time else ""
            status_tag = f'<span class="game-status">{status}</span>' if status else ""
            today_html += f"""
            <div class="game-card">
                <div class="game-teams">
                    <div class="team-block away-block">
                        <img src="{attr(away_logo)}" alt="{attr(away_name)}" class="team-logo">
                        <span class="team-name">{away_name}</span>
                    </div>
                    <div class="score-display">{score_display}</div>
                    <div class="team-block home-block">
                        <img src="{attr(home_logo)}" alt="{attr(home_name)}" class="team-logo">
                        <span class="team-name">{home_name}</span>
                    </div>
                </div>
                <div class="game-meta">
                    <span>🏟 {stadium}</span>
                    {time_tag}
                    {status_tag}
                </div>
            </div>"""
    else:
        today_html = '<div class="news-card"><span class="card-tag tag-game">今日賽程</span><p class="card-body">今日無安排比賽。</p></div>'

    # ── 明日預告 ──
    tomorrow_html = ""
    valid_tomorrow = [g for g in tomorrow_games if g.get("home_team") or g.get("away_team")] if tomorrow_games else []
    if valid_tomorrow:
        for game in valid_tomorrow:
            home_key = game.get("home_team_key", "")
            away_key = game.get("away_team_key", "")
            home_logo = safe_url(teams.get(home_key, {}).get("logo", "")) if isinstance(teams, dict) else ""
            away_logo = safe_url(teams.get(away_key, {}).get("logo", "")) if isinstance(teams, dict) else ""
            home_name = h(game.get("home_team", ""))
            away_name = h(game.get("away_team", ""))
            stadium = h(game.get("stadium", ""))
            game_time = h(game.get("time", ""))
            home_pitcher = h(game.get("home_pitcher", ""))
            away_pitcher = h(game.get("away_pitcher", ""))

            pitcher_info = ""
            if away_pitcher:
                pitcher_info += f'<span class="pitcher-info">先發: {away_pitcher}</span>'
            if home_pitcher:
                pitcher_info += f'<span class="pitcher-info">先發: {home_pitcher}</span>'
            time_tag = f'<span class="game-time">⏰ {game_time}</span>' if game_time else ""
            tomorrow_html += f"""
            <div class="game-card">
                <div class="game-teams">
                    <div class="team-block away-block">
                        <img src="{attr(away_logo)}" alt="{attr(away_name)}" class="team-logo">
                        <span class="team-name">{away_name}</span>
                    </div>
                    <div class="score-display">vs</div>
                    <div class="team-block home-block">
                        <img src="{attr(home_logo)}" alt="{attr(home_name)}" class="team-logo">
                        <span class="team-name">{home_name}</span>
                    </div>
                </div>
                <div class="game-meta">
                    <span>🏟 {stadium}</span>
                    {time_tag}
                </div>
                <div class="game-extra">{pitcher_info}</div>
            </div>"""
    else:
        tomorrow_html = '<div class="news-card"><span class="card-tag tag-game">明日預告</span><p class="card-body">明日無安排比賽。</p></div>'

    # ── 戰績表 ──
    standings_html = ""
    if standings:
        for league_key, league_display in [("central", "中央聯盟"), ("pacific", "太平洋聯盟")]:
            league_teams = standings.get(league_key, [])
            if not league_teams:
                continue
            league_color = "var(--central)" if league_key == "central" else "var(--pacific)"
            rows = ""
            for t in league_teams:
                tk = t.get("team_key", "")
                logo_url = teams.get(tk, {}).get("logo", "") if isinstance(teams, dict) else ""
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
        standings_html = '<div class="news-card"><span class="card-tag tag-game">戰績表</span><p class="card-body">戰績資料暫時無法取得。</p></div>'

    # ── 交流戰 ──
    interleague_html = ""
    if interleague and interleague.get("standings"):
        cw = interleague.get("central_wins", 0)
        pw = interleague.get("pacific_wins", 0)
        leader_text = ""
        if interleague.get("leader") == "central":
            leader_text = f"中央聯盟領先（{cw} - {pw}）"
        elif interleague.get("leader") == "pacific":
            leader_text = f"太平洋聯盟領先（{pw} - {cw}）"
        else:
            leader_text = f"平手（{cw} - {pw}）"
        interleague_html = f"""
        <div class="interleague-card">
            <div class="interleague-header">⚔️ 交流戰戰績</div>
            <div class="interleague-score">
                <span class="central-score">中央聯盟 {cw} 勝</span>
                <span class="vs-divider">vs</span>
                <span class="pacific-score">太平洋聯盟 {pw} 勝</span>
            </div>
            <div class="interleague-leader">{leader_text}</div>
        </div>"""
    else:
        interleague_html = '<div class="news-card"><span class="card-tag tag-game">交流戰</span><p class="card-body">交流戰資料暫時無法取得。</p></div>'

    # ── 個人排行榜 ──
    leaders_html = ""
    if leaders:
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
            entries = leaders.get(key, [])
            if not entries:
                continue
            league_color = "var(--central)" if "central" in key else "var(--pacific)"
            rows = ""
            for e in entries[:5]:
                tk = e.get("team_key", "")
                logo_url = teams.get(tk, {}).get("logo", "") if isinstance(teams, dict) else ""
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
        leaders_html = '<div class="news-card"><span class="card-tag tag-game">排行榜</span><p class="card-body">排行榜資料暫時無法取得。</p></div>'

    # ── 焦點新聞 ──
    focus_news_html = ""
    if focus_news:
        # 取前 8 則翻譯
        news_to_translate = focus_news[:8]
        translated = translate_news_batch(news_to_translate)
        for article in translated:
            title = h(article.get("title_zh", article.get("title", "")))
            summary = h(article.get("summary_zh", article.get("summary", ""))[:200])
            source = h(translate_source(article.get("source", "")))
            url = attr(safe_url(article.get("url", "")))
            date_str = h(article.get("date", ""))
            focus_news_html += f"""
            <div class="news-card focus-news">
                <span class="card-tag tag-news">{source}</span>
                <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h3>
                <p class="card-body">{summary}</p>
                <div class="news-meta">
                    <span class="news-date">{date_str}</span>
                    <a href="{url}" target="_blank" rel="noopener noreferrer" class="read-more">閱讀原文 →</a>
                </div>
            </div>"""
    else:
        focus_news_html = '<div class="news-card"><span class="card-tag tag-news">焦點新聞</span><p class="card-body">今日焦點新聞暫時無法取得。</p></div>'

    # ── 球隊新聞 ──
    team_news_html = ""
    if team_news:
        for league_key, league_display in [("central", "中央聯盟"), ("pacific", "太平洋聯盟")]:
            league_teams_news = []
            for tk, tinfo in (teams.items() if isinstance(teams, dict) else []):
                if tinfo.get("league") == league_key and tk in team_news:
                    league_teams_news.append((tk, tinfo, team_news[tk]))
            if not league_teams_news:
                continue
            league_color = "var(--central)" if league_key == "central" else "var(--pacific)"
            league_news_block = ""
            for tk, tinfo, articles in league_teams_news:
                logo_url = safe_url(tinfo.get("logo", ""))
                items_html = ""
                for article in articles[:3]:
                    title = h(article.get("title_zh", article.get("title", "")))
                    source = h(translate_source(article.get("source", "")))
                    link = attr(safe_url(article.get("link", "")))
                    if link:
                        items_html += f'<li class="news-item"><a href="{link}" target="_blank" rel="noopener noreferrer" class="news-link">{title}</a><span class="news-source">— {source}</span></li>'
                    else:
                        items_html += f'<li class="news-item"><span class="news-title">{title}</span><span class="news-source">— {source}</span></li>'
                if items_html:
                    league_news_block += f"""
                    <div class="team-news-block">
                        <div class="team-news-header">
                            <img src="{attr(logo_url)}" alt="{attr(tinfo.get('name', ''))}" class="news-team-logo">
                            <span class="team-news-name">{h(tinfo.get('name', ''))}</span>
                        </div>
                        <ul class="team-news-list">{items_html}</ul>
                    </div>"""
            if league_news_block:
                team_news_html += f"""
                <h3 class="league-subtitle" style="color:{league_color};">◇ {league_display}</h3>
                <div class="news-grid">{league_news_block}</div>"""
    if not team_news_html:
        team_news_html = '<div class="news-card"><span class="card-tag tag-news">球隊新聞</span><p class="card-body">今日球隊新聞暫時無法取得。</p></div>'

    # ── 合併主模板 ──
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>日職每日報 - {info['today_display']}</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&family=Noto+Serif+TC:wght@600;900&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0f172a;
            --paper: #1e293b;
            --ink: #f1f5f9;
            --muted: #94a3b8;
            --accent: #38bdf8;
            --gold: #fbbf24;
            --central: #60a5fa;
            --pacific: #f87171;
            --border: #334155;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Noto Sans TC', sans-serif;
            background: var(--bg);
            color: var(--ink);
            line-height: 1.7;
            min-height: 100vh;
        }}
        .newspaper {{
            max-width: 900px;
            margin: 0 auto;
            background: var(--paper);
            box-shadow: 0 4px 40px rgba(0,0,0,0.5);
            min-height: 100vh;
        }}
        .cover-banner {{
            width: 100%;
            border-radius: 0 0 16px 16px;
            overflow: hidden;
            margin-bottom: 0;
            box-shadow: 0 0 40px rgba(56,189,248,0.15);
        }}
        .cover-banner img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        .masthead {{
            background: linear-gradient(180deg, #020617 0%, #0f172a 100%);
            color: white;
            padding: 1.5rem 2rem;
            text-align: center;
            border-bottom: 2px solid var(--accent);
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
            text-shadow: 3px 3px 0 rgba(56,189,248,0.3);
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            font-size: 1rem;
            color: var(--muted);
            letter-spacing: 0.15em;
        }}
        .issue-info {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            font-size: 0.9rem;
            color: var(--muted);
        }}
        .content {{ padding: 2rem; }}
        .section {{ margin-bottom: 2.5rem; }}
        .section-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1.5rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid var(--accent);
        }}
        .section-title {{
            font-family: 'Noto Serif TC', serif;
            font-size: 1.5rem;
            font-weight: 900;
            flex: 1;
            color: var(--ink);
        }}
        .auto-badge {{
            display: inline-block;
            background: var(--accent);
            color: #0f172a;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 900;
        }}
        .news-card {{
            background: #0f172a;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 2px 12px rgba(0,0,0,0.3);
            border-left: 4px solid var(--accent);
            margin-bottom: 1rem;
        }}
        .focus-news {{
            border-left-color: var(--gold);
        }}
        .focus-news .card-title a {{
            color: var(--gold);
            text-decoration: none;
            transition: color 0.15s;
        }}
        .focus-news .card-title a:hover {{
            color: #f59e0b;
            text-decoration: underline;
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
        .tag-game {{ background: rgba(56,189,248,0.15); color: var(--accent); }}
        .tag-news {{ background: rgba(251,191,36,0.15); color: var(--gold); }}
        .card-title {{
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            color: var(--ink);
        }}
        .card-body {{ font-size: 0.95rem; color: var(--muted); line-height: 1.7; }}
        .news-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 0.75rem;
            padding-top: 0.5rem;
            border-top: 1px solid var(--border);
        }}
        .news-date {{ font-size: 0.8rem; color: var(--muted); }}
        .read-more {{
            font-size: 0.85rem;
            color: var(--accent);
            text-decoration: none;
            font-weight: 700;
        }}
        .read-more:hover {{ text-decoration: underline; }}
        /* ── 賽程卡片 ── */
        .game-card {{
            background: #0f172a;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            box-shadow: 0 2px 12px rgba(0,0,0,0.3);
            margin-bottom: 1rem;
            border: 1px solid var(--border);
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
            color: var(--ink);
        }}
        .score-display {{
            font-size: 1.8rem;
            font-weight: 900;
            color: var(--accent);
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
            color: var(--muted);
        }}
        .game-extra {{
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-top: 0.5rem;
            font-size: 0.75rem;
            color: var(--muted);
            flex-wrap: wrap;
        }}
        .pitcher-info, .attendance-info, .duration-info {{
            background: rgba(56,189,248,0.1);
            padding: 0.1rem 0.5rem;
            border-radius: 4px;
        }}
        .game-status {{
            display: inline-block;
            background: rgba(251,191,36,0.15);
            color: var(--gold);
            padding: 0.1rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
        }}
        .game-time {{
            color: var(--accent);
            font-weight: 700;
        }}
        /* ── 戰績表 ── */
        .league-subtitle {{
            font-family: 'Noto Serif TC', serif;
            font-size: 1.1rem;
            font-weight: 700;
            margin: 1rem 0 0.5rem;
            color: var(--ink);
        }}
        .standings-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            margin-bottom: 1rem;
            background: #0f172a;
            border-radius: 8px;
            overflow: hidden;
        }}
        .standings-table th {{
            background: #1e293b;
            padding: 0.5rem 0.4rem;
            text-align: center;
            font-weight: 700;
            border-bottom: 2px solid var(--border);
            color: var(--muted);
        }}
        .standings-table td {{
            padding: 0.4rem;
            text-align: center;
            border-bottom: 1px solid var(--border);
            color: var(--ink);
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
            color: var(--muted);
        }}
        /* ── 交流戰 ── */
        .interleague-card {{
            background: linear-gradient(135deg, #1e3a5f 0%, #3d1e1e 100%);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            margin-bottom: 1.5rem;
            border: 1px solid var(--border);
        }}
        .interleague-header {{
            font-size: 1.2rem;
            font-weight: 900;
            color: var(--gold);
            margin-bottom: 1rem;
        }}
        .interleague-score {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 2rem;
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}
        .central-score {{ color: var(--central); }}
        .pacific-score {{ color: var(--pacific); }}
        .vs-divider {{ color: var(--muted); font-size: 1rem; }}
        .interleague-leader {{
            font-size: 0.9rem;
            color: var(--gold);
            font-weight: 700;
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
            background: #0f172a;
            border-radius: 8px;
            overflow: hidden;
        }}
        .leaders-table th {{
            background: #1e293b;
            padding: 0.3rem 0.3rem;
            text-align: center;
            font-weight: 700;
            border-bottom: 2px solid var(--border);
            color: var(--muted);
        }}
        .leaders-table td {{
            padding: 0.3rem;
            text-align: center;
            border-bottom: 1px solid var(--border);
            color: var(--ink);
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
            background: #0f172a;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 12px rgba(0,0,0,0.3);
            border: 1px solid var(--border);
            flex: 1 1 280px;
            min-width: 0;
        }}
        .team-news-header {{
            display: flex;
            align-items: center;
            gap: 0.6rem;
            margin-bottom: 0.6rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--border);
        }}
        .news-team-logo {{
            width: 28px;
            height: 28px;
            object-fit: contain;
        }}
        .team-news-name {{
            font-size: 1rem;
            font-weight: 800;
            color: var(--ink);
        }}
        .team-news-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .news-item {{
            font-size: 0.85rem;
            padding: 0.4rem 0;
            border-bottom: 1px solid var(--border);
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
            color: var(--muted);
            margin-top: 0.15rem;
        }}
        .footer {{
            background: #020617;
            padding: 2rem;
            text-align: center;
            border-top: 2px solid var(--accent);
        }}
        .footer p {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 0.5rem; }}
        .back-link {{
            display: inline-block;
            margin-top: 1rem;
            padding: 0.75rem 1.5rem;
            background: var(--accent);
            color: #0f172a;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 900;
        }}
        .back-link:hover {{ background: #7dd3fc; }}
        @media (max-width: 600px) {{
            .title {{ font-size: 2rem; }}
            .content {{ padding: 1rem; }}
            .issue-info {{ flex-direction: column; gap: 0.5rem; }}
            .game-teams {{ flex-wrap: wrap; }}
            .leader-group {{ width: 100%; }}
            .interleague-score {{ flex-direction: column; gap: 0.5rem; }}
        }}
    </style>
</head>
<body>
    <div class="newspaper">
        {cover_html}
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
                    <h2 class="section-title">📰 焦點新聞</h2>
                    <span class="auto-badge">LLM翻譯</span>
                </div>
                {focus_news_html}
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">📋 昨日戰報 ({info['yesterday_display']})</h2>
                </div>
                {yesterday_html}
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">📅 今日賽程 ({info['today_display']})</h2>
                </div>
                {today_html}
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">🔮 明日預告 ({info['tomorrow_display']})</h2>
                </div>
                {tomorrow_html}
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">📊 聯盟戰績</h2>
                </div>
                {standings_html}
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">⚔️ 交流戰</h2>
                </div>
                {interleague_html}
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">🏆 個人排行榜</h2>
                </div>
                {leaders_html}
            </div>

            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">📰 球隊新聞摘要</h2>
                </div>
                {team_news_html}
            </div>
        </main>

        <footer class="footer">
            <p>📰 《日職每日報》自動生成版 · {info['today_display']}</p>
            <p>資料來源：NPB日本野球機構 / 日刊スポーツ / スポニチ / スポーツ報知 / Sports Bull / Baseball King / Full-Count</p>
            <p>⚾ 本報僅留存最近兩週版本 · 自動生成時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <a href="/ebooksforme/" class="back-link">← 返回圖書館報架</a>
        </footer>
    </div>
</body>
</html>"""
    return html


# ============================================================
# 部署
# ============================================================
def clean_old_issues():
    cutoff_date = datetime.now() - timedelta(days=14)
    removed = []
    ISSUE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for item in NEWSPAPER_DIR.iterdir():
        if item.is_dir() and ISSUE_DIR_RE.fullmatch(item.name):
            issue_date = datetime.strptime(item.name, "%Y-%m-%d")
            if issue_date < cutoff_date:
                shutil.rmtree(item)
                removed.append(item.name)
                print(f"Removed old issue: {item.name}")
    return removed


def deploy_to_github():
    try:
        os.chdir(GIT_DIR)
        # 只 add 明確路徑，避免把其他未提交改動一起推上去
        rel_path = str(NEWSPAPER_DIR.relative_to(GIT_DIR))
        subprocess.run(["git", "add", rel_path], check=True)

        # 檢查是否有變更需要提交
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=GIT_DIR,
        )
        if diff.returncode == 0:
            print("No changes to deploy.")
            return True

        subprocess.run(["git", "commit", "-m", f"日職每日報自動更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Deployed to GitHub Pages successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e}")
        return False


def update_rack_index(info):
    issues = []
    for item in NEWSPAPER_DIR.iterdir():
        if item.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", item.name):
            issues.append(item.name)
    issues.sort(reverse=True)

    issues_html = ""
    for issue in issues[:14]:
        date_obj = datetime.strptime(issue, "%Y-%m-%d")
        display_date = date_obj.strftime("%Y年%m月%d日")
        weekday = ["一", "二", "三", "四", "五", "六", "日"][date_obj.weekday()]
        issues_html += f"""
            <div class="issue-card">
                <div class="issue-date">{display_date} 星期{weekday}</div>
                <div class="issue-title">日職每日報</div>
                <a href="newspaper/npb/{issue}/" class="issue-link">閱讀本期 →</a>
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
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            margin: 0;
            padding: 2rem;
            min-height: 100vh;
            color: #f1f5f9;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        h1 {{
            text-align: center;
            color: #f1f5f9;
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            text-align: center;
            color: #94a3b8;
            margin-bottom: 2rem;
        }}
        .issues-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 1.5rem;
        }}
        .issue-card {{
            background: #1e293b;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 2px 12px rgba(0,0,0,0.3);
            transition: transform 0.2s, box-shadow 0.2s;
            border: 1px solid #334155;
        }}
        .issue-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.4);
        }}
        .issue-date {{
            font-size: 0.9rem;
            color: #94a3b8;
            margin-bottom: 0.5rem;
        }}
        .issue-title {{
            font-size: 1.3rem;
            font-weight: 900;
            color: #f1f5f9;
            margin-bottom: 1rem;
        }}
        .issue-link {{
            display: inline-block;
            padding: 0.5rem 1rem;
            background: #38bdf8;
            color: #0f172a;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 700;
            transition: background 0.2s;
        }}
        .issue-link:hover {{
            background: #7dd3fc;
        }}
        .back-link {{
            display: inline-block;
            margin-top: 2rem;
            padding: 0.75rem 1.5rem;
            background: #1e293b;
            color: #f1f5f9;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 700;
            border: 1px solid #334155;
        }}
        .info {{
            background: rgba(56,189,248,0.1);
            border-left: 4px solid #38bdf8;
            padding: 1rem;
            margin-bottom: 2rem;
            border-radius: 0 8px 8px 0;
            color: #94a3b8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📰 報架</h1>
        <p class="subtitle">日職每日報 · 僅留存最近兩週版本</p>

        <div class="info">
            <strong style="color:#38bdf8">自動更新說明：</strong>本報每日中午12:00自動生成，自動清除超過14天的舊期數。
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


def main():
    # 解析命令列參數
    parser = argparse.ArgumentParser(description="日職每日報 - HTML 生成腳本")
    parser.add_argument(
        "--model",
        type=str,
        default="Gemini 3.5 Flash (Medium)",
        help="指定 LLM 模型名稱 (預設: Gemini 3.5 Flash (Medium))",
    )
    args = parser.parse_args()

    global LLM_MODEL
    LLM_MODEL = args.model

    print(f"=== 日職每日報生成開始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"使用 LLM 模型: {LLM_MODEL}")

    # 1. 讀取數據
    today_str = datetime.now().strftime("%Y-%m-%d")
    # 從 collect_data 的輸出讀取
    data_file = NEWSPAPER_DIR / "data" / f"{today_str}.json"

    if not data_file.exists():
        print(f"數據檔案不存在: {data_file}")
        print("請先執行: python3 collect_data.py")
        sys.exit(1)

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    info = data.get("date_info", {"today": today_str, "today_display": today_str})
    print(f"今日日期: {info.get('today_display', info.get('today', ''))}")

    # 2. 清除舊期數
    removed = clean_old_issues()
    print(f"清除舊期數: {len(removed)} 個")

    # 3. 建立今日期數目錄
    today_dir = NEWSPAPER_DIR / info["today"]
    today_dir.mkdir(parents=True, exist_ok=True)
    images_dir = today_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # 4. 封面輪用
    today_date = datetime.strptime(info["today"], "%Y-%m-%d")
    week_number = today_date.isocalendar()[1]
    cover_index = (week_number - 1) % len(COVERS)
    cover_file = COVERS[cover_index]
    print(f"使用封面: {cover_file} (第 {week_number} 週)")

    # 複製封面
    cover_src = COVERS_DIR / cover_file
    if cover_src.exists():
        shutil.copy2(cover_src, images_dir / cover_file)
        print("已複製封面圖")
    else:
        print(f"[警告] 封面圖不存在: {cover_src}")
        cover_file = None

    # 5. 翻譯球隊新聞（每隊前3則）
    print("翻譯球隊新聞...")
    team_news = data.get("team_news", {})
    if team_news and has_llm():
        for tk, articles in team_news.items():
            if articles:
                # 每隊只翻譯前3則
                to_translate = articles[:3]
                translated = translate_news_batch(to_translate)
                team_news[tk] = translated
        data["team_news"] = team_news
    elif team_news:
        # LLM 不可用，使用原文
        for tk, articles in team_news.items():
            for article in articles:
                article["title_zh"] = article.get("title", "")

    # 6. 生成 HTML
    print("生成電子報 HTML...")
    html_content = generate_html(data, cover_file if cover_file else "")

    # 6. 寫入檔案
    html_path = today_dir / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"已生成: {html_path}")

    # 7. 更新報架索引
    update_rack_index(info)

    # 8. 部署
    print("部署到 GitHub Pages...")
    deploy_to_github()

    print(f"=== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    main()
