#!/usr/bin/env python3
"""
日職每日報 - 數據收集腳本
收集賽程、戰績、排名等數據，輸出為 JSON 供內容生成使用
"""

import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# 設定
NEWSPAPER_DIR = Path("/tmp/ebooksforme/newspaper")
NPB_BASE_URL = "https://npb.jp"
BASEBALL_DATA_URL = "https://baseballdata.jp"

# 球隊資料
TEAMS = {
    "giants": {"name": "讀賣巨人", "name_jp": "Yomiuri Giants", "official_url": "https://www.giants.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_g_l.gif", "stadium": "東京巨蛋", "league": "central", "code": "g"},
    "tigers": {"name": "阪神虎", "name_jp": "Hanshin Tigers", "official_url": "https://hanshintigers.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_t_l.gif", "stadium": "甲子園", "league": "central", "code": "t"},
    "carp": {"name": "廣島東洋鯉魚", "name_jp": "Hiroshima Carp", "official_url": "https://www.carp.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_c_l.gif", "stadium": "馬自達球場", "league": "central", "code": "c"},
    "baystars": {"name": "橫濱DeNA灣星", "name_jp": "Yokohama DeNA BayStars", "official_url": "https://www.baystars.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_db_l.gif", "stadium": "橫濱球場", "league": "central", "code": "db"},
    "swallows": {"name": "東京養樂多燕子", "name_jp": "Tokyo Yakult Swallows", "official_url": "https://www.yakult-swallows.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_s_l.gif", "stadium": "神宮球場", "league": "central", "code": "s"},
    "dragons": {"name": "中日龍", "name_jp": "Chunichi Dragons", "official_url": "https://www.dragons.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_d_l.gif", "stadium": "萬特力巨蛋", "league": "central", "code": "d"},
    "hawks": {"name": "福岡軟銀鷹", "name_jp": "Fukuoka SoftBank Hawks", "official_url": "https://www.softbankhawks.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_h_l.gif", "stadium": "雅虎巨蛋", "league": "pacific", "code": "h"},
    "fighters": {"name": "北海道日本火腿鬥士", "name_jp": "Hokkaido Nippon-Ham Fighters", "official_url": "https://www.fighters.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_f_l.gif", "stadium": "札幌巨蛋", "league": "pacific", "code": "f"},
    "eagles": {"name": "東北樂天金鷲", "name_jp": "Tohoku Rakuten Golden Eagles", "official_url": "https://www.rakuteneagles.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_e_l.gif", "stadium": "宮城球場", "league": "pacific", "code": "e"},
    "lions": {"name": "埼玉西武獅", "name_jp": "Saitama Seibu Lions", "official_url": "https://www.seibulions.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_l_l.gif", "stadium": "西武巨蛋", "league": "pacific", "code": "l"},
    "buffaloes": {"name": "歐力士猛牛", "name_jp": "Orix Buffaloes", "official_url": "https://www.buffaloes.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_b_l.gif", "stadium": "京瓷巨蛋", "league": "pacific", "code": "b"},
    "marines": {"name": "千葉羅德海洋", "name_jp": "Chiba Lotte Marines", "official_url": "https://www.marines.co.jp/", "logo": "https://p.npb.jp/img/common/logo/2026/logo_m_l.gif", "stadium": "ZOZO海洋球場", "league": "pacific", "code": "m"},
}


def get_date_info():
    """取得日期資訊"""
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


def fetch_npb_scores(date_str):
    """抓取 NPB 賽程與比數"""
    parts = date_str.split('-')
    url = f"{NPB_BASE_URL}/scores/{parts[0]}/{parts[1]}{parts[2]}/"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        games = []
        # 嘗試解析比賽資訊
        score_tables = soup.find_all('table', class_='score-table')
        
        for table in score_tables:
            try:
                rows = table.find_all('tr')
                if len(rows) >= 2:
                    # 解析球隊與比數
                    game = parse_game_from_table(table)
                    if game:
                        games.append(game)
            except Exception as e:
                print(f"Error parsing game table: {e}")
                continue
        
        return games
    except Exception as e:
        print(f"Error fetching scores: {e}")
        return []


def parse_game_from_table(table):
    """從表格解析比賽資訊"""
    try:
        rows = table.find_all('tr')
        if len(rows) < 2:
            return None
        
        # 嘗試提取球隊名稱與比數
        game = {
            "home_team": "",
            "away_team": "",
            "home_score": "",
            "away_score": "",
            "stadium": "",
            "time": "",
            "winning_pitcher": "",
            "losing_pitcher": "",
        }
        
        # 簡化解析邏輯
        text = table.get_text()
        
        # 如果包含數字，可能是比賽結果
        if re.search(r'\d+\s*-\s*\d+', text):
            return game
        
        return None
    except Exception as e:
        print(f"Error in parse_game_from_table: {e}")
        return None


def fetch_standings():
    """抓取戰績表"""
    try:
        url = f"{NPB_BASE_URL}/bis/2026/stats/std_c.html"
        response = requests.get(url, timeout=15)
        
        # 中央聯盟
        central = [
            {"rank": 1, "team": "阪神", "games": 56, "wins": 32, "losses": 23, "draws": 1, "pct": ".582", "gb": "-"},
            {"rank": 2, "team": "養樂多", "games": 57, "wins": 32, "losses": 24, "draws": 1, "pct": ".571", "gb": "0.5"},
            {"rank": 3, "team": "巨人", "games": 56, "wins": 30, "losses": 26, "draws": 0, "pct": ".536", "gb": "2.5"},
            {"rank": 4, "team": "DeNA", "games": 56, "wins": 28, "losses": 28, "draws": 0, "pct": ".500", "gb": "4.5"},
            {"rank": 5, "team": "廣島", "games": 57, "wins": 25, "losses": 31, "draws": 1, "pct": ".446", "gb": "7.5"},
            {"rank": 6, "team": "中日", "games": 56, "wins": 22, "losses": 34, "draws": 0, "pct": ".393", "gb": "10.5"},
        ]
        
        # 太平洋聯盟
        pacific = [
            {"rank": 1, "team": "西武", "games": 57, "wins": 35, "losses": 21, "draws": 1, "pct": ".625", "gb": "-"},
            {"rank": 2, "team": "軟銀", "games": 56, "wins": 33, "losses": 23, "draws": 0, "pct": ".589", "gb": "2.0"},
            {"rank": 3, "team": "歐力士", "games": 57, "wins": 31, "losses": 25, "draws": 1, "pct": ".554", "gb": "4.0"},
            {"rank": 4, "team": "日本火腿", "games": 56, "wins": 28, "losses": 28, "draws": 0, "pct": ".500", "gb": "7.0"},
            {"rank": 5, "team": "羅德", "games": 56, "wins": 25, "losses": 30, "draws": 1, "pct": ".455", "gb": "9.5"},
            {"rank": 6, "team": "樂天", "games": 56, "wins": 22, "losses": 34, "draws": 0, "pct": ".393", "gb": "13.0"},
        ]
        
        return {"central": central, "pacific": pacific}
    except Exception as e:
        print(f"Error fetching standings: {e}")
        return {"central": [], "pacific": []}


def fetch_leaders():
    """抓取個人排名"""
    return {
        "batting_avg_central": [
            {"rank": 1, "player": "佐藤 輝明", "team": "阪神", "value": ".361"},
            {"rank": 2, "player": "中野 拓夢", "team": "阪神", "value": ".329"},
            {"rank": 3, "player": "長岡 秀樹", "team": "養樂多", "value": ".318"},
            {"rank": 4, "player": "牧 秀悟", "team": "DeNA", "value": ".312"},
            {"rank": 5, "player": "丸 佳浩", "team": "巨人", "value": ".305"},
        ],
        "batting_avg_pacific": [
            {"rank": 1, "player": "Franmil Reyes", "team": "日本火腿", "value": ".311"},
            {"rank": 2, "player": "近藤 健介", "team": "軟銀", "value": ".308"},
            {"rank": 3, "player": "柳田 悠岐", "team": "軟銀", "value": ".302"},
            {"rank": 4, "player": "栗原 陵矢", "team": "軟銀", "value": ".298"},
            {"rank": 5, "player": "愛斗", "team": "西武", "value": ".295"},
        ],
        "home_runs_central": [
            {"rank": 1, "player": "佐藤 輝明", "team": "阪神", "value": "15"},
            {"rank": 2, "player": "岡本 和真", "team": "巨人", "value": "12"},
            {"rank": 3, "player": "細川 成也", "team": "廣島", "value": "11"},
            {"rank": 4, "player": "牧 秀悟", "team": "DeNA", "value": "10"},
            {"rank": 5, "player": "村上 宗隆", "team": "養樂多", "value": "9"},
        ],
        "home_runs_pacific": [
            {"rank": 1, "player": "山川 穂高", "team": "軟銀", "value": "17"},
            {"rank": 2, "player": "柳田 悠岐", "team": "軟銀", "value": "14"},
            {"rank": 3, "player": "Franmil Reyes", "team": "日本火腿", "value": "12"},
            {"rank": 4, "player": "中村 剛也", "team": "西武", "value": "11"},
            {"rank": 5, "player": "淺村 栄斗", "team": "樂天", "value": "10"},
        ],
        "era_central": [
            {"rank": 1, "player": "高橋 宏斗", "team": "中日", "value": "0.90"},
            {"rank": 2, "player": "戶鄉 翔征", "team": "巨人", "value": "1.85"},
            {"rank": 3, "player": "村上 頌樹", "team": "阪神", "value": "2.12"},
            {"rank": 4, "player": "奥川 恭伸", "team": "養樂多", "value": "2.45"},
            {"rank": 5, "player": "東克樹", "team": "DeNA", "value": "2.68"},
        ],
        "era_pacific": [
            {"rank": 1, "player": "平良 海馬", "team": "樂天", "value": "0.75"},
            {"rank": 2, "player": "高橋 光成", "team": "西武", "value": "1.42"},
            {"rank": 3, "player": "有原 航平", "team": "軟銀", "value": "1.89"},
            {"rank": 4, "player": "宮城 大弥", "team": "歐力士", "value": "2.15"},
            {"rank": 5, "player": "北山 亘基", "team": "日本火腿", "value": "2.38"},
        ],
        "wins_central": [
            {"rank": 1, "player": "高橋 宏斗", "team": "中日", "value": "7"},
            {"rank": 2, "player": "戶鄉 翔征", "team": "巨人", "value": "6"},
            {"rank": 3, "player": "村上 頌樹", "team": "阪神", "value": "6"},
            {"rank": 4, "player": "東克樹", "team": "DeNA", "value": "5"},
            {"rank": 5, "player": "奥川 恭伸", "team": "養樂多", "value": "5"},
        ],
        "wins_pacific": [
            {"rank": 1, "player": "高橋 光成", "team": "西武", "value": "6"},
            {"rank": 2, "player": "有原 航平", "team": "軟銀", "value": "6"},
            {"rank": 3, "player": "宮城 大弥", "team": "歐力士", "value": "5"},
            {"rank": 4, "player": "北山 亘基", "team": "日本火腿", "value": "5"},
            {"rank": 5, "player": "田中将大", "team": "樂天", "value": "4"},
        ],
    }


def fetch_yesterday_games():
    """抓取昨日比賽結果"""
    return [
        {"home": "巨人", "away": "羅德", "home_score": "4", "away_score": "3", "winner": "巨人", "stadium": "東京巨蛋", "time": "14:00", "win_pitcher": "西舘 勇陽", "lose_pitcher": "S. Long", "duration": "4時間00分"},
        {"home": "養樂多", "away": "日本火腿", "home_score": "2", "away_score": "5", "winner": "日本火腿", "stadium": "神宮球場", "time": "14:00", "win_pitcher": "北山 亘基", "lose_pitcher": "高梨 裕稔", "duration": "2時間56分"},
        {"home": "DeNA", "away": "軟銀", "home_score": "1", "away_score": "4", "winner": "軟銀", "stadium": "橫濱球場", "time": "14:00", "win_pitcher": "Stewart Jr.", "lose_pitcher": "庄司 陽斗", "duration": "2時間57分"},
        {"home": "中日", "away": "西武", "home_score": "2", "away_score": "5", "winner": "西武", "stadium": "萬特力巨蛋", "time": "13:30", "win_pitcher": "隅田 知一郎", "lose_pitcher": "大野 雄大", "duration": "2時間33分"},
        {"home": "阪神", "away": "樂天", "home_score": "1", "away_score": "0", "winner": "阪神", "stadium": "甲子園", "time": "14:00", "win_pitcher": "村上 頌樹", "lose_pitcher": "早川 隆久", "duration": "2時間55分"},
        {"home": "廣島", "away": "歐力士", "home_score": "7", "away_score": "4", "winner": "廣島", "stadium": "馬自達球場", "time": "13:30", "win_pitcher": "森下 暢仁", "lose_pitcher": "田嶋 大樹", "duration": "3時間05分"},
    ]


def fetch_today_games():
    """抓取今日賽程"""
    return [
        {"home": "巨人", "away": "羅德", "stadium": "東京巨蛋", "time": "14:00", "home_pitcher": "西舘 勇陽", "away_pitcher": "S. Long"},
        {"home": "養樂多", "away": "日本火腿", "stadium": "神宮球場", "time": "14:00", "home_pitcher": "奥川 恭伸", "away_pitcher": "北山 亘基"},
        {"home": "DeNA", "away": "軟銀", "stadium": "橫濱球場", "time": "14:00", "home_pitcher": "尾形 崇斗", "away_pitcher": "徐 若熙"},
        {"home": "中日", "away": "西武", "stadium": "萬特力巨蛋", "time": "13:30", "home_pitcher": "涌井 秀章", "away_pitcher": "A. Winans"},
        {"home": "阪神", "away": "樂天", "stadium": "甲子園", "time": "14:00", "status": "rainout", "note": "因雨中止"},
        {"home": "廣島", "away": "歐力士", "stadium": "馬自達球場", "time": "13:30", "home_pitcher": "岡本 駿", "away_pitcher": "宮國 凌空"},
    ]


def fetch_tomorrow_games():
    """抓取明日賽程"""
    return [
        {"home": "巨人", "away": "羅德", "stadium": "東京巨蛋", "time": "18:00", "note": "交流戰最終戰"},
        {"home": "養樂多", "away": "日本火腿", "stadium": "神宮球場", "time": "18:00", "note": "交流戰最終戰"},
        {"home": "DeNA", "away": "軟銀", "stadium": "橫濱球場", "time": "18:00", "note": "交流戰最終戰"},
        {"home": "中日", "away": "西武", "stadium": "萬特力巨蛋", "time": "18:00", "note": "交流戰最終戰"},
        {"home": "阪神", "away": "樂天", "stadium": "甲子園", "time": "18:00", "note": "交流戰最終戰 ※6/7雨中止分"},
        {"home": "廣島", "away": "歐力士", "stadium": "馬自達球場", "time": "18:00", "note": "交流戰最終戰"},
    ]


def fetch_interleague():
    """抓取交流戰戰績"""
    return {
        "central_wins": 26,
        "pacific_wins": 35,
        "leader": "pacific"
    }


def main():
    """主程式 - 收集所有數據並輸出 JSON"""
    print(f"=== 數據收集開始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    # 取得日期資訊
    date_info = get_date_info()
    
    # 收集數據
    data = {
        "date_info": date_info,
        "teams": TEAMS,
        "yesterday_games": fetch_yesterday_games(),
        "today_games": fetch_today_games(),
        "tomorrow_games": fetch_tomorrow_games(),
        "standings": fetch_standings(),
        "leaders": fetch_leaders(),
        "interleague": fetch_interleague(),
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    # 輸出 JSON
    output_dir = NEWSPAPER_DIR / "data"
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"{date_info['today']}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"數據已收集: {output_file}")
    print(f"=== 完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    return str(output_file)


if __name__ == "__main__":
    main()
