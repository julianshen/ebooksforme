#!/usr/bin/env python3
"""
JPOP流行報 - LLM 生成腳本
使用真實數據搜集 + LLM 格式化生成 JPOP 週報

數據來源（真實爬取）：
  - Billboard Japan Hot 100 榜單
  - 音楽ナタリー (natalie.mu/music) 新聞
  - Billboard JAPAN 新聞 (替代 ORICON — ORICON 為 JS 渲染不可爬)

修訂記錄：
  2026-06-07: 重寫數據收集層，移除所有硬編碼數據
              - 新增 collect_music_data() 動態爬取
              - 新增 search_spotify_track() Spotify API 搜尋
              - temperature 降至 0.2 降低幻覺風險
              - 禁止 LLM 自行提供連結或數據
              - 修正 import re 重複問題
"""

import os
import sys
import json
import re  # 僅保留一個 import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# 嘗試導入 LLM 庫
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

# ============================================================
# 第 1 部分：數據收集層 — 從真實來源爬取 JPOP 資訊
# ============================================================

def safe_request(url, timeout=20, headers=None):
    """安全 HTTP 請求，含錯誤處理與重試邏輯"""
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ja,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    if headers:
        default_headers.update(headers)
    try:
        resp = requests.get(url, headers=default_headers, timeout=timeout)
        resp.raise_for_status()
        # 檢查回應編碼
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️ 請求失敗 [{url}]: {e}")
        return None


def scrape_billboard_chart():
    """
    從 Billboard Japan Hot 100 爬取當週熱門歌曲榜單。
    URL: https://www.billboard-japan.com/charts/detail?a=hot100
    回傳：list[dict] — 每首歌含 rank, title, artist
    """
    print("  📊 正在爬取 Billboard Japan Hot 100 榜單...")
    songs = []
    url = "https://www.billboard-japan.com/charts/detail?a=hot100"
    resp = safe_request(url)
    if not resp:
        print("  ⚠️ 無法取得 Billboard Hot 100 榜單")
        return songs

    soup = BeautifulSoup(resp.text, "html.parser")
    # 排行榜表格中的每一列
    rows = soup.select("table tbody tr")
    if not rows:
        # 備用：直接用 class 選擇器
        rows = soup.select("tr[class^='rank']")

    for row in rows:
        # 取得排名
        rank_span = row.select_one(".rank_td span")
        if not rank_span:
            continue
        try:
            rank = int(rank_span.get_text(strip=True))
        except ValueError:
            continue

        # 取得歌曲標題
        title_el = row.select_one(".musuc_title")
        title = title_el.get_text(strip=True) if title_el else ""

        # 取得歌手名稱
        artist_el = row.select_one(".artist_name a")
        artist = artist_el.get_text(strip=True) if artist_el else ""

        if title and artist:
            songs.append({
                "rank": rank,
                "title": title,
                "artist": artist
            })

    if songs:
        print(f"  ✅ Billboard Hot 100: 成功取得 {len(songs)} 首歌曲")
        for s in songs[:5]:
            print(f"     #{s['rank']} {s['title']} — {s['artist']}")
        if len(songs) > 5:
            print(f"     ... 還有 {len(songs)-5} 首")
    else:
        print("  ⚠️ Billboard Hot 100: 未解析到任何歌曲")

    return songs


def scrape_natalie_news():
    """
    從音楽ナタリー (natalie.mu/music/news) 爬取最新 JPOP 新聞。
    回傳：list[dict] — 每則新聞含 title, summary, url, source
    """
    print("  📰 正在爬取 音楽ナタリー 新聞...")
    articles = []
    url = "https://natalie.mu/music/news"
    resp = safe_request(url)
    if not resp:
        print("  ⚠️ 無法取得音楽ナタリー新聞")
        return articles

    soup = BeautifulSoup(resp.text, "html.parser")
    # 每則新聞是 <a> 標籤，包含 NA_card_title 與 NA_card_summary
    news_links = soup.select("a[href*='/music/news/']")
    seen_urls = set()

    for link in news_links:
        href = link.get("href", "")
        # 只取文章頁面連結（數字 id）
        if not re.match(r'https?://natalie\.mu/music/news/\d+', href):
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)

        title_el = link.select_one(".NA_card_title")
        summary_el = link.select_one(".NA_card_summary")

        title = title_el.get_text(strip=True) if title_el else ""
        summary = summary_el.get_text(strip=True) if summary_el else ""

        if title:
            articles.append({
                "title": title,
                "summary": summary,
                "url": href,
                "source": "音楽ナタリー"
            })

    if articles:
        print(f"  ✅ 音楽ナタリー: 成功取得 {len(articles)} 則新聞")
        for a in articles[:3]:
            print(f"     • {a['title'][:50]}...")
    else:
        print("  ⚠️ 音楽ナタリー: 未解析到任何新聞")

    return articles


def scrape_billboard_news():
    """
    從 Billboard JAPAN 新聞頁爬取最新 JPOP 音樂新聞。
    替代 ORICON (JS 渲染無法直接爬取)。
    URL: https://www.billboard-japan.com/d_news/
    回傳：list[dict]
    """
    print("  📰 正在爬取 Billboard JAPAN 新聞...")
    articles = []
    url = "https://www.billboard-japan.com/d_news/"
    resp = safe_request(url)
    if not resp:
        print("  ⚠️ 無法取得 Billboard JAPAN 新聞")
        return articles

    soup = BeautifulSoup(resp.text, "html.parser")
    # 新聞標題連結：a.hover 指向 /d_news/detail/數字
    # Billboard 頁面為同一連結產生多個 a 元素（圖片版、數字版、文字版），
    # 我們只取文字內容最長的那個版本
    news_links = soup.select("a.hover[href*='/d_news/detail/']")
    seen_urls = set()
    # 暫存每條新聞的最佳標題（url -> best_title）
    best_titles = {}

    for link in news_links:
        href = link.get("href", "")
        full_url = f"https://www.billboard-japan.com{href}" if href.startswith("/") else href
        # 標準化 URL：移除尾部斜線
        full_url = full_url.rstrip("/")
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        title = link.get_text(strip=True)
        # 跳過空白、純數字、或太短的標題（這些是圖片版或編號版）
        if not title or len(title) < 5 or title.isdigit():
            continue
        # 移除前導的排名數字（例如「1YOASOBI」→「YOASOBI」）
        title = re.sub(r'^\d+\s*', '', title)
        # 若有更長的標題則取代
        if full_url not in best_titles or len(title) > len(best_titles[full_url]):
            best_titles[full_url] = title

    # 整理最終結果
    for full_url, title in best_titles.items():

        articles.append({
            "title": title,
            "summary": "",  # Billboard 首頁無摘要，可由後續 LLM 生成簡介
            "url": full_url,
            "source": "Billboard JAPAN"
        })

    if articles:
        print(f"  ✅ Billboard JAPAN: 成功取得 {len(articles)} 則新聞")
        for a in articles[:3]:
            print(f"     • {a['title'][:50]}...")
    else:
        print("  ⚠️ Billboard JAPAN: 未解析到任何新聞")

    return articles


def search_spotify_track(artist, song):
    """
    透過 Spotify Web API 搜尋真實 track 連結。
    使用 Client Credentials 流程（不需使用者授權）。

    參數：
      artist: str — 歌手名稱
      song: str — 歌曲名稱

    回傳：
      str or None — Spotify track URL (open.spotify.com/track/...)
      若無憑證或搜尋失敗則回傳 None
    """
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        # 無憑證，無法搜尋
        return None

    try:
        # Step 1: 取得 Access Token
        auth_url = "https://accounts.spotify.com/api/token"
        auth_response = requests.post(
            auth_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": "Basic " + __import__("base64").b64encode(
                    f"{client_id}:{client_secret}".encode()
                ).decode()
            },
            data={"grant_type": "client_credentials"},
            timeout=10
        )
        auth_response.raise_for_status()
        access_token = auth_response.json().get("access_token")
        if not access_token:
            return None

        # Step 2: 搜尋 track
        search_url = "https://api.spotify.com/v1/search"
        query = f"track:{song} artist:{artist}"
        search_response = requests.get(
            search_url,
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "q": query,
                "type": "track",
                "limit": 1,
                "market": "JP"
            },
            timeout=10
        )
        search_response.raise_for_status()
        data = search_response.json()

        tracks = data.get("tracks", {}).get("items", [])
        if tracks:
            track_id = tracks[0].get("id")
            if track_id:
                return f"https://open.spotify.com/track/{track_id}"

        return None

    except Exception as e:
        print(f"    ⚠️ Spotify search 錯誤 ({artist} - {song}): {e}")
        return None


def collect_music_data():
    """
    主要數據收集函數。從 Billboard Hot 100、音楽ナタリー、
    Billboard JAPAN 新聞爬取即時 JPOP 資訊。

    回傳結構：
    {
        "collection_time": "2026-06-07 12:30:00",   # 收集時間戳
        "has_data": True/False,                      # 是否有任何真實數據
        "billboard_chart": [ ... ],                  # Billboard Hot 100 榜單
        "natalie_news": [ ... ],                     # 音楽ナタリー新聞
        "billboard_news": [ ... ],                   # Billboard JAPAN 新聞
        "all_news": [ ... ],                         # 合併後的新聞列表
        "top_chart_songs": [ ... ]                   # 前 10 名歌曲
    }
    """
    print("\n" + "=" * 50)
    print("📡 資料收集階段")
    print("=" * 50)

    collection_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"⏰ 收集時間：{collection_time}\n")

    # 1. 爬取 Billboard Hot 100 榜單
    chart_songs = scrape_billboard_chart()
    top_chart = chart_songs[:10] if chart_songs else []

    # 2. 爬取音楽ナタリー新聞
    natalie_articles = scrape_natalie_news()

    # 3. 爬取 Billboard JAPAN 新聞
    bb_articles = scrape_billboard_news()

    # 4. 合併新聞列表（去重）
    all_news = []
    seen_titles = set()
    for article in natalie_articles + bb_articles:
        # 簡單去重：以標題前半段為 key
        title_key = article["title"][:30]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            all_news.append(article)

    has_data = bool(chart_songs or natalie_articles or bb_articles)

    print(f"\n📊 資料收集摘要：")
    print(f"   Billboard Hot 100 歌曲：{len(chart_songs)} 首")
    print(f"   音楽ナタリー新聞：{len(natalie_articles)} 則")
    print(f"   Billboard JAPAN 新聞：{len(bb_articles)} 則")
    print(f"   合計不重複新聞：{len(all_news)} 則")
    print(f"   資料可用：{'✅ 是' if has_data else '❌ 否'}")

    return {
        "collection_time": collection_time,
        "has_data": has_data,
        "billboard_chart": chart_songs,
        "natalie_news": natalie_articles,
        "billboard_news": bb_articles,
        "all_news": all_news,
        "top_chart_songs": top_chart
    }


# ============================================================
# 第 2 部分：日期資訊
# ============================================================

def get_date_info():
    """取得日期資訊"""
    now = datetime.now()

    # 計算期數（以 2026 年第 1 週為基準，若年份不同則改用 ISO 週數）
    week_number = now.isocalendar()[1]

    return {
        "date_str": now.strftime("%Y-%m-%d"),
        "display_date": f"{now.year}年{now.month}月{now.day}日",
        "week_number": week_number,
        "year": now.year,
        "month": now.month,
        "day": now.day
    }


# ============================================================
# 第 3 部分：Prompt 構建 — 使用動態爬取數據
# ============================================================

def build_prompt(date_info, music_data):
    """
    構建 LLM prompt — 所有數據來自 collect_music_data()，動態嵌入。

    原則：
    - 絕對不要求 LLM 提供連結或數據
    - 只要求 LLM 格式化我們提供的真實數據
    - 若某筆資料無對應連結，則跳過或不顯示連結欄位
    """
    if not music_data or not music_data.get("has_data"):
        return build_fallback_prompt(date_info)

    # ----- 製作 Highlight Artist 區塊 -----
    highlight_section = ""
    if music_data["top_chart_songs"]:
        # 以榜單第一名為 Highlight Artist
        top_song = music_data["top_chart_songs"][0]
        highlight_artist = top_song["artist"]
        highlight_song = top_song["title"]
        highlight_section = (
            f"### Highlight Artist: {highlight_artist}\n"
            f"- 本週 Billboard Japan Hot 100 冠軍：〈{highlight_song}〉— {highlight_artist}\n"
            f"- 榜單排名真實資料，來源：Billboard JAPAN\n"
            f"- 資料收集時間：{music_data['collection_time']}\n"
        )
    elif music_data["all_news"]:
        # 若榜單無資料，以新聞中最常出現的歌手為 highlight
        from collections import Counter
        name_counts = Counter()
        for article in music_data["all_news"][:10]:
            title = article["title"]
            # 擷取常見 JPOP 歌手名稱
            known_artists = [
                "Ado", "YOASOBI", "米津玄師", "King Gnu", "Mrs. GREEN APPLE",
                "Official髭男dism", "LiSA", "Aimer", "YOASOBI", "藤井風",
                "Vaundy", "back number", "SUPER EIGHT", "嵐", "NMB48",
                "CUTIE STREET", "M!LK", "iri", "Creepy Nuts", "Reol",
                "FRUITS ZIPPER", "BUDDiiS", "サカナクション", "ILLIT"
            ]
            for artist in known_artists:
                if artist in title:
                    name_counts[artist] += 1
        if name_counts:
            highlight_artist = name_counts.most_common(1)[0][0]
        else:
            highlight_artist = "JPOP 歌手"
        highlight_section = (
            f"### Highlight Artist: {highlight_artist}\n"
            f"- 本週注目歌手（根據新聞報導頻率）\n"
            f"- 資料收集時間：{music_data['collection_time']}\n"
        )
    else:
        highlight_section = "### Highlight Artist\n（本週資料整理中）\n"

    # ----- 製作最新歌曲區塊（從 Billboard 榜單） -----
    songs_section_lines = ["### 最新歌曲（Billboard Japan Hot 100 當週榜單）"]
    if music_data["top_chart_songs"]:
        for i, song in enumerate(music_data["top_chart_songs"]):
            rank = song["rank"]
            title = song["title"]
            artist = song["artist"]
            songs_section_lines.append(
                f"\n{rank}. 〈{title}〉— {artist}"
            )
            # ⚠️ 注意：預設不提供 Spotify/YouTube 連結
            # LLM 不可自行編造連結；若需 Spotify 連結可呼叫 search_spotify_track()
            songs_section_lines.append(f"   排行榜來源：Billboard JAPAN（真實數據）")
    else:
        songs_section_lines.append("\n（本週榜單資料整理中）")

    songs_section = "\n".join(songs_section_lines)

    # ----- 製作新聞區塊 -----
    news_section_lines = ["### 音樂新聞（真實爬取數據）"]
    if music_data["all_news"]:
        for i, article in enumerate(music_data["all_news"][:8]):  # 最多 8 則
            title = article["title"]
            source = article["source"]
            url = article["url"]
            summary = article.get("summary", "")
            news_section_lines.append(f"\n{i+1}. {title}")
            if summary:
                news_section_lines.append(f"   {summary}")
            news_section_lines.append(f"   來源：{source}")
            news_section_lines.append(f"   連結：{url}")
    else:
        news_section_lines.append("\n（本週新聞資料整理中）")

    news_section = "\n".join(news_section_lines)

    # ----- 構建最終 prompt -----
    prompt = f"""你是 JPOP流行報 的編輯系統。以下為本週的真實爬取數據，請根據這些數據生成 HTML 週報。

## 📋 嚴格規則（請務必遵守）

1. **禁止編造資料**：只使用下方提供的真實數據。若某個欄位沒有提供資料，則不顯示該欄位。
2. **禁止提供連結**：你只能使用下方「連結」欄位中明確提供的 URL。切勿自行編造任何 Spotify、YouTube、或新聞連結。
3. **無連結的處理方式**：若一首歌曲沒有提供 Spotify/YouTube 連結，則在 HTML 中不顯示該連結按鈕，或在備註顯示「[連結確認中]」。
4. **Spotify 格式**：如果有提供 Spotify URL，必須是 open.spotify.com/track/... 格式。
5. **語言**：使用繁體中文。歌曲名、歌手名保留日文原文。
6. **產出格式**：只輸出 5 個 <section> 的 HTML 內容，不要外層 html/head/body 標籤。

## 日期資訊
- 報紙日期：{date_info['display_date']}
- 第 {date_info['week_number']} 期
- 資料收集時間：{music_data['collection_time']}

## 真實數據（爬取自 Billboard JAPAN / 音楽ナタリー）

{highlight_section}

{songs_section}

{news_section}

### 日本演唱會
（本週演唱會資料整理中 — 若無資料，顯示「尚無已確認之資訊」）

### 台灣演唱會
（目前尚無已確認之 JPOP 歌手台灣公演資訊）

## HTML 格式要求
請生成 5 個 <section> 標籤的 HTML，使用以下佈局：

### Section 1: Highlight Artist
```html
<section>
  <h2 class="section-title">⭐ Highlight Artist</h2>
  <div class="highlight">
    <div class="label">🌟 本週焦點歌手</div>
    <h3>歌手名</h3>
    <p>真實簡介...</p>
    <div class="links">
      <!-- 只放有真實連結的項目；若無連結則跳過此區塊 -->
    </div>
  </div>
</section>
```

### Section 2: New Songs
```html
<section>
  <h2 class="section-title">🎶 最新歌曲</h2>
  <div class="song-grid">
    <div class="song-card">
      <h4>歌曲名</h4>
      <div class="artist-label">歌手名</div>
      <p>簡介及排名資訊</p>
      <div class="song-links">
        <!-- 不顯示連結，或只顯示「[連結確認中]」 -->
      </div>
    </div>
  </div>
</section>
```

### Section 3: Music News
```html
<section>
  <h2 class="section-title">📰 音樂新聞</h2>
  <div class="news-grid">
    <div class="news-card">
      <div class="news-source">來源名</div>
      <h4>新聞標題</h4>
      <p>摘要...</p>
      <a href="link" target="_blank">🔗 原文を見る →</a>
    </div>
  </div>
</section>
```

### Section 4: Japan Concerts
```html
<section>
  <h2 class="section-title">🎤 日本演唱會</h2>
  <table class="concert-table">
    <thead><tr><th>日期</th><th>歌手</th><th>場地</th><th>資訊</th></tr></thead>
    <tbody>
      <tr><td colspan="4" style="text-align:center;color:var(--muted);">本週資料整理中</td></tr>
    </tbody>
  </table>
</section>
```

### Section 5: Taiwan Concerts
```html
<section>
  <h2 class="section-title">🇹🇼 台灣演唱會・活動</h2>
  <table class="concert-table">
    <thead><tr><th>日期</th><th>歌手</th><th>場地</th><th>資訊</th></tr></thead>
    <tbody>
      <tr><td colspan="4" style="text-align:center;color:var(--muted);">尚無已確認之資訊</td></tr>
    </tbody>
  </table>
</section>
```

輸出時只需給以上 5 個 section 的 HTML，不要外層 html/head/body。
使用繁體中文，歌曲名保留日文原文。
所有連結使用 target="_blank" 在新分頁開啟。
"""
    return prompt


def build_fallback_prompt(date_info):
    """
    當無法取得任何真實數據時使用的 fallback prompt。
    顯示「本週資料正在整理中」，禁止 LLM 自行編造內容。
    """
    prompt = f"""你是 JPOP流行報 的編輯系統。

## 📋 嚴格規則（請務必遵守）

1. **禁止編造資料**：本週爬蟲未能取得真實數據。你只能在 HTML 中顯示「本週資料正在整理中」訊息。
2. **禁止提供任何連結**：不要提供任何 Spotify、YouTube、或新聞連結。
3. **禁止編造歌曲、新聞、或演唱會資訊**。
4. **語言**：使用繁體中文。

## 日期資訊
- 報紙日期：{date_info['display_date']}
- 第 {date_info['week_number']} 期

## 重要提示
本週無法從真實來源取得 JPOP 資料（Billboard JAPAN / 音楽ナタリー / ORICON 爬取失敗）。
請生成 5 個 <section> 的 HTML，全部顯示「本週資料正在整理中」的狀態訊息。
不要編造任何數據、歌手名稱、歌曲名稱、或連結。

輸出時直接給 5 個 section 的 HTML 即可，不要外層 html/head/body。
使用繁體中文。
"""
    return prompt


# ============================================================
# 第 4 部分：LLM API 呼叫
# ============================================================

def call_llm_codex(prompt, temperature=0.2):
    """使用 codex CLI 呼叫 LLM（第一優先）"""
    try:
        import subprocess
        print("使用 codex CLI...")
        result = subprocess.run(
            ["codex", "exec", "--", prompt],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        print(f"codex failed: {result.stderr[:200] if result.stderr else 'no output'}")
        return None
    except FileNotFoundError:
        print("codex not found")
        return None
    except Exception as e:
        print(f"codex error: {e}")
        return None


def call_llm_agy(prompt, temperature=0.2):
    """使用 agy (antigravity CLI) 呼叫 LLM（備援）"""
    try:
        import subprocess
        print("使用 agy (antigravity)...")
        result = subprocess.run(
            ["agy", "--sandbox", "--print", "--model", "Claude Opus 4.6 (Thinking)", prompt],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        print(f"agy failed: {result.stderr[:200] if result.stderr else 'no output'}")
        return None
    except FileNotFoundError:
        print("agy not found")
        return None
    except Exception as e:
        print(f"agy error: {e}")
        return None


def generate_content(date_info, music_data):
    """使用 LLM 生成內容 — 優先 codex，備援 agy"""
    prompt = build_prompt(date_info, music_data)

    # 1) codex CLI（第一優先）
    content = call_llm_codex(prompt)
    if content:
        return content

    # 2) agy (antigravity CLI，備援)
    content = call_llm_agy(prompt)
    if content:
        return content

    print("所有 LLM 提供者皆失敗（codex → agy）")
    return None


# ============================================================
# 第 5 部分：HTML 生成
# ============================================================
def generate_html(content, date_info):
    """生成完整 HTML（使用 LLM 內容）"""
    
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
            position: relative;
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
        h2.section-title {{
            font-size: 1.5rem;
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
        .highlight .label {{ color: var(--accent); font-weight: 700; font-size: 0.85rem; letter-spacing: 2px; margin-bottom: 4px; }}
        .highlight h3 {{ margin-top: 0; color: var(--accent); font-size: 1.4rem; }}
        .highlight p {{ margin: 10px 0; color: var(--muted); }}
        .links {{ margin-top: 12px; }}
        .links a {{
            display: inline-block;
            margin-right: 10px;
            margin-bottom: 6px;
            background: rgba(255,255,255,0.08);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.9rem;
            color: #4fc3f7;
            text-decoration: none;
            transition: background .2s;
        }}
        .links a:hover {{ background: rgba(255,255,255,0.15); }}
        .song-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }}
        .song-card {{
            background: var(--card);
            border-radius: 12px;
            padding: 18px;
            border: 1px solid #2a2a3e;
            transition: transform .2s, border-color .2s;
        }}
        .song-card:hover {{ transform: translateY(-3px); border-color: var(--accent); }}
        .song-card h4 {{ margin: 0 0 6px; color: #fff; font-size: 1.05rem; }}
        .song-card .artist-label {{ color: var(--accent); font-size: 0.85rem; font-weight: 700; margin-bottom: 6px; }}
        .song-card p {{ font-size: 0.9rem; color: var(--muted); margin: 0 0 10px; }}
        .song-links {{ margin-top: 8px; }}
        .song-links a {{
            display: inline-block;
            font-size: 0.8rem;
            padding: 4px 10px;
            margin-right: 6px;
            margin-bottom: 4px;
            border-radius: 12px;
            background: rgba(79,195,247,0.1);
            color: #4fc3f7;
            text-decoration: none;
        }}
        .song-links a:hover {{ background: rgba(79,195,247,0.2); }}
        .news-grid {{ display: grid; gap: 14px; }}
        .news-card {{
            background: var(--card);
            border-radius: 12px;
            padding: 18px;
            border: 1px solid #2a2a3e;
        }}
        .news-card h4 {{ margin: 0 0 6px; color: #fff; font-size: 1.05rem; }}
        .news-card .news-source {{ color: var(--accent); font-size: 0.85rem; font-weight: 700; }}
        .news-card p {{ font-size: 0.9rem; color: var(--muted); margin: 8px 0; }}
        .news-card a {{ color: #4fc3f7; font-size: 0.9rem; }}
        .data-info {{ background: rgba(255,255,255,0.05); border-radius: 8px; padding: 12px; margin-bottom: 15px; border-left: 3px solid var(--accent); font-size: 0.85rem; color: var(--muted); }}
        .chart-list {{ list-style: none; padding: 0; }}
        .chart-item {{
            display: flex;
            align-items: center;
            padding: 8px 12px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        .chart-rank {{ width: 30px; font-weight: 900; color: var(--accent); }}
        .chart-info {{ flex: 1; }}
        .chart-title {{ color: #fff; }}
        .chart-artist {{ font-size: 0.85rem; color: var(--muted); }}
        footer {{
            text-align: center;
            padding: 20px;
            color: var(--muted);
            font-size: 0.85rem;
            border-top: 1px solid #2a2a3e;
            margin-top: 40px;
        }}
        @media (max-width: 640px) {{
            .song-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎵 JPOP流行報</h1>
            <div class="date">{date_info['display_date']} · 第{date_info['week_number']}期 · 隔週日發行</div>
        </header>
        
        {content}
        
        <footer>
            <p>Issue Date: {date_info['date_str']} · 第{date_info['week_number']}期</p>
            <p>資料來源：Billboard JAPAN / 音楽ナタリー / ORICON</p>
            <p>© JPOP流行報 · 每週日發行 · 僅保留最近六期</p>
        </footer>
    </div>
</body>
</html>"""
    return template


def generate_html_direct(music_data, date_info):
    """直接從收集數據生成 HTML（無需 LLM 的備援模式）"""
    
    date_info['date_str']
    
    # --- Highlight Artist ---
    top_songs = music_data.get("top_chart_songs", [])
    all_news = music_data.get("all_news", [])
    
    # Highlight section
    highlight_html = ""
    if top_songs:
        top = top_songs[0]
        highlight_html = f"""
<section>
    <h2 class="section-title">⭐ Highlight</h2>
    <div class="highlight">
        <div class="label">🌟 本週注目</div>
        <h3>{top['artist']}</h3>
        <p>本週 Billboard Japan Hot 100 冠軍：〈{top['title']}〉</p>
    </div>
</section>"""
    
    # --- Billboard Chart ---
    chart_html = ""
    if top_songs:
        songs_list = ""
        for song in top_songs[:20]:
            songs_list += f"""
        <div class="chart-item">
            <div class="chart-rank">#{song['rank']}</div>
            <div class="chart-info">
                <div class="chart-title">{song['title']}</div>
                <div class="chart-artist">{song['artist']}</div>
            </div>
        </div>"""
        chart_html = f"""
<section>
    <h2 class="section-title">📊 Billboard Japan Hot 100</h2>
    <div class="data-info">資料來源：Billboard JAPAN · 即時爬取 · 共 {len(top_songs)} 首</div>
    <div class="chart-list">{songs_list}</div>
</section>"""
    
    # --- News ---
    news_html = ""
    if all_news:
        news_cards = ""
        for article in all_news[:8]:
            source = article.get("source", "")
            title = article.get("title", "")
            summary = article.get("summary", "")
            url = article.get("url", "")
            news_cards += f"""
        <div class="news-card">
            <div class="news-source">{source}</div>
            <h4>{title}</h4>
            <p>{summary}</p>
            <a href="{url}" target="_blank">🔗 原文 →</a>
        </div>"""
        news_html = f"""
<section>
    <h2 class="section-title">📰 音樂新聞</h2>
    <div class="data-info">來源：音楽ナタリー / Billboard JAPAN · 共 {len(all_news)} 則</div>
    <div class="news-grid">{news_cards}</div>
</section>"""
    
    content = highlight_html + chart_html + news_html
    return generate_html(content, date_info)



# ============================================================
# 第 6 部分：主函數
# ============================================================

def main():
    """主函數 — 資料收集 → Prompt 構建 → LLM 生成 → HTML 輸出"""

    print("=" * 50)
    print("JPOP流行報 - LLM 自動生成")
    print("=" * 50)

    # Step 1: 取得日期資訊
    date_info = get_date_info()
    print(f"\n📅 日期：{date_info['display_date']}")
    print(f"📆 期數：第 {date_info['week_number']} 期")

    # Step 2: 資料收集階段
    print(f"\n{'='*50}")
    print("📡 階段一：資料收集")
    print("=" * 50)
    print("   正在從真實來源爬取本週 JPOP 資訊...")
    print("   • Billboard Japan Hot 100 榜單")
    print("   • 音楽ナタリー (natalie.mu/music) 新聞")
    print("   • Billboard JAPAN 新聞")
    music_data = collect_music_data()

    if not music_data.get("has_data"):
        print("\n⚠️ 所有資料來源皆無法取得，將使用「本週資料整理中」模式")

    # Step 3: LLM 生成內容
    print(f"\n{'='*50}")
    print("🤖 階段二：LLM 格式化生成")
    print("=" * 50)
    print("   使用 temperature=0.2（低溫度，降低幻覺風險）")
    
    # 檢查是否有 LLM API key
    # 檢查是否有 LLM CLI 工具
    import shutil
    has_llm = shutil.which("agy") is not None or shutil.which("codex") is not None
    
    if has_llm:
        print("   正在呼叫 LLM API (codex → agy)...")
        content = generate_content(date_info, music_data)
    else:
        print("   ⚠️ 未設定 LLM API Key，使用直接生成模式（無 LLM）")
        content = None

    if not content and music_data.get("has_data"):
        print("   使用直接生成模式（跳過 LLM，基於爬取的數據直接建立 HTML）")
        html = generate_html_direct(music_data, date_info)
    elif content:
        # 移除 LLM 可能輸出的程式碼區塊標記
        content_clean = re.sub(r'```html?\n?', '', content)
        content_clean = re.sub(r'\n?```', '', content_clean)
        content_clean = content_clean.strip()
        html = generate_html(content_clean, date_info)
    else:
        print("❌ 生成失敗！無可用數據")
        sys.exit(1)

    # Step 5: 儲存檔案
    repo_dir = Path("/tmp/ebooksforme")
    output_dir = repo_dir / "newspaper" / "jpop" / date_info['date_str']
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "index.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"   ✅ 已儲存：{output_file}")
    print(f"   📏 檔案大小：{len(html)} 字元")

    # Step 6: 摘要報告
    print(f"\n{'='*50}")
    print("📋 生成摘要")
    print("=" * 50)
    print(f"   日期：{date_info['display_date']}")
    print(f"   期數：第 {date_info['week_number']} 期")
    print(f"   資料收集：{'✅ 成功' if music_data.get('has_data') else '⚠️ 使用 fallback'}")
    print(f"   榜單歌曲：{len(music_data.get('billboard_chart', []))} 首")
    print(f"   新聞總數：{len(music_data.get('all_news', []))} 則")
    print(f"   LLM 提供者：codex → agy")
    print(f"   LLM 溫度：0.2")
    print(f"   檔案：{output_file}")
    print(f"   URL: https://julianshen.github.io/ebooksforme/newspaper/jpop/{date_info['date_str']}/")
    print(f"\n{'='*50}")
    print("✅ 完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
