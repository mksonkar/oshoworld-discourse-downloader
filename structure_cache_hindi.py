import requests, json, math

BASE = "https://oshoworld.com"
HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
PER_PAGE = 10
OUT = "structure.json"


def post(path, payload):
    r = requests.post(BASE + path, headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def get_build_id():
    html = requests.get(BASE, timeout=30).text
    return html.split('"buildId":"')[1].split('"', 1)[0]


def get_page(build_id, slug):
    r = requests.get(f"{BASE}/_next/data/{build_id}/{slug}.json", timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_all_series():
    all_items, page = [], 1
    while True:
        data = post(
            "/api/server/audio/search-series-home",
            {"page": page, "sortBy": "name", "language": "hindi"},
        )
        all_items += data["items"]
        if len(all_items) >= data["total"][0]["total"]:
            break
        page += 1
    return all_items


def fetch_episodes(series_id, first_page):
    eps = list(first_page["listData"])
    total = first_page["total"]
    pages = math.ceil(total / PER_PAGE)
    for p in range(2, pages + 1):
        data = post(
            "/api/server/audio/series-filter",
            {"perPage": PER_PAGE, "page": p, "currentId": series_id, "search": ""},
        )
        eps += data["listData"]
    return eps


def fetch_subseries(series_id):
    subs, page = [], 1
    while True:
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
            break
        page += 1
    return subs


def main():
    build_id = get_build_id()
    structure = []

    for s in fetch_all_series():
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

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=2)

    print(f"[✓] Structure cached → {OUT}")


if __name__ == "__main__":
    main()
