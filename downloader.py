import os
import re
import json
import time
import requests
from pathlib import Path

BASE = "https://oshoworld.com"
OUT_DIR = "downloads"
STRUCTURE_FILE = "structure.json"
CHUNK_SIZE = 1024 * 1024  # 1 MB


# -------------------- Utilities --------------------


def sanitize(name: str) -> str:
    return re.sub(r"[^\w\-. ()]", "_", name).strip()


def human_time(seconds: float) -> str:
    if seconds <= 0:
        return "∞"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# -------------------- Progress Tracker --------------------


class SeriesProgress:
    def __init__(self, total_eps: int):
        self.total = total_eps
        self.done = 0
        self.start = time.time()
        self.times = []

    def mark_episode_done(self, seconds):
        self.done += 1
        self.times.append(seconds)

    def eta(self) -> str:
        if not self.times:
            return "∞"
        avg = sum(self.times) / len(self.times)
        remaining = self.total - self.done
        return human_time(avg * remaining)


# -------------------- Load Cached Structure --------------------


def load_structure():
    if not os.path.exists(STRUCTURE_FILE):
        raise RuntimeError("structure.json not found. Run structure probe first.")
    with open(STRUCTURE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# -------------------- Episode Download --------------------


def download_episode(ep, folder, idx, total_eps, progress):
    url = BASE + ep["file"]
    name = sanitize(Path(url).name)
    out_path = Path(folder) / name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"    [{idx}/{total_eps}] Exists: {name}")
        progress.mark_episode_done(0)  # already done, no time added
        return

    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"    [{idx}/{total_eps}] Downloading {name}")

    episode_start = time.time()  # 🔹 START TIMING HERE
    last_print = episode_start

    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        file_size = int(r.headers.get("Content-Length", 0))
        written = 0

        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                if not chunk:
                    continue

                f.write(chunk)
                written += len(chunk)
                now = time.time()
                if now - last_print >= 1:
                    print(
                        f"\r    [{idx}/{total_eps}] {name[:40]:40} ETA {progress.eta()}",
                        end="",
                        flush=True,
                    )
                    last_print = now

        elapsed = time.time() - episode_start
        progress.mark_episode_done(elapsed)

        if file_size and written != file_size:
            print(f"    [!] Size mismatch for {name}")
        else:
            progress.mark_episode_done(time.time() - episode_start)
            print(f"    [✓] Done: {name}")


# -------------------- Entry Download --------------------


def download_entry(entry):
    print(f"\n=== Downloading Series: {entry['title']} ===")

    # Case 1: normal series
    if entry["type"] == "series":
        episodes = entry["episodes"]
        total_eps = len(episodes)

        total_bytes = sum(int(ep.get("size", 0)) for ep in episodes if ep.get("size"))
        progress = SeriesProgress(total_eps)

        folder = Path(OUT_DIR) / sanitize(entry["title"])

        for i, ep in enumerate(episodes, 1):
            download_episode(ep, folder, i, total_eps, progress)

    # Case 2: series with sub-series (e.g. Geeta Darshan)
    else:
        total_sub = len(entry["subseries"])

        for si, ss in enumerate(entry["subseries"], 1):
            episodes = ss["episodes"]
            total_eps = len(episodes)

            print(
                f"\n--- Sub-series [{si}/{total_sub}]: {ss['title']} ({total_eps} episodes) ---"
            )

            progress = SeriesProgress(total_eps)

            folder = Path(OUT_DIR) / sanitize(entry["title"]) / sanitize(ss["title"])

            for i, ep in enumerate(episodes, 1):
                download_episode(ep, folder, i, total_eps, progress)

    print(f"=== Finished: {entry['title']} ===\n")


# -------------------- CLI --------------------


def main():
    structure = load_structure()

    print("1. Regex search")
    print("2. List all")
    choice = input("> ").strip()

    if choice == "1":
        rx = re.compile(input("Regex: "), re.I)
        picks = [s for s in structure if rx.search(s["title"])]
    else:
        picks = structure

    for i, s in enumerate(picks, 1):
        print(f"[{i}] {s['title']}")

    sel = input("Select (comma or all): ").strip()

    if sel.lower() == "all":
        targets = picks
    else:
        idxs = [int(x) - 1 for x in sel.split(",") if x.strip().isdigit()]
        targets = [picks[i] for i in idxs if 0 <= i < len(picks)]

    for entry in targets:
        download_entry(entry)


if __name__ == "__main__":
    main()
