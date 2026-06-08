#!/usr/bin/env python3
"""
日職每日報 - 數據收集腳本
從 NPB 官方網站爬取真實數據：賽程、戰績、排名等
全部輸出為 JSON 供內容生成使用

注意：本檔案所有數據均從 NPB 官方網站即時爬取，無任何硬編碼假數據。
"""

import json
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ============================================================
# 設定區
# ============================================================
NEWSPAPER_DIR = Path("/home/julianshen/projects/ebooksforme/newspaper")
NPB_BASE_URL = "https://npb.jp"

# 請求超時（秒）
HTTP_TIMEOUT = 20

# 設定 logging
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
        "name": "讀賣巨人",
        "name_jp": "読売ジャイアンツ",
        "short": "巨人",
        "official_url": "https://www.giants.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_g_l.gif",
        "stadium": "東京巨蛋",
        "league": "central",
        "code": "g",
    },
    "tigers": {
        "name": "阪神虎",
        "name_jp": "阪神タイガース",
        "short": "阪神",
        "official_url": "https://hanshintigers.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_t_l.gif",
        "stadium": "甲子園",
        "league": "central",
        "code": "t",
    },
    "carp": {
        "name": "廣島東洋鯉魚",
        "name_jp": "広島東洋カープ",
        "short": "広島",
        "official_url": "https://www.carp.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_c_l.gif",
        "stadium": "馬自達球場",
        "league": "central",
        "code": "c",
    },
    "baystars": {
        "name": "橫濱DeNA灣星",
        "name_jp": "横浜DeNAベイスターズ",
        "short": "DeNA",
        "official_url": "https://www.baystars.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_db_l.gif",
        "stadium": "橫濱球場",
        "league": "central",
        "code": "db",
    },
    "swallows": {
        "name": "東京養樂多燕子",
        "name_jp": "東京ヤクルトスワローズ",
        "short": "ヤクルト",
        "official_url": "https://www.yakult-swallows.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_s_l.gif",
        "stadium": "神宮球場",
        "league": "central",
        "code": "s",
    },
    "dragons": {
        "name": "中日龍",
        "name_jp": "中日ドラゴンズ",
        "short": "中日",
        "official_url": "https://www.dragons.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_d_l.gif",
        "stadium": "萬特力巨蛋",
        "league": "central",
        "code": "d",
    },
    "hawks": {
        "name": "福岡軟銀鷹",
        "name_jp": "福岡ソフトバンクホークス",
        "short": "ソフトバンク",
        "official_url": "https://www.softbankhawks.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_h_l.gif",
        "stadium": "雅虎巨蛋",
        "league": "pacific",
        "code": "h",
    },
    "fighters": {
        "name": "北海道日本火腿鬥士",
        "name_jp": "北海道日本ハムファイターズ",
        "short": "日本ハム",
        "official_url": "https://www.fighters.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_f_l.gif",
        "stadium": "札幌巨蛋",
        "league": "pacific",
        "code": "f",
    },
    "eagles": {
        "name": "東北樂天金鷲",
        "name_jp": "東北楽天ゴールデンイーグルス",
        "short": "楽天",
        "official_url": "https://www.rakuteneagles.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_e_l.gif",
        "stadium": "宮城球場",
        "league": "pacific",
        "code": "e",
    },
    "lions": {
        "name": "埼玉西武獅",
        "name_jp": "埼玉西武ライオンズ",
        "short": "西武",
        "official_url": "https://www.seibulions.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_l_l.gif",
        "stadium": "西武巨蛋",
        "league": "pacific",
        "code": "l",
    },
    "buffaloes": {
        "name": "歐力士猛牛",
        "name_jp": "オリックス・バファローズ",
        "short": "オリックス",
        "official_url": "https://www.buffaloes.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_b_l.gif",
        "stadium": "京瓷巨蛋",
        "league": "pacific",
        "code": "b",
    },
    "marines": {
        "name": "千葉羅德海洋",
        "name_jp": "千葉ロッテマリーンズ",
        "short": "ロッテ",
        "official_url": "https://www.marines.co.jp/",
        "logo": "https://p.npb.jp/img/common/logo/2026/logo_m_l.gif",
        "stadium": "ZOZO海洋球場",
        "league": "pacific",
        "code": "m",
    },
}

# 建立名稱查找用對照表
# 全名（日文）→ 英文 key
FULL_NAME_TO_KEY = {v["name_jp"]: k for k, v in TEAMS.items()}
# 短名（日文）→ 英文 key
SHORT_NAME_TO_KEY = {v["short"]: k for k, v in TEAMS.items()}
# 額外短名對應（schedule 頁面可能出現的變體）
EXTRA_SHORT_NAMES = {
    "巨人": "giants",
    "阪神": "tigers",
    "広島": "carp",
    "DeNA": "baystars",
    "ヤクルト": "swallows",
    "中日": "dragons",
    "ソフトバンク": "hawks",
    "日本ハム": "fighters",
    "楽天": "eagles",
    "西武": "lions",
    "オリックス": "buffaloes",
    "ロッテ": "marines",
}
SHORT_NAME_TO_KEY.update(EXTRA_SHORT_NAMES)

# 從 img alt 屬性中的全名對應
TEAM_ALT_TO_KEY = {
    "読売ジャイアンツ": "giants",
    "阪神タイガース": "tigers",
    "広島東洋カープ": "carp",
    "横浜DeNAベイスターズ": "baystars",
    "東京ヤクルトスワローズ": "swallows",
    "中日ドラゴンズ": "dragons",
    "福岡ソフトバンクホークス": "hawks",
    "北海道日本ハムファイターズ": "fighters",
    "東北楽天ゴールデンイーグルス": "eagles",
    "埼玉西武ライオンズ": "lions",
    "オリックス・バファローズ": "buffaloes",
    "千葉ロッテマリーンズ": "marines",
}

# 從 img src 中的 logo code（如 logo_g_s.gif 中的 g）對應 key
LOGO_CODE_TO_KEY = {
    "g": "giants",
    "t": "tigers",
    "c": "carp",
    "db": "baystars",
    "s": "swallows",
    "d": "dragons",
    "h": "hawks",
    "f": "fighters",
    "e": "eagles",
    "l": "lions",
    "b": "buffaloes",
    "m": "marines",
}


def resolve_team_name(name_text: str) -> str:
    """
    嘗試將各種日文球隊名稱轉換為 TEAMS 的 key。
    先後嘗試：全名比對 → logo code 比對 → 短名比對。
    若無法辨識則回傳原始字串。
    """
    name_text = name_text.strip()
    # 先試全名
    if name_text in TEAM_ALT_TO_KEY:
        return TEAM_ALT_TO_KEY[name_text]
    # 試試 logo code 嵌入（如 "logo_g_s.gif"）
    m = re.search(r"logo_([a-z]+)_s\.gif", name_text)
    if m:
        code = m.group(1)
        if code in LOGO_CODE_TO_KEY:
            return LOGO_CODE_TO_KEY[code]
    # 試短名
    if name_text in SHORT_NAME_TO_KEY:
        return SHORT_NAME_TO_KEY[name_text]
    # 試試是否為完整名稱的變體（去掉中間空格等）
    for full_jp, key in FULL_NAME_TO_KEY.items():
        if full_jp in name_text or name_text in full_jp:
            return key
    logger.warning("無法辨識的球隊名稱: '%s'", name_text)
    return name_text


# ============================================================
# 日期輔助
# ============================================================
def get_date_info():
    """取得日期資訊，包括今天、昨天、明天的格式化字串"""
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
        "year": today.year,
        "month": today.month,
        "day": today.day,
    }


def fetch_soup(url: str) -> BeautifulSoup | None:
    """安全的 HTTP GET + BeautifulSoup 解析，附錯誤處理與 timeout"""
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.Timeout:
        logger.error("請求超時: %s", url)
    except requests.exceptions.RequestException as e:
        logger.error("請求失敗 %s: %s", url, e)
    except Exception as e:
        logger.error("解析錯誤 %s: %s", url, e)
    return None


# ============================================================
# 爬取戰績表（中央聯盟 + 太平洋聯盟）
# ============================================================
def fetch_standings():
    """
    從 NPB 官方網站爬取聯盟戰績表。
    - 中央聯盟：https://npb.jp/bis/2026/stats/std_c.html
    - 太平洋聯盟：https://npb.jp/bis/2026/stats/std_p.html

    解析 <tr class="ststats"> 中的前 6 筆（例行賽排名），
    提取：team, games, wins, losses, draws, pct, gb
    """
    standings = {"central": [], "pacific": []}
    leagues = [
        ("central", f"{NPB_BASE_URL}/bis/2026/stats/std_c.html"),
        ("pacific", f"{NPB_BASE_URL}/bis/2026/stats/std_p.html"),
    ]

    for league_name, url in leagues:
        soup = fetch_soup(url)
        if soup is None:
            logger.warning("無法取得 %s 戰績頁面，回傳空列表", league_name)
            continue

        rows = soup.find_all("tr", class_="ststats")
        if not rows:
            logger.warning("在 %s 戰績頁面找不到 ststats 行", league_name)
            continue

        # 前 6 行為例行賽排名（後面的是交流戰等其他分組）
        rank = 1
        for row in rows[:6]:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            team_name_jp = cells[0].get_text(strip=True)
            team_key = resolve_team_name(team_name_jp)
            team_info = TEAMS.get(team_key, {"name": team_name_jp, "name_jp": team_name_jp})

            entry = {
                "rank": rank,
                "team": team_info["name"],
                "team_jp": team_info["name_jp"],
                "team_key": team_key,
                "games": cells[1].get_text(strip=True),
                "wins": cells[2].get_text(strip=True),
                "losses": cells[3].get_text(strip=True),
                "draws": cells[4].get_text(strip=True),
                "pct": cells[5].get_text(strip=True),
                "gb": cells[6].get_text(strip=True).replace("--", "-"),
            }
            standings[league_name].append(entry)
            rank += 1

        logger.info(
            "%s 戰績: 取得 %d 隊資料",
            "中央聯盟" if league_name == "central" else "太平洋聯盟",
            len(standings[league_name]),
        )

    return standings


# ============================================================
# 爬取比賽列表（從 header_score 或 schedule 頁面）
# ============================================================
def _parse_score_box(score_box) -> dict | None:
    """
    從 <div class="score_box"> 解析單一比賽資料（header 用）。
    回傳 dict 包含：away_team, home_team, away_score, home_score, stadium, status, detail_url
    """
    try:
        # 取得連結（比賽詳細頁）
        a_tag = score_box.find("a")
        detail_url = None
        if a_tag and a_tag.get("href"):
            href = a_tag["href"]
            if href.startswith("/"):
                detail_url = f"{NPB_BASE_URL}{href}"
            else:
                detail_url = href

        # 解析兩隊 logo
        imgs = score_box.find_all("img")
        home_team_key = None
        away_team_key = None
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

        # 解析比數
        score_div = score_box.find("div", class_="score")
        score_text = score_div.get_text(strip=True) if score_div else "*-*"

        # 比數格式通常為 "2-2"、"*-*"（因雨中斷）
        home_score = ""
        away_score = ""
        if "-" in score_text:
            parts = score_text.split("-", 1)
            home_score = parts[0].strip()
            away_score = parts[1].strip()

        # 解析 stadium / 狀態
        state_div = score_box.find("div", class_="state")
        stadium = ""
        status = ""
        if state_div:
            raw_text = state_div.get_text("\n", strip=True)
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            if lines:
                stadium_raw = lines[0]
                # 去掉日文括號
                stadium = stadium_raw.strip("（）()").strip()
                if len(lines) > 1:
                    status = lines[-1]

        game = {
            "home_team": TEAMS.get(home_team_key, {}).get("name", home_team_key) if home_team_key else "",
            "away_team": TEAMS.get(away_team_key, {}).get("name", away_team_key) if away_team_key else "",
            "home_team_key": home_team_key or "",
            "away_team_key": away_team_key or "",
            "home_score": home_score,
            "away_score": away_score,
            "stadium": stadium,
            "status": status,
            "detail_url": detail_url or "",
        }
        return game
    except Exception as e:
        logger.warning("解析 score_box 時發生錯誤: %s", e)
        return None


def fetch_today_games():
    """
    爬取今日比賽。
    NPB 每頁 header 都有 <div id="header_score"> 內含今日即時比分。
    我們利用這個來取得今天的比賽資料。
    """
    # 用任何 NPB 頁面都可以取得 header 中的 score_box
    # 用 standings 頁面作為來源
    url = f"{NPB_BASE_URL}/bis/2026/stats/std_c.html"
    soup = fetch_soup(url)
    if soup is None:
        # 備用：嘗試其他頁面
        url = f"{NPB_BASE_URL}/"
        soup = fetch_soup(url)

    if soup is None:
        logger.error("無法取得任何 NPB 頁面來解析今日比賽")
        return []

    header_score = soup.find("div", id="header_score")
    if header_score is None:
        logger.warning("找不到 header_score，嘗試從任何 score_box 解析")
        score_boxes = soup.find_all("div", class_="score_box")
    else:
        score_boxes = header_score.find_all("div", class_="score_box")

    games = []
    for sb in score_boxes:
        # 跳過 date 和 detail 類型的盒子
        classes = sb.get("class", [])
        if "date" in classes or "detail" in classes:
            continue
        game = _parse_score_box(sb)
        if game:
            games.append(game)

    logger.info("今日比賽: 取得 %d 場", len(games))
    return games


def fetch_yesterday_games():
    """
    爬取昨日比賽結果。
    使用 schedule 明細頁面（schedule_MM_detail.html）中昨日日期的比賽資料。
    """
    date_info = get_date_info()
    yesterday = datetime.now() - timedelta(days=1)
    month_str = yesterday.strftime("%m")
    day_str = yesterday.strftime("%d")
    date_id = f"date{month_str}{day_str}"

    schedule_url = f"{NPB_BASE_URL}/games/{yesterday.year}/schedule_{month_str}_detail.html"
    soup = fetch_soup(schedule_url)
    if soup is None:
        logger.error("無法取得 schedule 頁面: %s", schedule_url)
        return []

    # 尋找對應日期的 <tr>
    game_rows = soup.find_all("tr", id=date_id)
    if not game_rows:
        logger.warning("schedule 頁面找不到 %s 的比賽", date_id)
        return []

    games = []
    for row in game_rows:
        try:
            # 解析對戰組合與比數
            team1_div = row.find("div", class_="team1")
            team2_div = row.find("div", class_="team2")
            score1_div = row.find("div", class_="score1")
            score2_div = row.find("div", class_="score2")
            state_div = row.find("div", class_="state")  # 分隔線（-）
            place_div = row.find("div", class_="place")
            time_div = row.find("div", class_="time")
            comm_div = row.find("div", class_="comment")
            # 投手資訊（schedule 明細可能有）
            pit_divs = row.find_all("div", class_="pit")

            # 連結
            a_tag = row.find("a")
            detail_url = None
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                if href.startswith("/"):
                    detail_url = f"{NPB_BASE_URL}{href}"
                else:
                    detail_url = href

            home_team_name = team1_div.get_text(strip=True) if team1_div else ""
            away_team_name = team2_div.get_text(strip=True) if team2_div else ""
            home_score = score1_div.get_text(strip=True) if score1_div else ""
            away_score = score2_div.get_text(strip=True) if score2_div else ""
            place = place_div.get_text(strip=True) if place_div else ""
            game_time = time_div.get_text(strip=True) if time_div else ""
            comment = comm_div.get_text(strip=True) if comm_div else ""

            home_team_key = resolve_team_name(home_team_name)
            away_team_key = resolve_team_name(away_team_name)

            game = {
                "home_team": TEAMS.get(home_team_key, {}).get("name", home_team_name),
                "away_team": TEAMS.get(away_team_key, {}).get("name", away_team_name),
                "home_team_key": home_team_key,
                "away_team_key": away_team_key,
                "home_score": home_score,
                "away_score": away_score,
                "stadium": place,
                "time": game_time,
                "status": comment,
                "detail_url": detail_url or "",
            }

            # 如果有投手資訊，嘗試解析
            if len(pit_divs) >= 2:
                # 格式通常為 "分：赤星" 或 "勝：西舘 敗：ロング" 等
                away_pitcher_text = pit_divs[0].get_text(strip=True)
                home_pitcher_text = pit_divs[1].get_text(strip=True)
                game["home_pitcher_info"] = home_pitcher_text
                game["away_pitcher_info"] = away_pitcher_text

                # 嘗試解析勝敗投
                game["winning_pitcher_info"] = home_pitcher_text
                game["losing_pitcher_info"] = away_pitcher_text

            games.append(game)
        except Exception as e:
            logger.warning("解析昨日比賽 row 時發生錯誤: %s", e)
            continue

    # 再從詳細頁面補充勝敗投資訊（如果有 detail_url）
    for game in games:
        detail_url = game.get("detail_url", "")
        if detail_url:
            pitcher_info = _fetch_pitcher_info(detail_url)
            if pitcher_info:
                game.update(pitcher_info)

    logger.info("昨日比賽: 取得 %d 場", len(games))
    return games


def fetch_tomorrow_games():
    """
    爬取明日賽程。
    schedule 明細頁也會顯示未來的比賽（無比分）。
    """
    date_info = get_date_info()
    tomorrow = datetime.now() + timedelta(days=1)
    month_str = tomorrow.strftime("%m")
    day_str = tomorrow.strftime("%d")
    date_id = f"date{month_str}{day_str}"

    schedule_url = f"{NPB_BASE_URL}/games/{tomorrow.year}/schedule_{month_str}_detail.html"
    soup = fetch_soup(schedule_url)
    if soup is None:
        logger.error("無法取得 schedule 頁面: %s", schedule_url)
        return []

    game_rows = soup.find_all("tr", id=date_id)
    if not game_rows:
        logger.warning("schedule 頁面找不到 %s 的比賽", date_id)
        return []

    games = []
    for row in game_rows:
        try:
            team1_div = row.find("div", class_="team1")
            team2_div = row.find("div", class_="team2")
            place_div = row.find("div", class_="place")
            time_div = row.find("div", class_="time")
            comm_div = row.find("div", class_="comment")

            home_team_name = team1_div.get_text(strip=True) if team1_div else ""
            away_team_name = team2_div.get_text(strip=True) if team2_div else ""
            place = place_div.get_text(strip=True) if place_div else ""
            game_time = time_div.get_text(strip=True) if time_div else ""
            note = comm_div.get_text(strip=True) if comm_div else ""

            home_team_key = resolve_team_name(home_team_name)
            away_team_key = resolve_team_name(away_team_name)

            # 檢查是否有先發投手
            pit_divs = row.find_all("div", class_="pit")
            away_pitcher = ""
            home_pitcher = ""
            if len(pit_divs) >= 2:
                away_pitcher = pit_divs[0].get_text(strip=True)
                home_pitcher = pit_divs[1].get_text(strip=True)

            game = {
                "home_team": TEAMS.get(home_team_key, {}).get("name", home_team_name),
                "away_team": TEAMS.get(away_team_key, {}).get("name", away_team_name),
                "home_team_key": home_team_key,
                "away_team_key": away_team_key,
                "stadium": place,
                "time": game_time,
                "note": note,
                "home_pitcher": home_pitcher,
                "away_pitcher": away_pitcher,
                "status": "scheduled",
            }
            games.append(game)
        except Exception as e:
            logger.warning("解析明日比賽 row 時發生錯誤: %s", e)
            continue

    logger.info("明日賽程: 取得 %d 場", len(games))
    return games


def fetch_npb_scores(date_str):
    """
    通用函式：根據日期字串（YYYY-MM-DD）爬取該日的比賽資料。
    先嘗試 header_score（僅限今日），後備用 schedule 頁面。
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    if date_str == today_str:
        return fetch_today_games()
    else:
        # 對於非今日日期，使用 schedule 頁面
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        month_str = dt.strftime("%m")
        day_str = dt.strftime("%d")
        date_id = f"date{month_str}{day_str}"

        schedule_url = f"{NPB_BASE_URL}/games/{dt.year}/schedule_{month_str}_detail.html"
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

                home_team_name = team1_div.get_text(strip=True) if team1_div else ""
                away_team_name = team2_div.get_text(strip=True) if team2_div else ""
                home_score = score1_div.get_text(strip=True) if score1_div else ""
                away_score = score2_div.get_text(strip=True) if score2_div else ""
                place = place_div.get_text(strip=True) if place_div else ""
                game_time = time_div.get_text(strip=True) if time_div else ""

                home_team_key = resolve_team_name(home_team_name)
                away_team_key = resolve_team_name(away_team_name)

                game = {
                    "home_team": TEAMS.get(home_team_key, {}).get("name", home_team_name),
                    "away_team": TEAMS.get(away_team_key, {}).get("name", away_team_name),
                    "home_team_key": home_team_key,
                    "away_team_key": away_team_key,
                    "home_score": home_score,
                    "away_score": away_score,
                    "stadium": place,
                    "time": game_time,
                }
                games.append(game)
            except Exception as e:
                logger.warning("解析 %s 比賽 row 時發生錯誤: %s", date_str, e)
                continue
        return games


# ============================================================
# 爬取詳細比賽頁面（勝敗投、全壘打等）
# ============================================================
def _fetch_pitcher_info(detail_url: str) -> dict | None:
    """
    從比賽詳細頁面爬取勝敗投資訊。
    URL 格式範例：https://npb.jp/scores/2026/0606/g-m-02/
    詳細頁面包含 game_result_info 區塊、line-score 等。
    """
    soup = fetch_soup(detail_url)
    if soup is None:
        return None

    result = {}

    try:
        # 解析 line-score 區域的比賽基本資訊
        game_info_p = soup.select_one("p.game_info")
        if game_info_p:
            info_text = game_info_p.get_text("\n", strip=True)
            # 提取：開始時間、結束時間、比賽時間、入場人數
            # 格式：◇開始 14:00 ◇終了 17:58 ◇試合時間 3時間58分 ◇入場者 42,324人
            start_time_m = re.search(r"開始\s*(\S+)", info_text)
            end_time_m = re.search(r"終了\s*(\S+)", info_text)
            duration_m = re.search(r"試合時間\s*(\S+)", info_text)
            attendance_m = re.search(r"入場者\s*([\d,]+)", info_text)
            if start_time_m:
                result["start_time"] = start_time_m.group(1)
            if end_time_m:
                result["end_time"] = end_time_m.group(1)
            if duration_m:
                result["duration"] = duration_m.group(1)
            if attendance_m:
                result["attendance"] = attendance_m.group(1).replace(",", "")

            # 比賽狀態：試合終了、試合中、中止等
            if "試合終了" in info_text:
                result["status"] = "試合終了"
            elif "試合中" in info_text:
                result["status"] = "試合中"
            elif "中止" in info_text:
                result["status"] = "中止"
            elif "開始" in info_text:
                result["status"] = "開始前"

        # 解析 game_result_info 區塊中的勝敗投手
        # NPB 的詳細頁面中有 <section class="game_result_info">
        # 包含 batter 資訊（投打對決），但不一定直接有勝敗投
        # 勝敗投資訊可能在 game_info 或 game_result 中
        # 某些頁面有「勝利投手」「敗戦投手」的段落
        result_section = soup.find("section", class_="game_result_info")
        if result_section:
            # 嘗試找到勝敗投資訊
            # 有時勝敗投會寫在 batter 表格前的文字中
            result_text = result_section.get_text("\n", strip=True)

            # 嘗試多種模式比對勝敗投
            # 模式1: "勝利投手[：]選手名" "敗戦投手[：]選手名"
            win_m = re.search(r"勝利投手[：:]\s*([^\n]+)", result_text)
            lose_m = re.search(r"敗戦投手[：:]\s*([^\n]+)", result_text)
            if win_m:
                result["winning_pitcher"] = win_m.group(1).strip()
            if lose_m:
                result["losing_pitcher"] = lose_m.group(1).strip()

        # 若勝敗投不在 game_result_info 中，試試其他標題
        if "winning_pitcher" not in result or "losing_pitcher" not in result:
            # 在頁面中搜尋「勝利投手」「敗戦投手」標題
            for heading in soup.find_all(["h4", "h5", "p", "div"]):
                text = heading.get_text(strip=True)
                if "勝利投手" in text:
                    # 下一個兄弟元素或父元素後的文字
                    win_text = re.sub(r"勝利投手[：:]\s*", "", text).strip()
                    if win_text:
                        result["winning_pitcher"] = win_text
                if "敗戦投手" in text:
                    lose_text = re.sub(r"敗戦投手[：:]\s*", "", text).strip()
                    if lose_text:
                        result["losing_pitcher"] = lose_text

        # 解析本壘打資訊
        if result_section:
            hr_headings = result_section.find_all("h4")
            for h4 in hr_headings:
                if "本塁打" in h4.get_text(strip=True):
                    hr_table = h4.find_next("table")
                    if hr_table:
                        home_runs = []
                        for tr in hr_table.find_all("tr"):
                            th = tr.find("th")
                            td = tr.find("td")
                            if th and td:
                                team = th.get_text(strip=True)
                                hr_text = td.get_text(strip=True)
                                if hr_text:
                                    home_runs.append({"team": team, "detail": hr_text})
                        result["home_runs"] = home_runs

        # 解析球場
        place_span = soup.find("span", class_="place")
        if place_span:
            result["stadium"] = place_span.get_text(strip=True)

    except Exception as e:
        logger.warning("解析詳細頁面 %s 時發生錯誤: %s", detail_url, e)

    return result


def parse_game_from_table(table):
    """
    從 game detail page 的某個 table 解析比賽資訊（通用方法）。
    因應 NPB 頁面結構，直接使用 _fetch_pitcher_info 更可靠。
    但保留此 function 以維持 API 相容。
    """
    # 此函式已在上面 fetch_yesterday_games 和 fetch_today_games 中內聯實作
    # 這裡保留為 wrapper
    logger.warning("parse_game_from_table 已被取代，建議使用 _fetch_pitcher_info")
    return None


# ============================================================
# 爬取個人排行榜
# ============================================================
def fetch_leaders():
    """
    從 NPB 官方網站爬取個人打擊/投手排行榜。
    - 打擊排行榜：https://npb.jp/bis/2026/stats/bat_c.html (中央) / bat_p.html (太平洋)
    - 投手排行榜：https://npb.jp/bis/2026/stats/pit_c.html (中央) / pit_p.html (太平洋)

    因排行榜種類繁多（打擊率、全壘打、打點、盜壘、ERA、勝投、三振等），
    我們爬取原始數據後整理出重點排行榜。
    """
    leaders = {
        "batting_avg_central": [],
        "batting_avg_pacific": [],
        "home_runs_central": [],
        "home_runs_pacific": [],
        "era_central": [],
        "era_pacific": [],
        "wins_central": [],
        "wins_pacific": [],
    }

    # 打擊排行榜 URL
    bat_urls = [
        ("central", f"{NPB_BASE_URL}/bis/2026/stats/bat_c.html"),
        ("pacific", f"{NPB_BASE_URL}/bis/2026/stats/bat_p.html"),
    ]

    for league, url in bat_urls:
        soup = fetch_soup(url)
        if soup is None:
            logger.warning("無法取得 %s 打擊排行榜", league)
            continue

        rows = soup.find_all("tr", class_="ststats")
        if not rows:
            logger.warning("%s 打擊排行榜無 ststats 資料", league)
            continue

        avg_key = f"batting_avg_{league}"
        hr_key = f"home_runs_{league}"

        # 打擊排行榜表格結構：
        # td[0]=排名, td[1]=選手名+所屬, td[2]=打擊率, ..., td[10]=全壘打, ...
        for row in rows[:10]:  # 取前 10 名
            cells = row.find_all("td")
            if len(cells) < 12:
                continue

            rank = cells[0].get_text(strip=True)
            # 選手名稱格式： "佐藤　輝明<span class=\"stteam\">(神)</span>"
            player_cell = cells[1]
            player_name = player_cell.contents[0].strip() if player_cell.contents else ""
            # 取得所屬球隊（從 stteam span）
            stteam = player_cell.find("span", class_="stteam")
            team_code = stteam.get_text(strip=True).strip("()") if stteam else ""

            # 將球隊代碼轉換為 TEAMS key
            # 代碼對應：神=tigers, 巨=giants, デ=baystars, 中=dragons, 広=carp, ヤ=swallows
            # 鷹=hawks, 日=fighters, 楽=eagles, 西=lions, オ=buffaloes, ロ=marines
            team_abbr_map = {
                "神": "tigers", "巨": "giants", "デ": "baystars",
                "中": "dragons", "広": "carp", "ヤ": "swallows",
                "鷹": "hawks", "日": "fighters", "楽": "eagles",
                "西": "lions", "オ": "buffaloes", "ロ": "marines",
                "ソ": "hawks", "ホ": "hawks",
                "ニ": "fighters", "ア": "fighters",
                "金": "eagles", "イ": "eagles",
                "バ": "buffaloes", "シ": "buffaloes",
                "マ": "marines", "ー": "marines",
            }
            team_key = team_abbr_map.get(team_code, team_code)
            team_name = TEAMS.get(team_key, {}).get("name", team_code)

            avg_val = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            hr_val = cells[10].get_text(strip=True) if len(cells) > 10 else ""

            entry = {
                "rank": int(rank) if rank.isdigit() else rank,
                "player": player_name,
                "team": team_name,
                "team_key": team_key,
                "value": "",
            }

            # 打擊率
            if avg_val:
                avg_entry = entry.copy()
                avg_entry["value"] = avg_val
                leaders[avg_key].append(avg_entry)

            # 全壘打
            if hr_val and hr_val != "0":
                hr_entry = entry.copy()
                hr_entry["value"] = hr_val
                leaders[hr_key].append(hr_entry)

        logger.info("%s 打擊排行榜: 打擊率 %d 筆, 全壘打 %d 筆",
                     "中央聯盟" if league == "central" else "太平洋聯盟",
                     len(leaders[avg_key]), len(leaders[hr_key]))

    # 投手排行榜
    pit_urls = [
        ("central", f"{NPB_BASE_URL}/bis/2026/stats/pit_c.html"),
        ("pacific", f"{NPB_BASE_URL}/bis/2026/stats/pit_p.html"),
    ]

    for league, url in pit_urls:
        soup = fetch_soup(url)
        if soup is None:
            logger.warning("無法取得 %s 投手排行榜", league)
            continue

        rows = soup.find_all("tr", class_="ststats")
        if not rows:
            logger.warning("%s 投手排行榜無 ststats 資料", league)
            continue

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

            team_abbr_map = {
                "神": "tigers", "巨": "giants", "デ": "baystars",
                "中": "dragons", "広": "carp", "ヤ": "swallows",
                "鷹": "hawks", "日": "fighters", "楽": "eagles",
                "西": "lions", "オ": "buffaloes", "ロ": "marines",
            }
            team_key = team_abbr_map.get(team_code, team_code)
            team_name = TEAMS.get(team_key, {}).get("name", team_code)

            # ERA 在第 3 欄 (index 2)
            era_val = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            # 勝投在第 5 欄 (index 4) 的 wins（但要看表格結構）
            # 實際結構：0=rank, 1=name, 2=ERA, 3=games, 4=wins, 5=losses, 6=saves, ...
            wins_val = cells[4].get_text(strip=True) if len(cells) > 4 else ""

            entry = {
                "rank": int(rank) if rank.isdigit() else rank,
                "player": player_name,
                "team": team_name,
                "team_key": team_key,
                "value": "",
            }

            if era_val:
                era_entry = entry.copy()
                era_entry["value"] = era_val
                leaders[era_key].append(era_entry)

            if wins_val and wins_val != "0":
                wins_entry = entry.copy()
                wins_entry["value"] = wins_val
                leaders[wins_key].append(wins_entry)

        logger.info("%s 投手排行榜: ERA %d 筆, 勝投 %d 筆",
                     "中央聯盟" if league == "central" else "太平洋聯盟",
                     len(leaders[era_key]), len(leaders[wins_key]))

    return leaders


# ============================================================
# 爬取交流戰戰績
# ============================================================
def fetch_interleague():
    """
    從 NPB 交流戰排名頁面爬取交流戰戰績。
    URL: https://npb.jp/bis/2026/stats/std_inter.html
    解析 <tr class="ststats"> 行，計算中央/太平洋聯盟的勝負。
    """
    url = f"{NPB_BASE_URL}/bis/2026/stats/std_inter.html"
    soup = fetch_soup(url)
    if soup is None:
        logger.warning("無法取得交流戰戰績頁面")
        return {"central_wins": 0, "pacific_wins": 0, "leader": "unknown", "standings": []}

    rows = soup.find_all("tr", class_="ststats")
    if not rows:
        logger.warning("交流戰頁面無 ststats 資料")
        return {"central_wins": 0, "pacific_wins": 0, "leader": "unknown", "standings": []}

    inter_standings = []
    central_league_teams = {"giants", "tigers", "carp", "baystars", "swallows", "dragons"}
    pacific_league_teams = {"hawks", "fighters", "eagles", "lions", "buffaloes", "marines"}
    central_wins = 0
    pacific_wins = 0

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 7:
            continue

        team_name_jp = cells[0].get_text(strip=True)
        team_key = resolve_team_name(team_name_jp)
        team_info = TEAMS.get(team_key, {"name": team_name_jp, "name_jp": team_name_jp})

        games = cells[1].get_text(strip=True)
        wins = cells[2].get_text(strip=True)
        losses = cells[3].get_text(strip=True)
        draws = cells[4].get_text(strip=True)
        pct = cells[5].get_text(strip=True)
        gb = cells[6].get_text(strip=True).replace("--", "-")

        entry = {
            "team": team_info["name"],
            "team_jp": team_info["name_jp"],
            "team_key": team_key,
            "games": games,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "pct": pct,
            "gb": gb,
        }
        inter_standings.append(entry)

        # 累計勝場
        if team_key in central_league_teams and wins.isdigit():
            central_wins += int(wins)
        elif team_key in pacific_league_teams and wins.isdigit():
            pacific_wins += int(wins)

    # 判定哪個聯盟領先
    if central_wins > pacific_wins:
        leader = "central"
    elif pacific_wins > central_wins:
        leader = "pacific"
    else:
        leader = "tie"

    logger.info(
        "交流戰戰績: 中央聯盟 %d 勝, 太平洋聯盟 %d 勝, 領先: %s",
        central_wins, pacific_wins, leader,
    )

    return {
        "central_wins": central_wins,
        "pacific_wins": pacific_wins,
        "leader": leader,
        "standings": inter_standings,
    }


# ============================================================
# 主程式
# ============================================================
def main():
    """主程式 - 收集所有數據並輸出 JSON"""
    logger.info("=== 數據收集開始 %s ===", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 取得日期資訊
    date_info = get_date_info()

    # 收集各項數據
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

    # 組裝最終數據
    data = {
        "date_info": date_info,
        "teams": TEAMS,
        "yesterday_games": yesterday_games,
        "today_games": today_games,
        "tomorrow_games": tomorrow_games,
        "standings": standings,
        "leaders": leaders,
        "interleague": interleague,
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 輸出 JSON
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
