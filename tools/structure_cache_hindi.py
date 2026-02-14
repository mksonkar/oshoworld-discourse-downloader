import requests, json, math

BASE = "https://oshoworld.com"
HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
PER_PAGE = 10
OUT_FILE = "structure_hindi.json"


def log(msg):
    print(msg, flush=True)


def post(path, payload, retries=3, delay=2):
    url = BASE + path
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(
                url,
                headers=HEADERS,
                json=payload,
                timeout=30,
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries:
                raise
            print(f"    [!] Network error, retrying ({attempt}/{retries})...")
            time.sleep(delay * attempt)


def get_build_id():
    log("[*] Resolving Next.js BUILD_ID …")
    html = requests.get(BASE, timeout=30).text
    build_id = html.split('"buildId":"')[1].split('"', 1)[0]
    log(f"[✓] BUILD_ID = {build_id}")
    return build_id


def get_page(build_id, slug):
    r = requests.get(f"{BASE}/_next/data/{build_id}/{slug}.json", timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_all_series():
    all_items, page = [], 1
    log("[*] Fetching Hindi series list …")
    while True:
        log(f"[>] POST search-series-home page={page}")
        data = post(
            "/api/server/audio/search-series-home",
            {"page": page, "sortBy": "name", "language": "hindi"},
        )
        items = data["items"]
        all_items += items
        log(f"[+] Page {page}: {len(items)} items")
        if len(all_items) >= data["total"][0]["total"]:
            log(f"[✓] Total series fetched: {len(all_items)}")
            break
        page += 1
    return all_items


def fetch_episodes(series_id, first_page):
    eps = list(first_page["listData"])
    total = first_page["total"]
    pages = math.ceil(total / PER_PAGE)
    log(f"    [*] Episodes: {total} total, {pages} pages")
    for p in range(2, pages + 1):
        log(f"    [>] Fetching episodes page {p}/{pages}")
        data = post(
            "/api/server/audio/series-filter",
            {"perPage": PER_PAGE, "page": p, "currentId": series_id, "search": ""},
        )
        eps += data["listData"]
    log(f"    [✓] Episodes fetched: {len(eps)}")
    return eps


def fetch_subseries(series_id):
    subs, page = [], 1
    log("    [*] Fetching sub-series …")
    while True:
        log(f"    [>] subseries-filter page={page}")
        data = post(
            "/api/server/audio/subseries-filter",
            {
                "currentId": series_id,
                "perPage": 16,
                "sortBy": "index-dsc",
                "page": page,
            },
        )
        subs += data["listData"]
        if len(subs) >= data["total"][0]["total"]:
            log(f"    [✓] Sub-series fetched: {len(subs)}")
            break
        page += 1
    return subs


def main():
    build_id = get_build_id()
    structure = []

    for idx, s in enumerate(fetch_all_series(), 1):
        log(f"\n=== [{idx}] SERIES: {s['title']} ===")
        page = get_page(build_id, s["slug"])
        pd = page["pageProps"]["data"]["pageData"]
        entry = {"title": s["title"], "slug": s["slug"]}

        if "countSeries" in s:
            entry["type"] = "container"
            entry["subseries"] = []
            for ss in fetch_subseries(pd["categoryData"]["_id"]):
                sp = get_page(build_id, ss["slug"])
                spd = sp["pageProps"]["data"]["pageData"]
                eps = fetch_episodes(spd["categoryData"]["_id"], spd)
                entry["subseries"].append(
                    {"title": ss["title"], "slug": ss["slug"], "episodes": eps}
                )
        else:
            entry["type"] = "series"
            entry["episodes"] = fetch_episodes(pd["categoryData"]["_id"], pd)

        structure.append(entry)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)

    print(f"[✓] Structure cached → {OUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Exiting cleanly.")
        sys.exit(0)
