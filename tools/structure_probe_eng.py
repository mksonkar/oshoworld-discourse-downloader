#!/usr/bin/env python3

import requests
import time

BASE = "https://oshoworld.com"
API_FILTER = BASE + "/api/server/audio/filter"
API_SEARCH = BASE + "/api/server/audio/search-series-home"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
}

DELAY = 0.3  # polite delay between requests


def post(url, payload):
    r = requests.post(url, json=payload, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_initial_english():
    """
    Initial English landing call.
    This returns:
      - seriesData (direct series)
      - masterData (master categories like Kabir, Buddha, etc.)
    """
    print("[>] POST /audio/filter (english)")
    data = post(API_FILTER, {"language": "english"})
    return data


def fetch_paginated_english():
    """
    Paginated English series list.
    This is the same API as Hindi, but language=english.
    """
    page = 1
    all_items = []
    total_expected = None

    while True:
        print(f"[>] POST /search-series-home page={page}")
        data = post(
            API_SEARCH,
            {
                "page": page,
                "sortBy": "name",
                "language": "english",
            },
        )

        if total_expected is None:
            total_expected = data["total"][0]["total"]
            print(f"[i] Total expected series: {total_expected}")

        items = data.get("items", [])
        all_items.extend(items)

        print(f"[+] Page {page}: {len(items)} items")

        if len(all_items) >= total_expected:
            break

        page += 1
        time.sleep(DELAY)

    return all_items


def main():
    print("[*] Probing Osho English audio structure\n")

    # Step 1: initial landing data
    landing = fetch_initial_english()

    series_data = landing.get("seriesData", [])
    master_data = landing.get("masterData", [])

    print("\n=== DIRECT SERIES (from /audio/filter) ===")
    for i, s in enumerate(series_data, 1):
        print(f"[S{i:03}] {s['title']} ({s.get('count', '?')})")

    print("\n=== MASTER CATEGORIES ===")
    for i, m in enumerate(master_data, 1):
        print(f"[M{i:03}] {m['title']} (sub-series: {m.get('countSeries', '?')})")

    # Step 2: full paginated list
    print("\n=== PAGINATED SERIES LIST ===")
    all_series = fetch_paginated_english()

    print(f"\n[✓] Total series fetched: {len(all_series)}\n")

    for i, s in enumerate(all_series, 1):
        title = s.get("title", "<?>")
        count = s.get("count", "?")
        print(f"[{i:03}] {title} ({count})")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
