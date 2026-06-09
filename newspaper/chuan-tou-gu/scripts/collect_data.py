#!/usr/bin/env python3
"""
川投顧日報 - 數據收集腳本
純爬蟲，不使用 LLM
資料來源：Yahoo Finance, RSS 新聞, 財報日曆
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# 設定目錄
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# 日誌設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# HTTP Session
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})


def get_date_info():
    """取得日期資訊"""
    now = datetime.now()
    
    # 如果是週末，使用上個交易日
    if now.weekday() == 5:  # 週六
        market_date = now - timedelta(days=1)
    elif now.weekday() == 6:  # 週日
        market_date = now - timedelta(days=2)
    else:
        market_date = now
    
    # 前一個交易日
    if market_date.weekday() == 0:  # 週一
        prev_date = market_date - timedelta(days=3)
    else:
        prev_date = market_date - timedelta(days=1)
    
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    
    return {
        "date_str": market_date.strftime("%Y-%m-%d"),
        "prev_date_str": prev_date.strftime("%Y-%m-%d"),
        "display": f"{market_date.year}年{market_date.month:02d}月{market_date.day:02d}日",
        "weekday": weekdays[market_date.weekday()],
        "prev_display": f"{prev_date.year}年{prev_date.month:02d}月{prev_date.day:02d}日"
    }


def fetch_yahoo_quote(symbol):
    """從 Yahoo Finance v8 API 取得報價"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {
            "interval": "1d",
            "range": "5d",
            "includeAdjustedClose": "true"
        }
        resp = session.get(url, params=params, timeout=15)
        data = resp.json()
        
        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        
        if not timestamps or not closes:
            return None
        
        # 取得最新和前一筆有效資料
        valid_data = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
        if len(valid_data) < 1:
            return None
        
        latest_close = valid_data[-1][1]
        # 使用前一個有效交易日作為 prev_close，不是 chartPreviousClose！
        # chartPreviousClose 是整個範圍前的收盤（5天前），用來算漲跌幅會是
        # 累積 5 天的變化，不是一天的日變化。
        prev_close = valid_data[-2][1] if len(valid_data) > 1 else meta.get("chartPreviousClose", latest_close)
        
        change = latest_close - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        return {
            "price": round(latest_close, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "prev_close": round(prev_close, 2)
        }
    except Exception as e:
        logger.warning(f"Yahoo Finance {symbol} 失敗: {e}")
        return None


def fetch_market_indices():
    """取得美股大盤指數"""
    logger.info("正在取得美股大盤指數...")
    
    indices = {
        "^GSPC": {"name": "S&P 500", "symbol": "SPX"},
        "^DJI": {"name": "道瓊工業", "symbol": "DJI"},
        "^IXIC": {"name": "納斯達克", "symbol": "IXIC"},
        "^VIX": {"name": "VIX 恐慌指數", "symbol": "VIX"},
        "^TNX": {"name": "10年期公債殖利率", "symbol": "TNX"},
        "^RUT": {"name": "羅素2000", "symbol": "RUT"}
    }
    
    results = []
    for symbol, info in indices.items():
        quote = fetch_yahoo_quote(symbol)
        if quote:
            results.append({
                "name": info["name"],
                "symbol": info["symbol"],
                **quote
            })
    
    logger.info(f"大盤指數: {len(results)} 個")
    return results


def fetch_hot_stocks():
    """取得熱門股票報價"""
    logger.info("正在取得熱門股票...")
    
    hot_symbols = [
        ("NVDA", "NVIDIA"),
        ("TSLA", "Tesla"),
        ("AAPL", "Apple"),
        ("MSFT", "Microsoft"),
        ("GOOGL", "Alphabet"),
        ("META", "Meta Platforms"),
        ("AMZN", "Amazon"),
        ("AMD", "AMD"),
        ("AVGO", "Broadcom"),
        ("MU", "Micron"),
        ("PLTR", "Palantir"),
        ("DJT", "Trump Media & Technology")
    ]
    
    stocks = []
    for symbol, name in hot_symbols:
        quote = fetch_yahoo_quote(symbol)
        if quote:
            stocks.append({
                "symbol": symbol,
                "name": name,
                **quote
            })
    
    # 按漲跌幅絕對值排序
    stocks.sort(key=lambda x: abs(x.get("change_pct", 0)), reverse=True)
    
    logger.info(f"熱門股票: {len(stocks)} 檔")
    return stocks


def fetch_sector_performance():
    """取得板塊表現"""
    logger.info("正在取得板塊表現...")
    
    sectors = {
        "XLK": "科技",
        "XLF": "金融",
        "XLE": "能源",
        "XLI": "工業",
        "XLV": "醫療保健",
        "XLP": "必需消費",
        "XLY": "非必需消費",
        "XLB": "原物料",
        "XLU": "公用事業",
        "XLRE": "房地產"
    }
    
    results = []
    for symbol, name in sectors.items():
        quote = fetch_yahoo_quote(symbol)
        if quote:
            results.append({
                "symbol": symbol,
                "name": name,
                **quote
            })
    
    # 按漲跌幅排序
    results.sort(key=lambda x: x["change_pct"], reverse=True)
    
    logger.info(f"板塊表現: {len(results)} 個")
    return results


def fetch_yahoo_rss_news():
    """從 Yahoo Finance RSS 取得新聞"""
    logger.info("正在取得 Yahoo Finance RSS 新聞...")
    
    try:
        url = "https://finance.yahoo.com/rss/topstories"
        resp = session.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, "xml")
        
        articles = []
        for item in soup.find_all("item"):
            title = item.find("title")
            link = item.find("link")
            pub_date = item.find("pubDate")
            source = item.find("source")
            
            if title and link:
                title_text = title.get_text(strip=True)
                # 過濾掉導航連結
                if title_text in ["Today's news", "Newsletters", "Financial News"]:
                    continue
                if len(title_text) < 15:
                    continue
                    
                articles.append({
                    "title": title_text,
                    "url": link.get_text(strip=True),
                    "source": source.get_text(strip=True) if source else "Yahoo Finance",
                    "published": pub_date.get_text(strip=True) if pub_date else "",
                    "has_description": False
                })
        
        logger.info(f"Yahoo Finance RSS 新聞: {len(articles)} 則")
        return articles
    except Exception as e:
        logger.warning(f"Yahoo Finance RSS 失敗: {e}")
        return []


def fetch_cnbc_news():
    """從 CNBC RSS 取得新聞"""
    logger.info("正在取得 CNBC 新聞...")
    
    try:
        url = "https://www.cnbc.com/id/100003114/device/rss/rss.html"
        resp = session.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, "xml")
        
        articles = []
        for item in soup.find_all("item"):
            title = item.find("title")
            link = item.find("link")
            desc = item.find("description")
            pub_date = item.find("pubDate")
            
            if title and link:
                articles.append({
                    "title": title.get_text(strip=True),
                    "url": link.get_text(strip=True),
                    "description": desc.get_text(strip=True) if desc else "",
                    "source": "CNBC",
                    "published": pub_date.get_text(strip=True) if pub_date else "",
                    "has_description": bool(desc and desc.get_text(strip=True))
                })
        
        logger.info(f"CNBC 新聞: {len(articles)} 則")
        return articles
    except Exception as e:
        logger.warning(f"CNBC 新聞失敗: {e}")
        return []


def fetch_marketwatch_news():
    """從 MarketWatch RSS 取得新聞"""
    logger.info("正在取得 MarketWatch 新聞...")
    
    try:
        url = "https://www.marketwatch.com/rss/topstories"
        resp = session.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, "xml")
        
        articles = []
        for item in soup.find_all("item"):
            title = item.find("title")
            link = item.find("link")
            desc = item.find("description")
            pub_date = item.find("pubDate")
            
            if title and link:
                articles.append({
                    "title": title.get_text(strip=True),
                    "url": link.get_text(strip=True),
                    "description": desc.get_text(strip=True) if desc else "",
                    "source": "MarketWatch",
                    "published": pub_date.get_text(strip=True) if pub_date else "",
                    "has_description": bool(desc and desc.get_text(strip=True))
                })
        
        logger.info(f"MarketWatch 新聞: {len(articles)} 則")
        return articles
    except Exception as e:
        logger.warning(f"MarketWatch 新聞失敗: {e}")
        return []


def fetch_wsj_news():
    """從 WSJ RSS 取得新聞"""
    logger.info("正在取得 WSJ 新聞...")
    
    try:
        url = "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
        resp = session.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, "xml")
        
        articles = []
        for item in soup.find_all("item"):
            title = item.find("title")
            link = item.find("link")
            desc = item.find("description")
            pub_date = item.find("pubDate")
            
            if title and link:
                articles.append({
                    "title": title.get_text(strip=True),
                    "url": link.get_text(strip=True),
                    "description": desc.get_text(strip=True) if desc else "",
                    "source": "WSJ",
                    "published": pub_date.get_text(strip=True) if pub_date else "",
                    "has_description": bool(desc and desc.get_text(strip=True))
                })
        
        logger.info(f"WSJ 新聞: {len(articles)} 則")
        return articles
    except Exception as e:
        logger.warning(f"WSJ 新聞失敗: {e}")
        return []


def fetch_ft_news():
    """從 Financial Times RSS 取得新聞"""
    logger.info("正在取得 FT 新聞...")
    
    try:
        url = "https://www.ft.com/?format=rss"
        resp = session.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, "xml")
        
        articles = []
        for item in soup.find_all("item"):
            title = item.find("title")
            link = item.find("link")
            desc = item.find("description")
            pub_date = item.find("pubDate")
            
            if title and link:
                articles.append({
                    "title": title.get_text(strip=True),
                    "url": link.get_text(strip=True),
                    "description": desc.get_text(strip=True) if desc else "",
                    "source": "Financial Times",
                    "published": pub_date.get_text(strip=True) if pub_date else "",
                    "has_description": bool(desc and desc.get_text(strip=True))
                })
        
        logger.info(f"FT 新聞: {len(articles)} 則")
        return articles
    except Exception as e:
        logger.warning(f"FT 新聞失敗: {e}")
        return []


def fetch_earnings():
    """取得今日財報日曆"""
    logger.info("正在取得財報日曆...")
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"https://finance.yahoo.com/calendar/earnings?day={today}"
        resp = session.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        earnings = []
        rows = soup.select("table tbody tr")
        
        for row in rows[:20]:
            cells = row.select("td")
            if len(cells) >= 6:
                symbol = cells[0].get_text(strip=True)
                name = cells[1].get_text(strip=True)
                event_name = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                call_time = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                eps_est = cells[4].get_text(strip=True) if len(cells) > 4 else "-"
                reported = cells[5].get_text(strip=True) if len(cells) > 5 else "-"
                surprise = cells[6].get_text(strip=True) if len(cells) > 6 else "-"
                
                # 只保留有 EPS 預估或已公布 EPS 的
                if eps_est != "-" or reported != "-":
                    earnings.append({
                        "symbol": symbol,
                        "name": name,
                        "event": event_name,
                        "call_time": call_time,
                        "eps_estimate": eps_est if eps_est != "-" else None,
                        "reported_eps": reported if reported != "-" else None,
                        "surprise_pct": surprise if surprise != "-" else None
                    })
        
        logger.info(f"財報: {len(earnings)} 檔")
        return earnings
    except Exception as e:
        logger.warning(f"財報取得失敗: {e}")
        return []


def fetch_futures():
    """取得美股期貨數據"""
    logger.info("正在取得美股期貨...")
    
    futures = {
        "ES=F": {"name": "S&P 500 期貨", "symbol": "ES"},
        "NQ=F": {"name": "納斯達克期貨", "symbol": "NQ"},
        "YM=F": {"name": "道瓊期貨", "symbol": "YM"}
    }
    
    results = []
    for symbol, info in futures.items():
        quote = fetch_yahoo_quote(symbol)
        if quote:
            results.append({
                "name": info["name"],
                "symbol": info["symbol"],
                **quote
            })
    
    logger.info(f"期貨: {len(results)} 個")
    return results


def main():
    date_info = get_date_info()
    logger.info(f"=== 川投顧日報數據收集: {date_info['date_str']} ===")
    
    data = {
        "date_info": date_info,
        "generated_at": datetime.now().isoformat(),
        "market_indices": fetch_market_indices(),
        "hot_stocks": fetch_hot_stocks(),
        "sector_performance": fetch_sector_performance(),
        "news": {
            "yahoo": fetch_yahoo_rss_news(),
            "cnbc": fetch_cnbc_news(),
            "marketwatch": fetch_marketwatch_news(),
            "wsj": fetch_wsj_news(),
            "ft": fetch_ft_news()
        },
        "earnings": fetch_earnings(),
        "futures": fetch_futures()
    }
    
    # 儲存 JSON
    output_path = DATA_DIR / f"{date_info['date_str']}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"數據已儲存: {output_path}")
    
    # 統計
    total_news = sum(len(v) for v in data["news"].values())
    logger.info(f"=== 完成 ===")
    logger.info(f"  大盤指數: {len(data['market_indices'])} 個")
    logger.info(f"  熱門股票: {len(data['hot_stocks'])} 檔")
    logger.info(f"  板塊表現: {len(data['sector_performance'])} 個")
    logger.info(f"  新聞合計: {total_news} 則")
    logger.info(f"  財報: {len(data['earnings'])} 檔")
    logger.info(f"  期貨: {len(data['futures'])} 個")
    
    return output_path


if __name__ == "__main__":
    main()
