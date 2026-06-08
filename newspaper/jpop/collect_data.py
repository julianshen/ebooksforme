#!/usr/bin/env python3
"""
JPOP流行報 - 數據收集腳本 v2.0
從 Billboard Japan、音楽ナタリー、Billboard JAPAN 等真實來源爬取數據

全部輸出為 JSON 供內容生成使用。無任何硬編碼假數據。
"""

import json
import logging
import re
import sys
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# 設定區
# ============================================================
NEWSPAPER_DIR = Path("/home/julianshen/projects/ebooksforme/newspaper/jpop")
HTTP_TIMEOUT = 20
NEWS_MAX_PER_SOURCE = 10  # 每個新聞來源最多取幾則

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("collect_data")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}

# 建立帶 retry 的 session
_session = requests.Session()
_session.headers.update(_HEADERS)
_session.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
    ),
)


# ============================================================
# HTTP 輔助
# ============================================================
def fetch_soup(url: str, timeout: int = HTTP_TIMEOUT) -> BeautifulSoup | None:
    try:
        resp = _session.get(url, timeout=(5, timeout))
        resp.raise_for_status()
        # 信任 response header 的 encoding，而非強制 utf-8
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        logger.error("請求失敗 %s: %s", url, e)
        return None


def fetch_text(url: str, timeout: int = HTTP_TIMEOUT) -> str | None:
    try:
        resp = _session.get(url, timeout=(5, timeout))
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.error("請求失敗 %s: %s", url, e)
        return None


# ============================================================
# 日期資訊
# ============================================================
def get_week_info():
    """取得本週日期資訊"""
    today = datetime.now()
    # 週報以週日為基準
    days_since_sunday = today.weekday() + 1 if today.weekday() != 6 else 0
    week_start = today - timedelta(days=days_since_sunday)
    week_end = week_start + timedelta(days=6)
    week_number = today.isocalendar()[1]

    return {
        "date": today.strftime("%Y-%m-%d"),
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
        "week_display": f"{week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')}",
        "week_number": week_number,
        "year": today.year,
        "month": today.month,
        "day": today.day,
    }


# ============================================================
# 1. Billboard Japan Hot 100 榜單
# ============================================================
def fetch_billboard_chart():
    """
    從 Billboard Japan Hot 100 爬取當週榜單
    URL: https://www.billboard-japan.com/charts/detail?a=hot100
    """
    logger.info("爬取 Billboard Japan Hot 100...")
    songs = []
    url = "https://www.billboard-japan.com/charts/detail?a=hot100"
    soup = fetch_soup(url)
    if not soup:
        return songs

    # 解析排行榜表格 - 每首歌在 <tr class="rankN"> 中
    rows = soup.find_all("tr", class_=re.compile(r"rank\d+"))

    for row in rows:
        try:
            # 排名
            rank_td = row.select_one("td.rank_td span")
            if not rank_td:
                continue
            rank_text = rank_td.get_text(strip=True)
            if not rank_text.isdigit():
                continue
            rank = int(rank_text)

            # 曲名
            title_el = row.select_one("p.musuc_title")
            title = title_el.get_text(strip=True) if title_el else ""

            # 藝人
            artist_el = row.select_one("p.artist_name")
            artist = artist_el.get_text(strip=True) if artist_el else ""

            # 上週排名
            last_rank = ""
            last_span = row.select_one("span.last")
            if last_span:
                last_text = last_span.get_text(strip=True)
                m = re.search(r"前回：(\d+|-)", last_text)
                if m:
                    last_rank = m.group(1)

            # 週數
            weeks_on_chart = ""
            charts_span = row.select_one("span.charts_in")
            if charts_span:
                weeks_text = charts_span.get_text(strip=True)
                m = re.search(r"チャートイン：(\d+)", weeks_text)
                if m:
                    weeks_on_chart = m.group(1)

            if title and artist:
                songs.append({
                    "rank": rank,
                    "title": title,
                    "artist": artist,
                    "last_rank": last_rank,
                    "weeks_on_chart": weeks_on_chart,
                })
        except Exception as e:
            logger.debug("解析 Billboard 行失敗: %s", e)
            continue

    logger.info("Billboard Hot 100: 取得 %d 首", len(songs))
    if len(songs) < 10:
        logger.warning("Billboard Hot 100 解析筆數異常，僅取得 %d 首，請檢查 selector", len(songs))
    return songs


# ============================================================
# 2. 音楽ナタリー新聞（共用 soup）
# ============================================================
_natalie_soup_cache: BeautifulSoup | None = None


def _get_natalie_soup() -> BeautifulSoup | None:
    """共用 Natalie 首頁 soup，避免重複請求"""
    global _natalie_soup_cache
    if _natalie_soup_cache is None:
        _natalie_soup_cache = fetch_soup("https://natalie.mu/music")
    return _natalie_soup_cache


def fetch_natalie_news():
    """
    從音楽ナタリー (natalie.mu/music) 爬取音樂新聞
    新聞卡片 class: NA_card
    """
    logger.info("爬取 音楽ナタリー 新聞...")
    news = []
    soup = _get_natalie_soup()
    if not soup:
        return news

    # 新聞卡片: <div class="NA_card NA_card-topnews"> 或 <div class="NA_card NA_card-l">
    cards = soup.find_all("div", class_=re.compile(r"NA_card"))

    for card in cards[:NEWS_MAX_PER_SOURCE]:
        try:
            # 連結和標題在 <a> 內
            a_tag = card.find("a", href=re.compile(r"/music/news/\d+"))
            if not a_tag:
                continue

            href = a_tag.get("href", "")
            if href and not str(href).startswith("http"):
                href = f"https://natalie.mu{href}"

            # 標題
            title_el = a_tag.select_one("p.NA_card_title")
            title = title_el.get_text(strip=True) if title_el else ""

            # 摘要
            summary_el = a_tag.select_one("p.NA_card_summary")
            summary = summary_el.get_text(strip=True) if summary_el else ""

            # 圖片
            img_el = a_tag.select_one("img")
            image = img_el.get("src", "") if img_el else ""
            if image and image.startswith("//"):
                image = f"https:{image}"

            # 日期
            date_el = a_tag.select_one("div.NA_card_date")
            date_str = date_el.get_text(strip=True) if date_el else ""

            if title and href:
                news.append({
                    "title": title,
                    "url": href,
                    "summary": summary,
                    "image": image,
                    "date": date_str,
                    "source": "音楽ナタリー",
                })
        except Exception as e:
            logger.debug("解析 Natalie 新聞失敗: %s", e)
            continue

    logger.info("音楽ナタリー: 取得 %d 則", len(news))
    return news


# ============================================================
# 3. Billboard JAPAN 新聞
# ============================================================
def fetch_billboard_news():
    """
    從 Billboard JAPAN 新聞頁面爬取音樂新聞
    URL: https://www.billboard-japan.com/d_news/
    """
    logger.info("爬取 Billboard JAPAN 新聞...")
    news = []
    url = "https://www.billboard-japan.com/d_news/"
    soup = fetch_soup(url)
    if not soup:
        return news

    # 新聞列表: div.d_news__box 包含 h3 > a
    boxes = soup.find_all("div", class_="d_news__box")

    for box in boxes[:NEWS_MAX_PER_SOURCE]:
        try:
            h3 = box.find("h3")
            if not h3:
                continue
            a_tag = h3.find("a", href=re.compile(r"/d_news/detail/\d+"))
            if not a_tag:
                continue

            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if href and not str(href).startswith("http"):
                href = f"https://www.billboard-japan.com{href}"

            # 嘗試找日期
            date_str = ""
            date_el = box.select_one(".date, time")
            if date_el:
                date_str = date_el.get_text(strip=True)

            if title and href:
                news.append({
                    "title": title,
                    "url": href,
                    "summary": "",
                    "image": "",
                    "date": date_str,
                    "source": "Billboard JAPAN",
                })
        except Exception as e:
            logger.debug("解析 Billboard 新聞失敗: %s", e)
            continue

    logger.info("Billboard JAPAN: 取得 %d 則", len(news))
    return news


# ============================================================
# 4. Model Press 新聞
# ============================================================
def fetch_modelpress_news():
    """
    從 Model Press 爬取藝人/音樂新聞
    """
    logger.info("爬取 Model Press 新聞...")
    news = []
    url = "https://mdpr.jp/music"
    soup = fetch_soup(url)
    if not soup:
        return news

    # 新聞卡片
    articles = soup.select("article, .c-article-card, .article-item")

    for article in articles[:NEWS_MAX_PER_SOURCE]:
        try:
            title_el = article.select_one("h3, h2, .title")
            title = title_el.get_text(strip=True) if title_el else ""

            link_el = article.find("a")
            href = link_el.get("href", "") if link_el else ""
            if href and not str(href).startswith("http"):
                href = f"https://mdpr.jp{href}"

            summary_el = article.select_one("p, .description")
            summary = summary_el.get_text(strip=True) if summary_el else ""

            img_el = article.select_one("img")
            image = img_el.get("src", "") if img_el else ""

            if title and href:
                news.append({
                    "title": title,
                    "url": href,
                    "summary": summary,
                    "image": image,
                    "date": "",
                    "source": "Model Press",
                })
        except Exception as e:
            logger.debug("解析 Model Press 失敗: %s", e)
            continue

    logger.info("Model Press: 取得 %d 則", len(news))
    return news


# ============================================================
# 5. 新曲發行情報（從 Natalie 首頁新聞中篩選）
# ============================================================
def fetch_new_releases():
    """
    從音楽ナタリー新聞中篩選新曲發行相關新聞（共用 soup）
    """
    logger.info("爬取新曲發行情報...")
    releases = []
    soup = _get_natalie_soup()
    if not soup:
        return releases

    # 尋找包含「リリース」「シングル」「アルバム」的新聞
    cards = soup.find_all("div", class_=re.compile(r"NA_card"))

    keywords = ["リリース", "シングル", "アルバム", "配信", "CD", "新曲"]
    for card in cards:
        try:
            a_tag = card.find("a", href=re.compile(r"/music/news/\d+"))
            if not a_tag:
                continue

            title_el = a_tag.select_one("p.NA_card_title")
            title = title_el.get_text(strip=True) if title_el else ""

            # 檢查是否為新曲相關
            if not any(kw in title for kw in keywords):
                continue

            summary_el = a_tag.select_one("p.NA_card_summary")
            summary = summary_el.get_text(strip=True) if summary_el else ""

            href = a_tag.get("href", "")
            if href and not str(href).startswith("http"):
                href = f"https://natalie.mu{href}"

            img_el = a_tag.select_one("img")
            image = img_el.get("src", "") if img_el else ""
            if image and image.startswith("//"):
                image = f"https:{image}"

            # 嘗試從摘要提取藝人名
            artist = ""
            if summary:
                # 通常格式: 「藝人名」が... 或 藝人名が...
                m = re.match(r"^「?([^」]+)」?が", summary)
                if m:
                    artist = m.group(1)

            if title:
                releases.append({
                    "title": title,
                    "artist": artist,
                    "date": "",
                    "url": href,
                    "image": image,
                })
        except Exception as e:
            logger.debug("解析新曲失敗: %s", e)
            continue

    logger.info("新曲發行: 取得 %d 筆", len(releases))
    return releases


# ============================================================
# 6. 演唱會情報（從 Natalie 首頁新聞中篩選）
# ============================================================
def fetch_concert_info():
    """
    從音楽ナタリー新聞中篩選演唱會相關新聞（共用 soup）
    """
    logger.info("爬取演唱會情報...")
    concerts = []
    soup = _get_natalie_soup()
    if not soup:
        return concerts

    cards = soup.find_all("div", class_=re.compile(r"NA_card"))

    keywords = ["ライブ", "ツアー", "フェス", "公演", "コンサート", "出演", "開催"]
    for card in cards:
        try:
            a_tag = card.find("a", href=re.compile(r"/music/news/\d+"))
            if not a_tag:
                continue

            title_el = a_tag.select_one("p.NA_card_title")
            title = title_el.get_text(strip=True) if title_el else ""

            # 檢查是否為演唱會相關
            if not any(kw in title for kw in keywords):
                continue

            summary_el = a_tag.select_one("p.NA_card_summary")
            summary = summary_el.get_text(strip=True) if summary_el else ""

            href = a_tag.get("href", "")
            if href and not str(href).startswith("http"):
                href = f"https://natalie.mu{href}"

            # 嘗試提取日期和場地
            date_str = ""
            venue = ""
            if summary:
                # 尋找日期模式: X月X日 或 X/X
                m = re.search(r"(\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2})", summary)
                if m:
                    date_str = m.group(1)
                # 尋找場地: 在「会場」「場所」後
                m = re.search(r"(東京|大阪|名古屋|福岡|札幌|仙台|広島|横浜)[・\w]*", summary)
                if m:
                    venue = m.group(0)

            # 嘗試提取藝人名
            artist = ""
            if summary:
                m = re.match(r"^「?([^」]+)」?が", summary)
                if m:
                    artist = m.group(1)

            if title:
                concerts.append({
                    "title": title,
                    "artist": artist,
                    "date": date_str,
                    "venue": venue,
                    "url": href,
                })
        except Exception as e:
            logger.debug("解析演唱會失敗: %s", e)
            continue

    logger.info("演唱會: 取得 %d 筆", len(concerts))
    return concerts


# ============================================================
# 7. YouTube 連結搜尋
# ============================================================
def search_youtube_link(title: str, artist: str) -> str:
    """
    搜尋 YouTube 影片連結。回傳 youtu.be 短網址或空字串。
    """
    try:
        query = urllib.parse.quote(f"{title} {artist} MV")
        search_url = f"https://www.youtube.com/results?search_query={query}"
        text = fetch_text(search_url)
        if not text:
            return ""

        # 從 ytInitialData 中提取 videoId
        match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', text)
        if match:
            return f"https://youtu.be/{match.group(1)}"

        # 備用：從 watch?v= 提取
        match = re.search(r'watch\?v=([a-zA-Z0-9_-]{11})', text)
        if match:
            return f"https://youtu.be/{match.group(1)}"

        return ""
    except Exception as e:
        logger.debug("YouTube 搜尋失敗 %s - %s: %s", title, artist, e)
        return ""


# ============================================================
# 8. Spotify 搜尋連結
# ============================================================
def get_spotify_search_link(title: str, artist: str) -> str:
    """
    回傳 Spotify 搜尋頁面連結（Spotify 為動態應用，無法直接解析 track URL）
    """
    query = urllib.parse.quote(f"{title} {artist}")
    return f"https://open.spotify.com/search/{query}"


# ============================================================
# 主函數：收集所有數據
# ============================================================
def collect_all_data():
    """並行收集所有 JPOP 數據"""
    week_info = get_week_info()

    # 並行爬取各來源
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_chart = executor.submit(fetch_billboard_chart)
        future_natalie = executor.submit(fetch_natalie_news)
        future_bb_news = executor.submit(fetch_billboard_news)
        future_modelpress = executor.submit(fetch_modelpress_news)
        future_releases = executor.submit(fetch_new_releases)
        future_concerts = executor.submit(fetch_concert_info)

        def result_or_empty(name, future):
            try:
                return future.result()
            except Exception:
                logger.exception("%s 收集失敗", name)
                return []

        chart = result_or_empty("Billboard chart", future_chart)
        natalie_news = result_or_empty("Natalie news", future_natalie)
        bb_news = result_or_empty("Billboard news", future_bb_news)
        modelpress_news = result_or_empty("Model Press news", future_modelpress)
        releases = result_or_empty("New releases", future_releases)
        concerts = result_or_empty("Concert info", future_concerts)

    if not chart:
        logger.warning("Billboard chart 為空，請檢查 selector 或網站狀態")

    # 合併新聞並去重
    all_news = natalie_news + bb_news + modelpress_news
    seen_urls = set()
    unique_news = []
    for n in all_news:
        if n["url"] and n["url"] not in seen_urls:
            seen_urls.add(n["url"])
            unique_news.append(n)

    # 為 Top 10 歌曲搜尋 YouTube/Spotify 連結
    top_songs = [song.copy() for song in chart[:10]] if chart else []
    logger.info("為 Top %d 歌曲搜尋串流連結...", len(top_songs))
    for song in top_songs:
        song["youtube_url"] = search_youtube_link(song["title"], song["artist"])
        song["spotify_url"] = get_spotify_search_link(song["title"], song["artist"])

    # 本週焦點歌手（週榜冠軍）
    highlight = {}
    if chart:
        top_song = chart[0]
        highlight = {
            "artist": top_song["artist"],
            "song": top_song["title"],
            "rank": top_song["rank"],
        }

    data = {
        "has_data": len(chart) > 0 or len(unique_news) > 0,
        "collection_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "week_info": week_info,
        "highlight": highlight,
        "chart": chart,
        "top_songs": top_songs,
        "news": unique_news,
        "new_releases": releases,
        "concerts": concerts,
    }

    return data


# ============================================================
# 儲存 JSON
# ============================================================
def save_data(data: dict):
    """儲存數據到 JSON 檔案"""
    date_str = data["week_info"]["date"]
    data_dir = NEWSPAPER_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    json_path = data_dir / f"{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("數據已儲存: %s", json_path)
    return json_path


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("開始收集 JPOP 週報數據")
    logger.info("=" * 50)

    data = collect_all_data()
    json_path = save_data(data)

    # 簡易報告
    print(f"\n{'='*50}")
    print(f"數據收集完成: {json_path}")
    print(f"  榜單歌曲: {len(data.get('chart', []))} 首")
    print(f"  新聞: {len(data.get('news', []))} 則")
    print(f"  新曲發行: {len(data.get('new_releases', []))} 筆")
    print(f"  演唱會: {len(data.get('concerts', []))} 筆")
    print(f"{'='*50}")
