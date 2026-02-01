# The best Osho Discourse Downloader

A python based CLI tool to fetch and download all **Osho English & Hindi audio discourses** from https://oshoworld.com, with full support for series, sub-series, episode pagination, caching, progress tracking, auto resume and parallel downloads.

## Features
- Fetches all English & Hindi discourse series
- **Parallel downloads**
- **Global search** with RegEx support
- Handles nested sub-series (e.g. Geeta Darshan)
- Reliable episode pagination
- Selective download via regex search or list all
- Progress display with per-series ETA
- **Resume-safe** (skips existing files)
- **Cache entire list** (no refetching structure on every run)
- **Safe, stable folder names** using backend slugs

## Requirements
- Python 3.10+

## Installation

### 1. Clone the repo
```bash
git clone https://github.com/mksonkar/oshoworld-discourse-downloader.git
cd oshoworld-scraper
```
### 2. Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install requests
```
### 3. Run the scraper once to generate and save the list of discourses
```bash
python structure_cache_english.py
python structure_cache_hindi.py
```
### 3. Run the downloader script
```bash
python downloader.py
```

