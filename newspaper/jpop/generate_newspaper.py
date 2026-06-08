#!/usr/bin/env python3
"""
JPOP流行報 - HTML 生成腳本 v2.0
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

# 解析命令列參數及環境變數以動態選擇 LLM 模型
parser = argparse.ArgumentParser(description="JPOP流行報生成器")
parser.add_argument(
    "--model",
    type=str,
    default=os.environ.get("AGY_MODEL", "Claude Opus 4.6 (Thinking)"),
    help="使用 agy 時指定的 LLM 模型"
)
args, _ = parser.parse_known_args()
AGY_MODEL = args.model

# ============================================================
# 設定
# ============================================================
NEWSPAPER_DIR = Path("/home/julianshen/projects/ebooksforme/newspaper/jpop")
GIT_DIR = Path("/home/julianshen/projects/ebooksforme")
COVERS_DIR = NEWSPAPER_DIR / "covers"

COVERS = ["cover-1.png", "cover-2.png", "cover-3.png", "cover-4.png", "cover-5.png"]

# ============================================================
# HTML 安全輔助函數
# ============================================================
ALLOWED_SCHEMES = {"https", "http"}


def h(value) -> str:
    """HTML escape 文字內容"""
    return html.escape(str(value or ""), quote=True)


def safe_url(value: str) -> str:
    """過濾 URL，只允許 http/https scheme"""
    value = str(value or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in ALLOWED_SCHEMES:
        return ""
    return html.escape(value, quote=True)


# ============================================================
# LLM 新聞翻譯
# ============================================================

def has_llm() -> bool:
    return shutil.which("codex") is not None or shutil.which("agy") is not None


def call_llm(prompt: str, timeout: int = 300) -> str | None:
    """呼叫本地 LLM 進行新聞翻譯/摘要 - 使用純文字模式避免 prompt injection"""
    # 安全過濾：移除可能引發 prompt injection 的控制字元
    safe_prompt = prompt.replace("\x00", "").replace("\x1b", "")

    # 1) agy（第一優先 - 純文字模式，用 stdin 傳遞 prompt）
    if shutil.which("agy"):
        try:
            proc = subprocess.Popen(
                ["agy", "--print", "--model", AGY_MODEL, "--print-timeout", f"{timeout}s"],
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

    # 2) codex CLI（備援 - 限制工作目錄）
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

    batch_size = 8
    results = []

    for i in range(0, len(news_items), batch_size):
        batch = news_items[i:i + batch_size]
        news_text = ""
        for idx, item in enumerate(batch):
            news_text += f"\n[{idx}] 標題: {item.get('title', '')}\n"
            news_text += f"    來源: {item.get('source', '')}\n"
            news_text += f"    摘要: {item.get('summary', '')[:400]}\n"

        prompt = f"""你是一位專業的日本音樂新聞編輯。請將以下日文新聞翻譯成繁體中文，並為每則新聞生成 50-80 字的中文摘要。

要求：
1. 標題翻譯要準確且吸引人
2. 摘要要涵蓋新聞重點
3. 歌曲名稱、藝人名稱保留日文原文
4. 直接回傳格式化的結果，不要額外解釋

輸出格式（嚴格遵守）：
[0] 中文標題: <翻譯後標題>
    摘要: <中文摘要>

[1] 中文標題: <翻譯後標題>
    摘要: <中文摘要>

（以此類推）

---
{news_text}"""

        print(f"  翻譯新聞批次 {i//batch_size + 1}/{(len(news_items)-1)//batch_size + 1}...")
        response = call_llm(prompt)

        if response:
            # 解析回傳結果
            for idx, item in enumerate(batch):
                pattern = rf"\[{idx}\]\s*中文標題:\s*(.+?)(?:\n|$)\s*摘要:\s*(.+?)(?:\n\[|$)"
                match = re.search(pattern, response, re.DOTALL)
                if match:
                    item["title_zh"] = match.group(1).strip()
                    item["summary_zh"] = match.group(2).strip()
                else:
                    item["title_zh"] = item.get("title", "")
                    item["summary_zh"] = item.get("summary", "")[:200]
        else:
            for item in batch:
                item["title_zh"] = item.get("title", "")
                item["summary_zh"] = item.get("summary", "")[:200]

        results.extend(batch)

    return results


# ============================================================
# HTML 生成
# ============================================================
def generate_html(data: dict) -> tuple[str, str]:
    """生成電子報 HTML，回傳 (html, cover_file)"""

    week_info = data.get("week_info", {})
    chart = data.get("chart", [])
    top_songs = data.get("top_songs", [])
    news = data.get("news", [])
    new_releases = data.get("new_releases", [])
    concerts = data.get("concerts", [])
    highlight = data.get("highlight", {})

    date_display = week_info.get("week_display", "")
    week_number = week_info.get("week_number", 1)
    year = week_info.get("year", 2026)

    # 封面輪用
    cover_index = (week_number - 1) % len(COVERS)
    cover_file = COVERS[cover_index]
    cover_src = f"images/{cover_file}"

    # ── Top 10 歌曲表格 ──
    chart_html = ""
    if top_songs:
        rows = ""
        for song in top_songs:
            rank = song.get("rank", "")
            title = h(song.get("title", ""))
            artist = h(song.get("artist", ""))
            last_rank = song.get("last_rank", "")
            weeks = h(song.get("weeks_on_chart", ""))
            yt = safe_url(song.get("youtube_url", ""))
            sp = safe_url(song.get("spotify_url", ""))

            # 排名變化
            trend = ""
            if last_rank and str(last_rank).isdigit():
                diff = int(last_rank) - int(rank)
                if diff > 0:
                    trend = f'<span class="trend-up">▲{diff}</span>'
                elif diff < 0:
                    trend = f'<span class="trend-down">▼{abs(diff)}</span>'
                else:
                    trend = '<span class="trend-same">→</span>'

            links = ""
            if yt:
                links += f'<a href="{yt}" target="_blank" class="link-yt" rel="noopener noreferrer">▶ YouTube</a>'
            if sp:
                links += f'<a href="{sp}" target="_blank" class="link-sp" rel="noopener noreferrer">♫ Spotify</a>'

            rows += f"""
                <tr>
                    <td class="rank-cell">{rank}</td>
                    <td class="song-cell">
                        <div class="song-title">{title}</div>
                        <div class="song-artist">{artist}</div>
                    </td>
                    <td class="trend-cell">{trend}</td>
                    <td class="weeks-cell">{weeks}週</td>
                    <td class="links-cell">{links}</td>
                </tr>"""

        chart_html = f"""
            <table class="chart-table">
                <thead>
                    <tr><th>#</th><th>歌曲</th><th>趨勢</th><th>週數</th><th>連結</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>"""
    else:
        chart_html = '<div class="empty-msg">暫時無法取得榜單資料</div>'

    # ── 本週焦點 ──
    highlight_html = ""
    if highlight:
        artist = h(highlight.get("artist", ""))
        song = h(highlight.get("song", ""))
        highlight_html = f"""
            <div class="highlight-card">
                <div class="highlight-badge">本週 No.1</div>
                <div class="highlight-song">{song}</div>
                <div class="highlight-artist">{artist}</div>
            </div>"""

    # ── 新聞區塊 ──
    news_html = ""
    if news:
        for article in news[:12]:
            title = h(article.get("title_zh", article.get("title", "")))
            summary = h(article.get("summary_zh", article.get("summary", ""))[:150])
            source = h(article.get("source", ""))
            url = safe_url(article.get("url", ""))
            image = safe_url(article.get("image", ""))
            date_str = h(article.get("date", ""))

            img_tag = f'<img src="{image}" alt="" class="news-thumb">' if image else ""
            link_start = f'<a href="{url}" target="_blank" rel="noopener noreferrer">' if url else ""
            link_end = "</a>" if url else ""

            news_html += f"""
            <div class="news-card">
                {img_tag}
                <div class="news-content">
                    <div class="news-meta">
                        <span class="news-source-tag">{source}</span>
                        <span class="news-date">{date_str}</span>
                    </div>
                    <h4 class="news-title">{link_start}{title}{link_end}</h4>
                    <p class="news-summary">{summary}</p>
                </div>
            </div>"""
    else:
        news_html = '<div class="empty-msg">暫時無法取得新聞資料</div>'

    # ── 新曲發行 ──
    releases_html = ""
    if new_releases:
        for rel in new_releases[:8]:
            title = h(rel.get("title", ""))
            artist = h(rel.get("artist", ""))
            date_str = h(rel.get("date", ""))
            url = safe_url(rel.get("url", ""))
            image = safe_url(rel.get("image", ""))

            img_tag = f'<img src="{image}" alt="" class="release-thumb">' if image else ""
            link_start = f'<a href="{url}" target="_blank" rel="noopener noreferrer">' if url else ""
            link_end = "</a>" if url else ""

            releases_html += f"""
            <div class="release-card">
                {img_tag}
                <div class="release-info">
                    {link_start}<div class="release-title">{title}</div>{link_end}
                    <div class="release-artist">{artist}</div>
                    <div class="release-date">{date_str}</div>
                </div>
            </div>"""
    else:
        releases_html = '<div class="empty-msg">暫時無法取得新曲資料</div>'

    # ── 演唱會 ──
    concerts_html = ""
    if concerts:
        for c in concerts[:8]:
            title = h(c.get("title", ""))
            artist = h(c.get("artist", ""))
            date_str = h(c.get("date", ""))
            venue = h(c.get("venue", ""))
            url = safe_url(c.get("url", ""))

            link_start = f'<a href="{url}" target="_blank" rel="noopener noreferrer">' if url else ""
            link_end = "</a>" if url else ""

            concerts_html += f"""
            <div class="concert-card">
                <div class="concert-date">{date_str}</div>
                <div class="concert-info">
                    {link_start}<div class="concert-title">{title}</div>{link_end}
                    <div class="concert-artist">{artist}</div>
                    <div class="concert-venue">{venue}</div>
                </div>
            </div>"""
    else:
        concerts_html = '<div class="empty-msg">暫時無法取得演唱會資料</div>'

    # ── 合併主模板 ──
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JPOP流行報 第{week_number}期 - {date_display}</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&family=Noto+Serif+TC:wght@600;900&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0f0f1a;
            --bg-card: #1a1a2e;
            --bg-hover: #252540;
            --text: #e8e8f0;
            --text-muted: #a0a0b8;
            --accent: #ff2a6d;
            --accent2: #05d9e8;
            --gold: #ffd700;
            --border: #2a2a45;
            --gradient-start: #ff2a6d;
            --gradient-end: #05d9e8;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Noto Sans TC', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            min-height: 100vh;
        }}
        .newspaper {{
            max-width: 900px;
            margin: 0 auto;
            background: var(--bg);
            min-height: 100vh;
        }}
        /* ── 封面 ── */
        .cover-banner {{
            width: 100%;
            border-radius: 0 0 16px 16px;
            overflow: hidden;
            margin-bottom: 24px;
            box-shadow: 0 0 40px rgba(255,42,109,0.15);
        }}
        .cover-banner img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        /* ── 報頭 ── */
        .masthead {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 2rem;
            text-align: center;
            border-bottom: 3px solid var(--accent);
        }}
        .tagline {{
            font-size: 0.85rem;
            letter-spacing: 0.4em;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 0.5rem;
            font-weight: 700;
        }}
        .title {{
            font-family: 'Noto Serif TC', serif;
            font-size: 3rem;
            font-weight: 900;
            letter-spacing: 0.15em;
            background: linear-gradient(90deg, var(--gradient-start), var(--gradient-end));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            font-size: 1rem;
            color: var(--text-muted);
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
            color: var(--text-muted);
        }}
        /* ── 內容區 ── */
        .content {{ padding: 2rem; }}
        .section {{ margin-bottom: 3rem; }}
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
            font-size: 1.6rem;
            font-weight: 900;
            flex: 1;
            color: var(--text);
        }}
        .section-icon {{
            font-size: 1.5rem;
        }}
        /* ── 焦點卡片 ── */
        .highlight-card {{
            background: linear-gradient(135deg, var(--bg-card), #252540);
            border-radius: 16px;
            padding: 2rem;
            text-align: center;
            border: 1px solid var(--border);
            position: relative;
            overflow: hidden;
        }}
        .highlight-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--gradient-start), var(--gradient-end));
        }}
        .highlight-badge {{
            display: inline-block;
            background: var(--accent);
            color: white;
            padding: 0.3rem 1rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 700;
            margin-bottom: 1rem;
        }}
        .highlight-song {{
            font-size: 2rem;
            font-weight: 900;
            color: var(--gold);
            margin-bottom: 0.5rem;
        }}
        .highlight-artist {{
            font-size: 1.2rem;
            color: var(--text-muted);
        }}
        /* ── 排行榜表格 ── */
        .chart-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95rem;
        }}
        .chart-table thead {{
            background: var(--bg-card);
        }}
        .chart-table th {{
            padding: 0.75rem 0.5rem;
            text-align: left;
            color: var(--accent2);
            font-weight: 700;
            border-bottom: 2px solid var(--accent);
        }}
        .chart-table td {{
            padding: 0.75rem 0.5rem;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}
        .rank-cell {{
            font-weight: 900;
            font-size: 1.2rem;
            color: var(--accent);
            width: 50px;
            text-align: center;
        }}
        .song-cell {{ min-width: 200px; }}
        .song-title {{ font-weight: 700; color: var(--text); }}
        .song-artist {{ font-size: 0.85rem; color: var(--text-muted); }}
        .trend-cell {{ width: 60px; text-align: center; }}
        .trend-up {{ color: #4ade80; }}
        .trend-down {{ color: #f87171; }}
        .trend-same {{ color: var(--text-muted); }}
        .weeks-cell {{ width: 60px; text-align: center; color: var(--text-muted); }}
        .links-cell {{ width: 150px; }}
        .links-cell a {{
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            text-decoration: none;
            margin-right: 0.3rem;
            margin-bottom: 0.2rem;
        }}
        .link-yt {{ background: #ff0000; color: white; }}
        .link-sp {{ background: #1db954; color: white; }}
        /* ── 新聞卡片 ── */
        .news-grid {{
            display: grid;
            gap: 1rem;
        }}
        .news-card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.25rem;
            border: 1px solid var(--border);
            display: flex;
            gap: 1rem;
            transition: background 0.2s;
        }}
        .news-card:hover {{ background: var(--bg-hover); }}
        .news-thumb {{
            width: 100px;
            height: 75px;
            object-fit: cover;
            border-radius: 8px;
            flex-shrink: 0;
        }}
        .news-content {{ flex: 1; }}
        .news-meta {{
            display: flex;
            gap: 0.75rem;
            margin-bottom: 0.5rem;
            font-size: 0.8rem;
        }}
        .news-source-tag {{
            background: rgba(255,42,109,0.2);
            color: var(--accent);
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            font-weight: 700;
        }}
        .news-date {{ color: var(--text-muted); }}
        .news-title {{
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            line-height: 1.4;
        }}
        .news-title a {{
            color: var(--text);
            text-decoration: none;
        }}
        .news-title a:hover {{ color: var(--accent2); }}
        .news-summary {{
            font-size: 0.9rem;
            color: var(--text-muted);
            line-height: 1.6;
        }}
        /* ── 新曲卡片 ── */
        .releases-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1rem;
        }}
        .release-card {{
            background: var(--bg-card);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
            transition: transform 0.2s;
        }}
        .release-card:hover {{ transform: translateY(-4px); }}
        .release-thumb {{
            width: 100%;
            height: 150px;
            object-fit: cover;
        }}
        .release-info {{ padding: 1rem; }}
        .release-title {{
            font-weight: 700;
            color: var(--text);
            margin-bottom: 0.3rem;
            font-size: 0.95rem;
        }}
        .release-artist {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 0.3rem;
        }}
        .release-date {{
            font-size: 0.8rem;
            color: var(--accent2);
        }}
        /* ── 演唱會卡片 ── */
        .concerts-grid {{
            display: grid;
            gap: 1rem;
        }}
        .concert-card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.25rem;
            border: 1px solid var(--border);
            display: flex;
            gap: 1rem;
            align-items: center;
        }}
        .concert-date {{
            background: linear-gradient(135deg, var(--accent), #ff6b9d);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-weight: 700;
            font-size: 0.9rem;
            text-align: center;
            min-width: 80px;
        }}
        .concert-info {{ flex: 1; }}
        .concert-title {{
            font-weight: 700;
            color: var(--text);
            margin-bottom: 0.3rem;
        }}
        .concert-artist {{
            font-size: 0.9rem;
            color: var(--text-muted);
        }}
        .concert-venue {{
            font-size: 0.85rem;
            color: var(--accent2);
            margin-top: 0.2rem;
        }}
        /* ── 空訊息 ── */
        .empty-msg {{
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            background: var(--bg-card);
            border-radius: 12px;
        }}
        /* ── 頁尾 ── */
        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }}
        /* ── 響應式 ── */
        @media (max-width: 600px) {{
            .content {{ padding: 1rem; }}
            .title {{ font-size: 2rem; }}
            .news-card {{ flex-direction: column; }}
            .news-thumb {{ width: 100%; height: 150px; }}
            .releases-grid {{ grid-template-columns: 1fr; }}
            .chart-table {{ font-size: 0.85rem; }}
            .links-cell {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="newspaper">
        <!-- 封面 -->
        <div class="cover-banner">
            <img src="{cover_src}" alt="JPOP流行報封面">
        </div>

        <!-- 報頭 -->
        <div class="masthead">
            <div class="tagline">Japanese Pop Music Weekly</div>
            <div class="title">JPOP流行報</div>
            <div class="subtitle">每週精選日本最新音樂情報</div>
            <div class="issue-info">
                <span>第 {week_number} 期</span>
                <span>{year}年</span>
                <span>{date_display}</span>
            </div>
        </div>

        <div class="content">
            <!-- 本週焦點 -->
            <div class="section">
                <div class="section-header">
                    <span class="section-icon">🎵</span>
                    <h2 class="section-title">本週焦點</h2>
                </div>
                {highlight_html}
            </div>

            <!-- 新歌速報 -->
            <div class="section">
                <div class="section-header">
                    <span class="section-icon">📊</span>
                    <h2 class="section-title">Billboard Japan Hot 100 Top 10</h2>
                </div>
                {chart_html}
            </div>

            <!-- 音樂新聞 -->
            <div class="section">
                <div class="section-header">
                    <span class="section-icon">📰</span>
                    <h2 class="section-title">音樂新聞</h2>
                </div>
                <div class="news-grid">
                    {news_html}
                </div>
            </div>

            <!-- 新曲發行 -->
            <div class="section">
                <div class="section-header">
                    <span class="section-icon">💿</span>
                    <h2 class="section-title">新曲發行</h2>
                </div>
                <div class="releases-grid">
                    {releases_html}
                </div>
            </div>

            <!-- 演唱會情報 -->
            <div class="section">
                <div class="section-header">
                    <span class="section-icon">🎤</span>
                    <h2 class="section-title">演唱會情報</h2>
                </div>
                <div class="concerts-grid">
                    {concerts_html}
                </div>
            </div>
        </div>

        <div class="footer">
            <p>JPOP流行報 第{week_number}期 | 自動生成於 {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
            <p>數據來源：Billboard Japan、音楽ナタリー、Billboard JAPAN、Model Press</p>
        </div>
    </div>
</body>
</html>"""

    return html, cover_file


# ============================================================
# 主流程
# ============================================================
def main():
    # 讀取最新 JSON
    data_dir = NEWSPAPER_DIR / "data"
    json_files = sorted(data_dir.glob("*.json"), reverse=True)
    if not json_files:
        print("錯誤：找不到數據檔案")
        sys.exit(1)

    json_path = json_files[0]
    print(f"讀取數據: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    week_info = data.get("week_info", {})
    date_str = week_info.get("date", datetime.now().strftime("%Y-%m-%d"))

    # 翻譯新聞
    news = data.get("news", [])
    if news:
        print(f"翻譯 {len(news)} 則新聞...")
        data["news"] = translate_news_batch(news)

    # 生成 HTML
    print("生成 HTML...")
    html, cover_file = generate_html(data)

    # 寫入檔案
    output_dir = NEWSPAPER_DIR / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / "index.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML 已寫入: {html_path}")

    # 複製封面圖
    if cover_file:
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        cover_src = COVERS_DIR / cover_file
        if cover_src.exists():
            shutil.copy2(cover_src, images_dir / cover_file)
            print(f"封面已複製: {cover_file}")

    # 清除舊期數（保留6期）
    clean_old_issues()

    return output_dir


def clean_old_issues():
    """清除超過6期的舊期數"""
    ISSUE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    dirs = [d for d in NEWSPAPER_DIR.iterdir() if d.is_dir() and ISSUE_DIR_RE.fullmatch(d.name)]
    dirs.sort(key=lambda d: d.name, reverse=True)

    if len(dirs) > 6:
        for old_dir in dirs[6:]:
            shutil.rmtree(old_dir)
            print(f"移除舊期數: {old_dir.name}")


if __name__ == "__main__":
    main()
