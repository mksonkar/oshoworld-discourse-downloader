import os
import re
import json
import time
import sys
import requests
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://oshoworld.com"
BASE_OUT_DIR = Path("downloads")
CHUNK_SIZE = 1024 * 1024  # 1 MB
MAX_WORKERS = 4

STRUCTURE_FILES = {
    "hindi": {
        "path": "structure_hindi.json",
        "builder": ["python", "structure_cache_hindi.py"],
    },
    "english": {
        "path": "structure_english.json",
        "builder": ["python", "structure_cache_english.py"],
    },
}

# -------------------- Utilities --------------------


def ensure_cache(language):
    info = STRUCTURE_FILES[language]
    path = Path(info["path"])

    if path.exists():
        return

    print(f"[!] Cache missing for {language}, building it now...")
    print("One time process, it will take a few minutes")
    result = subprocess.run(info["builder"])

    if result.returncode != 0 or not path.exists():
        print(f"[!] Failed to build cache for {language}")
        sys.exit(1)


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


def load_structure(lang):
    path = STRUCTURE_FILES[lang]["path"]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Hindi format → list
    if isinstance(data, list):
        return data

    # English format → { language, series }
    if isinstance(data, dict) and "series" in data:
        return data["series"]

    raise ValueError("Unknown structure format")


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

        if file_size and written != file_size:
            print(f"    [!] Size mismatch for {name}")
        else:
            progress.mark_episode_done(elapsed)
            print(f"    [✓] Done: {name}")


# -------------------- Entry Download --------------------


def download_entry(entry, out_dir):
    print(f"\n=== Downloading Series: {entry['title']} ===")

    # Case 1: container with subseries (Hindi only)
    if "subseries" in entry:
        total_sub = len(entry["subseries"])

        for si, ss in enumerate(entry["subseries"], 1):
            episodes = ss["episodes"]
            total_eps = len(episodes)

            print(
                f"\n--- Sub-series [{si}/{total_sub}]: {ss['title']} ({total_eps} episodes) ---"
            )

            progress = SeriesProgress(total_eps)
            folder = out_dir / entry["slug"] / ss["slug"]

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [
                    executor.submit(
                        download_episode, ep, folder, i, total_eps, progress
                    )
                    for i, ep in enumerate(episodes, 1)
                ]
                for f in as_completed(futures):
                    f.result()

    # Case 2: normal series (ALL English + most Hindi)
    else:
        episodes = entry["episodes"]
        total_eps = len(episodes)

        progress = SeriesProgress(total_eps)
        folder = out_dir / entry["slug"]

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(download_episode, ep, folder, i, total_eps, progress)
                for i, ep in enumerate(episodes, 1)
            ]
            for f in as_completed(futures):
                f.result()

    print(f"=== Finished: {entry['title']} ===\n")


# -------------------- CLI --------------------


def main():

    print("=" * 40)
    print("        OSHO DISCOURSE DOWNLOADER")
    print("=" * 40)
    print("Select mode:")
    print("  1. English")
    print("  2. Hindi")
    print("  3. Global search")
    print("-" * 40)
    mode = input("> ").strip()
    if mode == "3":
        rx = re.compile(input("Regex (global): "), re.I)

        ensure_cache("hindi")
        ensure_cache("english")

        hindi_series = load_structure("hindi")
        english_series = load_structure("english")

        all_items = []
        for s in hindi_series:
            all_items.append(("hindi", s))
        for s in english_series:
            all_items.append(("english", s))

        matches = [(lang, s) for lang, s in all_items if rx.search(s["title"])]

        if not matches:
            print("[!] No matches found")
            return

        for i, (lang, s) in enumerate(matches, 1):
            print(f"[{i}] ({lang.upper()}) {s['title']}")

        sel = input("Select (comma or all): ").strip()

        if sel.lower() == "all":
            targets = matches
        else:
            idxs = [int(x) - 1 for x in sel.split(",") if x.isdigit()]
            targets = [matches[i] for i in idxs if 0 <= i < len(matches)]

        for lang, entry in targets:
            out_dir = BASE_OUT_DIR / lang
            out_dir.mkdir(parents=True, exist_ok=True)
            download_entry(entry, out_dir)

        return

    if mode == "1":
        lang = "english"
    elif mode == "2":
        lang = "hindi"
    else:
        print("Invalid choice")
        return

    structure_file = STRUCTURE_FILES[lang]["path"]

    OUT_DIR = BASE_OUT_DIR / lang
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ensure_cache(lang)
    series = load_structure(lang)

    print("1. Regex search")
    print("2. List all")
    choice = input("> ").strip()
    if choice == "1":
        rx = re.compile(input("Regex: "), re.I)
        picks = [s for s in series if rx.search(s["title"])]
    else:
        picks = series

    for i, s in enumerate(picks, 1):
        print(f"[{i}] {s['title']}")

    sel = input("Select (comma or all): ").strip()

    if sel.lower() == "all":
        targets = picks
    else:
        idxs = [int(x) - 1 for x in sel.split(",") if x.strip().isdigit()]
        targets = [picks[i] for i in idxs if 0 <= i < len(picks)]

    for entry in targets:
        download_entry(entry, OUT_DIR)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Exiting cleanly.")
        sys.exit(0)
