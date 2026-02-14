#!/usr/bin/env python3
# structure_cache_english.py
# Builds structure_english.json for English Osho audios

import requests
import re
import json
import math
import time
from pathlib import Path

BASE = "https://oshoworld.com"
API_SERIES = f"{BASE}/api/server/audio/search-series-home"
API_EPISODES = f"{BASE}/api/server/audio/series-filter"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

OUT_FILE = Path("structure_english.json")


# -----------------------------
# helpers
# -----------------------------
def get_build_id():
    """
    Fetch BUILD_ID from /audio-english page
    """
    url = f"{BASE}/audio-english"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    # look for /_next/static/<BUILD_ID>/_buildManifest.js
    m = re.search(r"/_next/static/([^/]+)/_buildManifest\.js", r.text)
    if not m:
        raise RuntimeError("BUILD_ID not found in audio-english page")

    return m.group(1)


def post(url, payload, retries=3, delay=2):
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(
                url,
                json=payload,
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries:
                raise
            print(f"    [!] Network error, retrying ({attempt}/{retries})...")
            time.sleep(delay * attempt)


def get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


# -----------------------------
# core logic
# -----------------------------
def fetch_all_series():
    print("[*] Fetching English series list...")

    page = 1
    all_items = []

    first = post(API_SERIES, {"page": 1, "sortBy": "name", "language": "english"})
    total = first["total"][0]["total"]
    per_page = len(first["items"])
    pages = math.ceil(total / per_page)

    all_items.extend(first["items"])

    for p in range(2, pages + 1):
        print(f"[>] POST search-series-home page={p}")
        data = post(API_SERIES, {"page": p, "sortBy": "name", "language": "english"})
        all_items.extend(data["items"])
        time.sleep(0.2)

    print(f"[✓] Total series fetched: {len(all_items)}")

    return all_items


def resolve_series_id(build_id, slug):
    """
    Resolve series_id by hitting Next.js data endpoint
    """
    url = f"{BASE}/_next/data/{build_id}/{slug}.json"
    data = get_json(url)

    try:
        return data["pageProps"]["data"]["pageData"]["categoryData"]["_id"]
    except KeyError:
        return None


def fetch_all_episodes(series_id):
    """
    Fetch all episodes for a series using series-filter
    """
    episodes = []

    page = 1
    per_page = 10

    first = post(
        API_EPISODES,
        {"currentId": series_id, "page": 1, "perPage": per_page, "search": ""},
    )

    total = first.get("total", 0)
    episodes.extend(first["listData"])

    pages = math.ceil(total / per_page)

    for p in range(2, pages + 1):
        data = post(
            API_EPISODES,
            {"currentId": series_id, "page": p, "perPage": per_page, "search": ""},
        )
        episodes.extend(data["listData"])
        time.sleep(0.2)

    return episodes


def build_structure():
    build_id = get_build_id()
    print(f"[✓] BUILD_ID: {build_id}")

    series_list = fetch_all_series()

    structure = {
        "language": "english",
        "series": [],
    }

    for idx, s in enumerate(series_list, 1):
        title = s["title"]
        slug = s["slug"]
        count = s.get("count")

        print(f"\n=== [{idx}] SERIES: {title} ===")

        series_id = resolve_series_id(build_id, slug)
        if not series_id:
            print("  [!] Failed to resolve series_id, skipping")
            continue

        episodes_raw = fetch_all_episodes(series_id)

        episodes = []
        for ep in episodes_raw:
            episodes.append(
                {
                    "title": ep.get("title"),
                    "slug": ep.get("slug"),
                    "duration": ep.get("duration"),
                    "file": ep.get("file"),
                    "description": ep.get("description"),
                }
            )

        print(f"    [+] Episodes: {len(episodes)}")

        structure["series"].append(
            {
                "title": title,
                "slug": slug,
                "count": count,
                "series_id": series_id,
                "episodes": episodes,
            }
        )

    return structure


def main():
    print("[*] Building English audio cache")
    start = time.time()
    structure = build_structure()

    OUT_FILE.write_text(json.dumps(structure, indent=2, ensure_ascii=False))
    elapsed = time.time() - start
    print(f"\n[✓] English cache written: {OUT_FILE}")
    print(f"[✓] Total series cached: {len(structure['series'])}")
    print(f"[✓] Time taken: {elapsed:.1f}s")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Exiting cleanly.")
        sys.exit(0)
