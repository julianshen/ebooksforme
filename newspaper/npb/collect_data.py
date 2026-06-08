#!/usr/bin/env python3
"""
日職每日報 - 數據收集腳本 v2.0
從 NPB 官方網站 + 日本運動媒體爬取真實數據

新聞來源:
- NPB 官網 (npb.jp/news/)
- 日刊スポーツ (nikkansports.com/baseball/)
- スポニチ (sponichi.co.jp/baseball/)
- スポーツ報知 (hochi.news/baseball/)
- Sports Bull (sportsbull.jp/baseball/)
- Baseball King (baseballking.jp/)
- Full-Count (full-count.jp/)

全部輸出為 JSON 供內容生成使用。無任何硬編碼假數據。
"""

import json
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# ============================================================
# 設定區
# ============================================================
NEWSPAPER_DIR = Path("/tmp/ebooksforme/newspaper/npb")
NPB_BASE_URL = "https://npb.jp"

HTTP_TIMEOUT = 20
NEWS_MAX_PER_SOURCE = 8  # 每個新聞來源最多取幾則

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("collect_data")

# ============================================================
# 球隊資料
# ============================================================
TEAMS = {
    "giants": {
        "name": "讀賣巨人", "name_jp": "読売ジャイアンツ", "short": "巨人",
        "official_url": "https://www.giants.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_g_l.gif",
        "stadium": "東京巨蛋", "league": "central", "code": "g",
    },
    "tigers": {
        "name": "阪神虎", "name_jp": "阪神タイガース", "short": "阪神",
        "official_url": "https://hanshintigers.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_t_l.gif",
        "stadium": "甲子園", "league": "central", "code": "t",
    },
    "carp": {
        "name": "廣島東洋鯉魚", "name_jp": "広島東洋カープ", "short": "広島",
        "official_url": "https://www.carp.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_c_l.gif",
        "stadium": "馬自達球場", "league": "central", "code": "c",
    },
    "baystars": {
        "name": "橫濱DeNA灣星", "name_jp": "横浜DeNAベイスターズ", "short": "DeNA",
        "official_url": "https://www.baystars.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_db_l.gif",
        "stadium": "橫濱球場", "league": "central", "code": "db",
    },
    "swallows": {
        "name": "東京養樂多燕子", "name_jp": "東京ヤクルトスワローズ", "short": "ヤクルト",
        "official_url": "https://www.yakult-swallows.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_s_l.gif",
        "stadium": "神宮球場", "league": "central", "code": "s",
    },
    "dragons": {
        "name": "中日龍", "name_jp": "中日ドラゴンズ", "short": "中日",
        "official_url": "https://www.dragons.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_d_l.gif",
        "stadium": "萬特力巨蛋", "league": "central", "code": "d",
    },
    "hawks": {
        "name": "福岡軟銀鷹", "name_jp": "福岡ソフトバンクホークス", "short": "ソフトバンク",
        "official_url": "https://www.softbankhawks.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_h_l.gif",
        "stadium": "雅虎巨蛋", "league": "pacific", "code": "h",
    },
    "fighters": {
        "name": "北海道日本火腿鬥士", "name_jp": "北海道日本ハムファイターズ", "short": "日本ハム",
        "official_url": "https://www.fighters.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_f_l.gif",
        "stadium": "札幌巨蛋", "league": "pacific", "code": "f",
    },
    "eagles": {
        "name": "東北樂天金鷲", "name_jp": "東北楽天ゴールデンイーグルス", "short": "楽天",
        "official_url": "https://www.rakuteneagles.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_e_l.gif",
        "stadium": "宮城球場", "league": "pacific", "code": "e",
    },
    "lions": {
        "name": "埼玉西武獅", "name_jp": "埼玉西武ライオンズ", "short": "西武",
        "official_url": "https://www.seibulions.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_l_l.gif",
        "stadium": "西武巨蛋", "league": "pacific", "code": "l",
    },
    "buffaloes": {
        "name": "歐力士猛牛", "name_jp": "オリックス・バファローズ", "short": "オリックス",
        "official_url": "https://www.buffaloes.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_b_l.gif",
        "stadium": "京瓷巨蛋", "league": "pacific", "code": "b",
    },
    "marines": {
        "name": "千葉羅德海洋", "name_jp": "千葉ロッテマリーンズ", "short": "ロッテ",
        "official_url": "https://www.marines.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_m_l.gif",
        "stadium": "ZOZO海洋球場", "league": "pacific", "code": "m",
    },
}

TEAM_ALT_TO_KEY = {
    "読売ジャイアンツ": "giants", "阪神タイガース": "tigers",
    "広島東洋カープ": "carp", "横浜DeNAベイスターズ": "baystars",
    "東京ヤクルトスワローズ": "swallows", "中日ドラゴンズ": "dragons",
    "福岡ソフトバンクホークス": "hawks", "北海道日本ハムファイターズ": "fighters",
    "東北楽天ゴールデンイーグルス": "eagles", "埼玉西武ライオンズ": "lions",
    "オリックス・バファローズ": "buffaloes", "千葉ロッテマリーンズ": "marines",
}

LOGO_CODE_TO_KEY = {
    "g": "giants", "t": "tigers", "c": "carp", "db": "baystars",
    "s": "swallows", "d": "dragons", "h": "hawks", "f": "fighters",
    "e": "eagles", "l": "lions", "b": "buffaloes", "m": "marines",
}

TEAM_ABBR_MAP = {
    "神": "tigers", "巨": "giants", "デ": "baystars", "中": "dragons",
    "広": "carp", "ヤ": "swallows", "鷹": "hawks", "日": "fighters",
    "楽": "eagles", "西": "lions", "オ": "buffaloes", "ロ": "marines",
    "ソ": "hawks", "ホ": "hawks", "ニ": "fighters", "ア": "fighters",
    "金": "eagles", "イ": "eagles", "バ": "buffaloes", "シ": "buffaloes",
    "マ": "marines", "ー": "marines",
}


def resolve_team_name(name_text: str) -> str:
    name_text = name_text.strip()
    if name_text in TEAM_ALT_TO_KEY:
        return TEAM_ALT_TO_KEY[name_text]
    m = re.search(r"logo_([a-z]+)_s\.gif", name_text)
    if m:
        code = m.group(1)
        if code in LOGO_CODE_TO_KEY:
            return LOGO_CODE_TO_KEY[code]
    for full_jp, key in TEAM_ALT_TO_KEY.items():
        if full_jp in name_text or name_text in full_jp:
            return key
    logger.warning("無法辨識的球隊名稱: '%s'", name_text)
    return name_text


# ============================================================
# HTTP 輔助
# ============================================================
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}


def fetch_soup(url: str, timeout: int = HTTP_TIMEOUT) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, timeout=timeout, headers=_HEADERS)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.error("請求失敗 %s: %s", url, e)
        return None


def fetch_text(url: str, timeout: int = HTTP_TIMEOUT) -> str | None:
    try:
        resp = requests.get(url, timeout=timeout, headers=_HEADERS)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    except Exception as e:
        logger.error("請求失敗 %s: %s", url, e)
        return None


# ============================================================
# 日期輔助
# ============================================================
def get_date_info():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    return {
        "today": today.strftime("%Y-%m-%d"),
        "today_display": today.strftime("%Y年%m月%d日"),
        "today_weekday": ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][today.weekday()],
        "yesterday": yesterday.strftime("%Y-%m-%d"),
        "yesterday_display": yesterday.strftime("%m月%d日"),
        "tomorrow": tomorrow.strftime("%Y-%m-%d"),
        "tomorrow_display": tomorrow.strftime("%m月%d日"),
        "year": today.year, "month": today.month, "day": today.day,
    }


# ============================================================
# NPB 數據爬取
# ============================================================
def fetch_standings():
    standings = {"central": [], "pacific": []}
    leagues = [
        ("central", f"{NPB_BASE_URL}/bis/{datetime.now().year}/stats/std_c.html"),
        ("pacific", f"{NPB_BASE_URL}/bis/{datetime.now().year}/stats/std_p.html"),
    ]
    for league_name, url in leagues:
        soup = fetch_soup(url)
        if soup is None:
            continue
        rows = soup.find_all("tr", class_="ststats")
        rank = 1
        for row in rows[:6]:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue
            team_name_jp = cells[0].get_text(strip=True)
            team_key = resolve_team_name(team_name_jp)
            team_info = TEAMS.get(team_key, {"name": team_name_jp, "name_jp": team_name_jp})
            standings[league_name].append({
                "rank": rank, "team": team_info["name"], "team_jp": team_info["name_jp"],
                "team_key": team_key, "games": cells[1].get_text(strip=True),
                "wins": cells[2].get_text(strip=True), "losses": cells[3].get_text(strip=True),
                "draws": cells[4].get_text(strip=True), "pct": cells[5].get_text(strip=True),
                "gb": cells[6].get_text(strip=True).replace("--", "-"),
            })
            rank += 1
    return standings


def _parse_score_box(score_box) -> dict | None:
    try:
        a_tag = score_box.find("a")
        detail_url = None
        if a_tag and a_tag.get("href"):
            href = a_tag["href"]
            detail_url = f"{NPB_BASE_URL}{href}" if href.startswith("/") else href
        imgs = score_box.find_all("img")
        home_team_key = away_team_key = None
        for img in imgs:
            cls = img.get("class", [])
            alt = img.get("alt", "")
            src = img.get("src", "")
            team_key = resolve_team_name(alt) or resolve_team_name(src) or alt
            if "logo_left" in cls:
                home_team_key = team_key
            elif "logo_right" in cls:
                away_team_key = team_key
        if not home_team_key and not away_team_key:
            return None
        score_div = score_box.find("div", class_="score")
        score_text = score_div.get_text(strip=True) if score_div else "*-*"
        home_score = away_score = ""
        if "-" in score_text:
            parts = score_text.split("-", 1)
            home_score = parts[0].strip()
            away_score = parts[1].strip()
        state_div = score_box.find("div", class_="state")
        stadium = status = ""
        if state_div:
            raw_text = state_div.get_text("\n", strip=True)
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            if lines:
                stadium = lines[0].strip("（）()").strip()
                if len(lines) > 1:
                    status = lines[-1]
        return {
            "home_team": TEAMS.get(home_team_key, {}).get("name", home_team_key) if home_team_key else "",
            "away_team": TEAMS.get(away_team_key, {}).get("name", away_team_key) if away_team_key else "",
            "home_team_key": home_team_key or "", "away_team_key": away_team_key or "",
            "home_score": home_score, "away_score": away_score,
            "stadium": stadium, "status": status, "detail_url": detail_url or "",
        }
    except Exception as e:
        logger.warning("解析 score_box 錯誤: %s", e)
        return None


def fetch_today_games():
    url = f"{NPB_BASE_URL}/bis/{datetime.now().year}/stats/std_c.html"
    soup = fetch_soup(url)
    if soup is None:
        soup = fetch_soup(f"{NPB_BASE_URL}/")
    if soup is None:
        return []
    header_score = soup.find("div", id="header_score")
    score_boxes = header_score.find_all("div", class_="score_box") if header_score else soup.find_all("div", class_="score_box")
    games = []
    for sb in score_boxes:
        classes = sb.get("class", [])
        if "date" in classes or "detail" in classes:
            continue
        game = _parse_score_box(sb)
        if game:
            games.append(game)
    logger.info("今日比賽: %d 場", len(games))
    return games


def _fetch_games_from_schedule(date_offset: int) -> list:
    target = datetime.now() + timedelta(days=date_offset)
    month_str = target.strftime("%m")
    day_str = target.strftime("%d")
    date_id = f"date{month_str}{day_str}"
    schedule_url = f"{NPB_BASE_URL}/games/{target.year}/schedule_{month_str}_detail.html"
    soup = fetch_soup(schedule_url)
    if soup is None:
        return []
    game_rows = soup.find_all("tr", id=date_id)
    games = []
    for row in game_rows:
        try:
            team1_div = row.find("div", class_="team1")
            team2_div = row.find("div", class_="team2")
            score1_div = row.find("div", class_="score1")
            score2_div = row.find("div", class_="score2")
            place_div = row.find("div", class_="place")
            time_div = row.find("div", class_="time")
            comm_div = row.find("div", class_="comment")
            pit_divs = row.find_all("div", class_="pit")
            a_tag = row.find("a")
            detail_url = None
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                detail_url = f"{NPB_BASE_URL}{href}" if href.startswith("/") else href

            home_team_name = team1_div.get_text(strip=True) if team1_div else ""
            away_team_name = team2_div.get_text(strip=True) if team2_div else ""
            home_score = score1_div.get_text(strip=True) if score1_div else ""
            away_score = score2_div.get_text(strip=True) if score2_div else ""
            place = place_div.get_text(strip=True) if place_div else ""
            game_time = time_div.get_text(strip=True) if time_div else ""
            comment = comm_div.get_text(strip=True) if comm_div else ""

            home_team_key = resolve_team_name(home_team_name)
            away_team_key = resolve_team_name(away_team_name)

            away_pitcher = home_pitcher = ""
            if len(pit_divs) >= 2:
                away_pitcher = pit_divs[0].get_text(strip=True)
                home_pitcher = pit_divs[1].get_text(strip=True)

            game = {
                "home_team": TEAMS.get(home_team_key, {}).get("name", home_team_name),
                "away_team": TEAMS.get(away_team_key, {}).get("name", away_team_name),
                "home_team_key": home_team_key, "away_team_key": away_team_key,
                "home_score": home_score, "away_score": away_score,
                "stadium": place, "time": game_time, "status": comment,
                "detail_url": detail_url or "",
                "home_pitcher": home_pitcher, "away_pitcher": away_pitcher,
            }
            games.append(game)
        except Exception as e:
            logger.warning("解析 schedule row 錯誤: %s", e)
    return games


def fetch_yesterday_games():
    games = _fetch_games_from_schedule(-1)
    # 補充詳細資訊
    for game in games:
        detail_url = game.get("detail_url", "")
        if detail_url:
            info = _fetch_game_detail(detail_url)
            if info:
                game.update(info)
    logger.info("昨日比賽: %d 場", len(games))
    return games


def fetch_tomorrow_games():
    games = _fetch_games_from_schedule(1)
    logger.info("明日賽程: %d 場", len(games))
    return games


def _fetch_game_detail(detail_url: str) -> dict | None:
    soup = fetch_soup(detail_url)
    if soup is None:
        return None
    result = {}
    try:
        game_info_p = soup.select_one("p.game_info")
        if game_info_p:
            info_text = game_info_p.get_text("\n", strip=True)
            start_time_m = re.search(r"開始\s*(\S+)", info_text)
            end_time_m = re.search(r"終了\s*(\S+)", info_text)
            duration_m = re.search(r"試合時間\s*(\S+)", info_text)
            attendance_m = re.search(r"入場者\s*([\d,]+)", info_text)
            if start_time_m: result["start_time"] = start_time_m.group(1)
            if end_time_m: result["end_time"] = end_time_m.group(1)
            if duration_m: result["duration"] = duration_m.group(1)
            if attendance_m: result["attendance"] = attendance_m.group(1).replace(",", "")
            if "試合終了" in info_text: result["status"] = "試合終了"
            elif "試合中" in info_text: result["status"] = "試合中"
            elif "中止" in info_text: result["status"] = "中止"
            elif "開始" in info_text: result["status"] = "開始前"

        result_section = soup.find("section", class_="game_result_info")
        if result_section:
            result_text = result_section.get_text("\n", strip=True)
            win_m = re.search(r"勝利投手[：:]\s*([^\n]+)", result_text)
            lose_m = re.search(r"敗戦投手[：:]\s*([^\n]+)", result_text)
            if win_m: result["winning_pitcher"] = win_m.group(1).strip()
            if lose_m: result["losing_pitcher"] = lose_m.group(1).strip()

            hr_headings = result_section.find_all("h4")
            for h4 in hr_headings:
                if "本塁打" in h4.get_text(strip=True):
                    hr_table = h4.find_next("table")
                    if hr_table:
                        home_runs = []
                        for tr in hr_table.find_all("tr"):
                            th = tr.find("th")
                            td = tr.find("td")
                            if th and td and td.get_text(strip=True):
                                home_runs.append({"team": th.get_text(strip=True), "detail": td.get_text(strip=True)})
                        result["home_runs"] = home_runs

        place_span = soup.find("span", class_="place")
        if place_span:
            result["stadium"] = place_span.get_text(strip=True)
    except Exception as e:
        logger.warning("解析詳細頁面 %s 錯誤: %s", detail_url, e)
    return result


def fetch_leaders():
    leaders = {
        "batting_avg_central": [], "batting_avg_pacific": [],
        "home_runs_central": [], "home_runs_pacific": [],
        "era_central": [], "era_pacific": [],
        "wins_central": [], "wins_pacific": [],
    }
    year = datetime.now().year

    for league, url in [("central", f"{NPB_BASE_URL}/bis/{year}/stats/bat_c.html"),
                        ("pacific", f"{NPB_BASE_URL}/bis/{year}/stats/bat_p.html")]:
        soup = fetch_soup(url)
        if soup is None:
            continue
        rows = soup.find_all("tr", class_="ststats")
        avg_key = f"batting_avg_{league}"
        hr_key = f"home_runs_{league}"
        for row in rows[:10]:
            cells = row.find_all("td")
            if len(cells) < 12:
                continue
            rank = cells[0].get_text(strip=True)
            player_cell = cells[1]
            player_name = player_cell.contents[0].strip() if player_cell.contents else ""
            stteam = player_cell.find("span", class_="stteam")
            team_code = stteam.get_text(strip=True).strip("()") if stteam else ""
            team_key = TEAM_ABBR_MAP.get(team_code, team_code)
            team_name = TEAMS.get(team_key, {}).get("name", team_code)
            avg_val = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            hr_val = cells[10].get_text(strip=True) if len(cells) > 10 else ""
            entry = {"rank": int(rank) if rank.isdigit() else rank, "player": player_name,
                     "team": team_name, "team_key": team_key, "value": ""}
            if avg_val:
                e = entry.copy(); e["value"] = avg_val; leaders[avg_key].append(e)
            if hr_val and hr_val != "0":
                e = entry.copy(); e["value"] = hr_val; leaders[hr_key].append(e)

    for league, url in [("central", f"{NPB_BASE_URL}/bis/{year}/stats/pit_c.html"),
                        ("pacific", f"{NPB_BASE_URL}/bis/{year}/stats/pit_p.html")]:
        soup = fetch_soup(url)
        if soup is None:
            continue
        rows = soup.find_all("tr", class_="ststats")
        era_key = f"era_{league}"
        wins_key = f"wins_{league}"
        for row in rows[:10]:
            cells = row.find_all("td")
            if len(cells) < 12:
                continue
            rank = cells[0].get_text(strip=True)
            player_cell = cells[1]
            player_name = player_cell.contents[0].strip() if player_cell.contents else ""
            stteam = player_cell.find("span", class_="stteam")
            team_code = stteam.get_text(strip=True).strip("()") if stteam else ""
            team_key = TEAM_ABBR_MAP.get(team_code, team_code)
            team_name = TEAMS.get(team_key, {}).get("name", team_code)
            era_val = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            wins_val = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            entry = {"rank": int(rank) if rank.isdigit() else rank, "player": player_name,
                     "team": team_name, "team_key": team_key, "value": ""}
            if era_val:
                e = entry.copy(); e["value"] = era_val; leaders[era_key].append(e)
            if wins_val and wins_val != "0":
                e = entry.copy(); e["value"] = wins_val; leaders[wins_key].append(e)

    return leaders


def fetch_interleague():
    year = datetime.now().year
    url = f"{NPB_BASE_URL}/bis/{year}/stats/std_inter.html"
    soup = fetch_soup(url)
    if soup is None:
        return {"central_wins": 0, "pacific_wins": 0, "leader": "unknown", "standings": []}
    rows = soup.find_all("tr", class_="ststats")
    inter_standings = []
    central_league_teams = {"giants", "tigers", "carp", "baystars", "swallows", "dragons"}
    pacific_league_teams = {"hawks", "fighters", "eagles", "lions", "buffaloes", "marines"}
    central_wins = pacific_wins = 0
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 7:
            continue
        team_name_jp = cells[0].get_text(strip=True)
        team_key = resolve_team_name(team_name_jp)
        team_info = TEAMS.get(team_key, {"name": team_name_jp, "name_jp": team_name_jp})
        wins = cells[2].get_text(strip=True)
        entry = {
            "team": team_info["name"], "team_jp": team_info["name_jp"], "team_key": team_key,
            "games": cells[1].get_text(strip=True), "wins": wins,
            "losses": cells[3].get_text(strip=True), "draws": cells[4].get_text(strip=True),
            "pct": cells[5].get_text(strip=True), "gb": cells[6].get_text(strip=True).replace("--", "-"),
        }
        inter_standings.append(entry)
        if team_key in central_league_teams and wins.isdigit():
            central_wins += int(wins)
        elif team_key in pacific_league_teams and wins.isdigit():
            pacific_wins += int(wins)
    leader = "central" if central_wins > pacific_wins else ("pacific" if pacific_wins > central_wins else "tie")
    return {"central_wins": central_wins, "pacific_wins": pacific_wins, "leader": leader, "standings": inter_standings}


# ============================================================
# 新聞爬取 - 多來源並行
# ============================================================

def fetch_npb_news() -> list:
    """NPB 官方新聞"""
    url = f"{NPB_BASE_URL}/news/npb_all.html"
    soup = fetch_soup(url)
    if soup is None:
        return []
    news = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a.get("href") or ""
        if len(text) > 10 and "news/detail" in href:
            full_url = f"{NPB_BASE_URL}{href}" if href.startswith("/") else href
            news.append({"title": text, "url": full_url, "source": "NPB官方", "date": "", "summary": ""})
        if len(news) >= NEWS_MAX_PER_SOURCE:
            break
    logger.info("NPB官方新聞: %d 則", len(news))
    return news


def fetch_nikkansports_news() -> list:
    """日刊スポーツ - 野球新聞"""
    url = "https://www.nikkansports.com/baseball/news/"
    soup = fetch_soup(url)
    if soup is None:
        return []
    news = []
    # 日刊スポーツ的新聞列表結構
    for item in soup.select("div.newslist__item, article.newslist__item, li.newslist__item")[:NEWS_MAX_PER_SOURCE]:
        a = item.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if href.startswith("/"):
            href = f"https://www.nikkansports.com{href}"
        elif not href.startswith("http"):
            href = f"https://www.nikkansports.com/baseball/{href}"
        # 日期
        date_el = item.select_one("time, span.date, div.newslist__date")
        date_str = date_el.get_text(strip=True) if date_el else ""
        # 摘要
        summary_el = item.select_one("p.newslist__text, div.newslist__text")
        summary = summary_el.get_text(strip=True) if summary_el else ""
        if title and len(title) > 5:
            news.append({"title": title, "url": href, "source": "日刊スポーツ", "date": date_str, "summary": summary[:300]})
    # 備用選擇器
    if not news:
        for item in soup.select("a[href*='/baseball/news/']")[:NEWS_MAX_PER_SOURCE]:
            title = item.get_text(strip=True)
            href = item.get("href", "")
            if not href.startswith("http"):
                href = f"https://www.nikkansports.com{href}" if href.startswith("/") else f"https://www.nikkansports.com/baseball/{href}"
            if title and len(title) > 5 and title not in [n["title"] for n in news]:
                news.append({"title": title, "url": href, "source": "日刊スポーツ", "date": "", "summary": ""})
    logger.info("日刊スポーツ: %d 則", len(news))
    return news


def fetch_sponichi_news() -> list:
    """スポニチ - 野球新聞"""
    url = "https://www.sponichi.co.jp/baseball/"
    soup = fetch_soup(url)
    if soup is None:
        return []
    news = []
    for item in soup.select("div.article, article.article, li.article")[:NEWS_MAX_PER_SOURCE]:
        a = item.find("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href") or ""
        if href.startswith("/"):
            href = f"https://www.sponichi.co.jp{href}"
        elif not href.startswith("http"):
            href = f"https://www.sponichi.co.jp/baseball/{href}"
        date_el = item.select_one("time, span.date")
        date_str = date_el.get_text(strip=True) if date_el else ""
        summary_el = item.select_one("p.summary, div.summary")
        summary = summary_el.get_text(strip=True) if summary_el else ""
        if title and len(title) > 5:
            news.append({"title": title, "url": href, "source": "スポニチ", "date": date_str, "summary": summary[:300]})
    if not news:
        for item in soup.select("a[href*='/baseball/news/']")[:NEWS_MAX_PER_SOURCE]:
            title = item.get_text(strip=True)
            href = item.get("href") or ""
            if not href.startswith("http"):
                href = f"https://www.sponichi.co.jp{href}" if href.startswith("/") else f"https://www.sponichi.co.jp/baseball/{href}"
            if title and len(title) > 5 and title not in [n["title"] for n in news]:
                news.append({"title": title, "url": href, "source": "スポニチ", "date": "", "summary": ""})
    logger.info("スポニチ: %d 則", len(news))
    return news


def fetch_hochi_news() -> list:
    """スポーツ報知 - 野球新聞"""
    url = "https://hochi.news/"
    soup = fetch_soup(url)
    if soup is None:
        return []
    news = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a.get("href") or ""
        if len(text) > 15 and "/articles/" in href:
            full_url = f"https://hochi.news{href}" if href.startswith("/") else href
            news.append({"title": text, "url": full_url, "source": "スポーツ報知", "date": "", "summary": ""})
        if len(news) >= NEWS_MAX_PER_SOURCE:
            break
    logger.info("スポーツ報知: %d 則", len(news))
    return news


def fetch_sportsbull_news() -> list:
    """Sports Bull - 野球新聞"""
    url = "https://sportsbull.jp/"
    soup = fetch_soup(url)
    if soup is None:
        return []
    news = []
    # Sports Bull 首頁主要是賽程表，新聞在 /p/ 或 /article/ 路徑
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a.get("href") or ""
        if len(text) > 15 and ("/p/" in href or "/article/" in href):
            full_url = f"https://sportsbull.jp{href}" if href.startswith("/") else href
            news.append({"title": text, "url": full_url, "source": "Sports Bull", "date": "", "summary": ""})
        if len(news) >= NEWS_MAX_PER_SOURCE:
            break
    logger.info("Sports Bull: %d 則", len(news))
    return news


def fetch_baseballking_news() -> list:
    """Baseball King"""
    url = "https://baseballking.jp/"
    soup = fetch_soup(url)
    if soup is None:
        return []
    news = []
    for item in soup.select("article.post, div.post, li.post")[:NEWS_MAX_PER_SOURCE]:
        a = item.find("a")
        if not a:
            continue
        title_el = item.select_one("h2, h3, .entry-title, .post-title")
        title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
        href = a.get("href", "")
        if not href.startswith("http"):
            href = f"https://baseballking.jp{href}" if href.startswith("/") else href
        date_el = item.select_one("time, span.date, .post-date")
        date_str = date_el.get_text(strip=True) if date_el else ""
        summary_el = item.select_one("p.summary, .entry-summary, p")
        summary = summary_el.get_text(strip=True) if summary_el else ""
        if title and len(title) > 5:
            news.append({"title": title, "url": href, "source": "Baseball King", "date": date_str, "summary": summary[:300]})
    if not news:
        for item in soup.select("a[href*='/npb/']")[:NEWS_MAX_PER_SOURCE]:
            title = item.get_text(strip=True)
            href = item.get("href", "")
            if not href.startswith("http"):
                href = f"https://baseballking.jp{href}" if href.startswith("/") else href
            if title and len(title) > 5 and title not in [n["title"] for n in news]:
                news.append({"title": title, "url": href, "source": "Baseball King", "date": "", "summary": ""})
    logger.info("Baseball King: %d 則", len(news))
    return news


def fetch_fullcount_news() -> list:
    """Full-Count"""
    url = "https://full-count.jp/category/npb/"
    soup = fetch_soup(url)
    if soup is None:
        return []
    news = []
    for item in soup.select("article.post, div.post, li.post")[:NEWS_MAX_PER_SOURCE]:
        a = item.find("a")
        if not a:
            continue
        title_el = item.select_one("h2, h3, .entry-title")
        title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
        href = a.get("href", "")
        if not href.startswith("http"):
            href = f"https://full-count.jp{href}" if href.startswith("/") else href
        date_el = item.select_one("time, span.date")
        date_str = date_el.get_text(strip=True) if date_el else ""
        summary_el = item.select_one("p.summary, .entry-summary")
        summary = summary_el.get_text(strip=True) if summary_el else ""
        if title and len(title) > 5:
            news.append({"title": title, "url": href, "source": "Full-Count", "date": date_str, "summary": summary[:300]})
    if not news:
        for item in soup.select("a[href*='/2026/']")[:NEWS_MAX_PER_SOURCE]:
            title = item.get_text(strip=True)
            href = item.get("href", "")
            if not href.startswith("http"):
                href = f"https://full-count.jp{href}" if href.startswith("/") else href
            if title and len(title) > 5 and title not in [n["title"] for n in news]:
                news.append({"title": title, "url": href, "source": "Full-Count", "date": "", "summary": ""})
    logger.info("Full-Count: %d 則", len(news))
    return news


def fetch_all_news() -> dict:
    """並行爬取所有新聞來源"""
    sources = {
        "npb": fetch_npb_news,
        "nikkansports": fetch_nikkansports_news,
        "sponichi": fetch_sponichi_news,
        "hochi": fetch_hochi_news,
        "sportsbull": fetch_sportsbull_news,
        "baseballking": fetch_baseballking_news,
        "fullcount": fetch_fullcount_news,
    }
    results = {}
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(fn): name for name, fn in sources.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                logger.error("新聞來源 %s 爬取失敗: %s", name, e)
                results[name] = []

    # 合併去重（依標題）
    all_news = []
    seen_titles = set()
    for source_name, news_list in results.items():
        for news in news_list:
            title_key = news["title"][:30]  # 前30字去重
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                all_news.append(news)

    logger.info("新聞合計: %d 則（去重後）", len(all_news))
    return {"by_source": results, "all": all_news}


# ============================================================
# Google News RSS - 球隊新聞
# ============================================================
def fetch_team_news(max_per_team=3):
    news = {}
    base_url = "https://news.google.com/rss/search"
    for team_key, team_info in TEAMS.items():
        query = f"{team_info['name_jp']} プロ野球"
        try:
            params = {"q": query, "hl": "ja", "gl": "JP"}
            resp = requests.get(base_url, params=params, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "xml")
            items = soup.find_all("item")
            team_news = []
            for item in items[:max_per_team]:
                title_el = item.find("title")
                source_el = item.find("source")
                link_el = item.find("link")
                title = title_el.text.strip() if title_el else ""
                source = source_el.text.strip() if source_el else ""
                link = link_el.text.strip() if link_el else ""
                if title:
                    team_news.append({"title": title, "source": source, "link": link})
            if team_news:
                news[team_key] = team_news
        except Exception as e:
            logger.warning("News fetch failed for %s: %s", team_key, e)
    return news


# ============================================================
# 主程式
# ============================================================
def main():
    logger.info("=== 數據收集開始 %s ===", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    date_info = get_date_info()

    logger.info("正在爬取戰績表...")
    standings = fetch_standings()

    logger.info("正在爬取今日比賽...")
    today_games = fetch_today_games()

    logger.info("正在爬取昨日比賽...")
    yesterday_games = fetch_yesterday_games()

    logger.info("正在爬取明日賽程...")
    tomorrow_games = fetch_tomorrow_games()

    logger.info("正在爬取個人排行榜...")
    leaders = fetch_leaders()

    logger.info("正在爬取交流戰戰績...")
    interleague = fetch_interleague()

    logger.info("正在爬取焦點新聞...")
    focus_news = fetch_all_news()

    logger.info("正在爬取球隊新聞...")
    team_news = fetch_team_news()

    data = {
        "date_info": date_info,
        "teams": TEAMS,
        "yesterday_games": yesterday_games,
        "today_games": today_games,
        "tomorrow_games": tomorrow_games,
        "standings": standings,
        "leaders": leaders,
        "interleague": interleague,
        "focus_news": focus_news,
        "team_news": team_news,
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    output_dir = NEWSPAPER_DIR / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{date_info['today']}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("數據已收集: %s", output_file)
    logger.info("=== 完成 %s ===", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return str(output_file)


if __name__ == "__main__":
    main()
