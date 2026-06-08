#!/usr/bin/env python3
"""
音樂連結搜尋工具 v1.0
根據歌曲名稱 + 藝人名稱，搜尋 Spotify 和 YouTube 的真實連結

用法:
    python3 music_link_finder.py "歌曲名" "藝人名"
    python3 music_link_finder.py --json '{"songs": [{"title": "...", "artist": "..."}]}'
    python3 music_link_finder.py --file songs.json

輸出格式:
    {
        "song": "歌曲名",
        "artist": "藝人名",
        "spotify_url": "https://open.spotify.com/track/...",
        "youtube_url": "https://www.youtube.com/watch?v=...",
        "spotify_found": true,
        "youtube_found": true
    }
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
from typing import Optional

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}


def search_spotify(title: str, artist: str) -> Optional[str]:
    """
    搜尋 Spotify track 連結。
    由於 Spotify 搜尋結果頁面是動態載入（React 應用），
    無法直接從 HTML 解析真實 track URL，因此回傳搜尋頁面連結。
    使用者點擊後可在 Spotify 頁面看到搜尋結果。
    """
    return f"https://open.spotify.com/search/{urllib.parse.quote(f'{title} {artist}')}"


def search_youtube(title: str, artist: str) -> Optional[str]:
    """
    搜尋 YouTube 音樂影片連結。
    使用 YouTube 搜尋結果頁面解析 videoId。
    """
    queries = [
        f"{title} {artist} official music video",
        f"{title} {artist}",
    ]

    try:
        for query in queries:
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)
                if video_ids:
                    return f"https://www.youtube.com/watch?v={video_ids[0]}"
    except Exception as e:
        print(f"  [YouTube 搜尋失敗] {e}", file=sys.stderr)

    # 備用：回傳搜尋頁面
    return f"https://www.youtube.com/results?search_query={urllib.parse.quote(f'{title} {artist}')}"


def find_song_links(title: str, artist: str, delay: float = 1.0) -> dict:
    """
    搜尋單首歌曲的 Spotify + YouTube 連結。

    Args:
        title: 歌曲名稱
        artist: 藝人名稱
        delay: 每次搜尋間隔秒數（避免被封）

    Returns:
        {
            "song": str,
            "artist": str,
            "spotify_url": str | None,
            "youtube_url": str | None,
            "spotify_found": bool,
            "youtube_found": bool,
        }
    """
    print(f"  搜尋: {title} - {artist}")

    spotify_url = search_spotify(title, artist)
    time.sleep(delay)
    youtube_url = search_youtube(title, artist)
    time.sleep(delay)

    # 判斷是否為真實 track URL（還是只是搜尋頁 fallback）
    spotify_found = spotify_url and "/track/" in spotify_url
    youtube_found = youtube_url and "/watch?v=" in youtube_url

    result = {
        "song": title,
        "artist": artist,
        "spotify_url": spotify_url,
        "youtube_url": youtube_url,
        "spotify_found": spotify_found,
        "youtube_found": youtube_found,
    }

    status = []
    if spotify_found:
        status.append("Spotify ✅")
    else:
        status.append("Spotify ⚠️")
    if youtube_found:
        status.append("YouTube ✅")
    else:
        status.append("YouTube ⚠️")
    print(f"    {' | '.join(status)}")

    return result


def find_multiple_songs(songs: list[dict], delay: float = 1.0) -> list[dict]:
    """
    批次搜尋多首歌曲的連結。

    Args:
        songs: [{"title": "...", "artist": "..."}, ...]
        delay: 每次搜尋間隔秒數

    Returns:
        [result_dict, ...]
    """
    results = []
    total = len(songs)
    for i, song in enumerate(songs, 1):
        print(f"[{i}/{total}] ", end="")
        result = find_song_links(song["title"], song["artist"], delay=delay)
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description="搜尋歌曲的 Spotify + YouTube 連結")
    parser.add_argument("title", nargs="?", help="歌曲名稱")
    parser.add_argument("artist", nargs="?", help="藝人名稱")
    parser.add_argument("--json", help="JSON 字串，格式: '{\"songs\": [{\"title\": \"...\", \"artist\": \"...\"}]}'")
    parser.add_argument("--file", help="JSON 檔案路徑")
    parser.add_argument("--delay", type=float, default=1.0, help="每次搜尋間隔秒數（預設 1.0）")
    parser.add_argument("--output", "-o", help="輸出 JSON 檔案路徑")
    args = parser.parse_args()

    songs = []

    if args.json:
        data = json.loads(args.json)
        songs = data.get("songs", [])
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
            songs = data.get("songs", [])
    elif args.title and args.artist:
        songs = [{"title": args.title, "artist": args.artist}]
    else:
        parser.print_help()
        sys.exit(1)

    if not songs:
        print("沒有提供歌曲資料", file=sys.stderr)
        sys.exit(1)

    print(f"=== 開始搜尋 {len(songs)} 首歌曲 ===")
    results = find_multiple_songs(songs, delay=args.delay)

    output = {"results": results, "total": len(results)}
    output_json = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"\n結果已儲存: {args.output}")
    else:
        print("\n=== 搜尋結果 ===")
        print(output_json)


if __name__ == "__main__":
    main()
