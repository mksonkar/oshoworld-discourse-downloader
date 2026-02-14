import requests
import json
import math

BASE = "https://oshoworld.com"

HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

PER_PAGE = 10


# -------------------------------
# API helpers
# -------------------------------


def post_json(path, payload):
    url = BASE + path
    r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def get_build_id():
    html = requests.get(BASE, timeout=30).text
    marker = '"buildId":"'
    i = html.find(marker)
    if i == -1:
        raise RuntimeError("buildId not found")
    return html[i + len(marker) :].split('"', 1)[0]


def get_series_page(build_id, slug):
    url = f"{BASE}/_next/data/{build_id}/{slug}.json"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


# -------------------------------
# Fetch all top-level series
# -------------------------------


def fetch_all_series():
    all_items = []
    page = 1

    while True:
        print(f"[>] POST search-series-home page={page}")
        data = post_json(
            "/api/server/audio/search-series-home",
            {"page": page, "sortBy": "name", "language": "hindi"},
        )

        items = data.get("items", [])
        if not items:
            break

        all_items.extend(items)

        total = data["total"][0]["total"]
        if len(all_items) >= total:
            break

        page += 1

    print(f"[✓] Series fetched: {len(all_items)}")
    return all_items


# -------------------------------
# Fetch sub-series (Geeta Darshan)
# -------------------------------


def fetch_subseries(series_id):
    subseries = []
    page = 1

    while True:
        data = post_json(
            "/api/server/audio/subseries-filter",
            {
                "currentId": series_id,
                "perPage": 16,
                "sortBy": "index-dsc",
                "page": page,
            },
        )

        items = data.get("listData", [])
        if not items:
            break

        subseries.extend(items)

        total = data["total"][0]["total"]
        if len(subseries) >= total:
            break

        page += 1

    return subseries


# -------------------------------
# Fetch episodes (pagination)
# -------------------------------


def fetch_episodes(series_id, first_page_data):
    episodes = []
    episodes.extend(first_page_data["listData"])

    total = first_page_data["total"]
    if total <= len(episodes):
        return episodes

    total_pages = math.ceil(total / PER_PAGE)

    for page in range(2, total_pages + 1):
        data = post_json(
            "/api/server/audio/series-filter",
            {"perPage": PER_PAGE, "page": page, "currentId": series_id, "search": ""},
        )
        episodes.extend(data.get("listData", []))

    return episodes


# -------------------------------
# Inspect one series
# -------------------------------


def inspect_series(build_id, series):
    title = series["title"]
    slug = series["slug"]

    print(f"\n=== SERIES ===")
    print(f"Title : {title}")
    print(f"Slug  : {slug}")

    page = get_series_page(build_id, slug)
    page_data = page["pageProps"]["data"]["pageData"]

    # Container series (Geeta Darshan)
    if "countSeries" in series:
        series_id = page_data["categoryData"]["_id"]
        subseries = fetch_subseries(series_id)

        print(f"  [Container] {len(subseries)} sub-series")

        for ss in subseries:
            print(f"  └─ SubSeries: {ss['title']} ({ss['count']})")

            ss_page = get_series_page(build_id, ss["slug"])
            ss_data = ss_page["pageProps"]["data"]["pageData"]

            ss_id = ss_data["categoryData"]["_id"]
            episodes = fetch_episodes(ss_id, ss_data)

            for ep in episodes:
                print(f"       └─ Ep {ep['audio_index']:>3}: {ep['title']}")

    # Normal series
    else:
        series_id = page_data["categoryData"]["_id"]
        episodes = fetch_episodes(series_id, page_data)

        print(f"  Episodes: {len(episodes)}")

        for ep in episodes:
            print(f"  └─ Ep {ep['audio_index']:>3}: {ep['title']}")


# -------------------------------
# Main
# -------------------------------


def main():
    print("[*] Probing Osho Hindi audio structure")

    build_id = get_build_id()
    series_list = fetch_all_series()

    for s in series_list:
        inspect_series(build_id, s)


if __name__ == "__main__":
    main()
