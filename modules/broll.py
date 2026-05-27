"""
modules/broll.py
Downloads free stock video clips from Pexels and Pixabay
based on keywords extracted from the video script.
"""

import os
import re
import requests
from typing import List, Optional
from pathlib import Path

from config import PEXELS_API_KEY, PIXABAY_API_KEY


def search_pexels_videos(query: str, per_page: int = 5) -> List[str]:
    """Search Pexels for video clips. Returns list of direct video URLs."""
    if not PEXELS_API_KEY:
        print("  [broll] No Pexels API key — skipping Pexels")
        return []

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": per_page, "orientation": "landscape"}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        videos = r.json().get("videos", [])
        links = []
        for v in videos:
            # prefer HD (1280x720) or Full HD
            files = sorted(v.get("video_files", []), key=lambda f: f.get("width", 0))
            hd = next((f for f in files if f.get("width", 0) >= 1280), None)
            if hd:
                links.append(hd["link"])
        return links
    except Exception as e:
        print(f"  [broll] Pexels error: {e}")
        return []


def search_pixabay_videos(query: str, per_page: int = 5) -> List[str]:
    """Search Pixabay for video clips. Returns list of direct video URLs."""
    if not PIXABAY_API_KEY:
        print("  [broll] No Pixabay API key — skipping Pixabay")
        return []

    url = "https://pixabay.com/api/videos/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "per_page": per_page,
        "video_type": "film",
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        links = []
        for h in hits:
            videos = h.get("videos", {})
            hd = videos.get("large", {}).get("url") or videos.get("medium", {}).get("url")
            if hd:
                links.append(hd)
        return links
    except Exception as e:
        print(f"  [broll] Pixabay error: {e}")
        return []


def download_clip(url: str, output_path: str, timeout: int = 60) -> Optional[str]:
    """Download a video clip to disk. Returns path or None on failure."""
    try:
        r = requests.get(url, stream=True, timeout=timeout)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  [broll] Downloaded {Path(output_path).name} ({size_mb:.1f} MB)")
        return output_path
    except Exception as e:
        print(f"  [broll] Download error: {e}")
        return None


def extract_broll_queries(script_text: str, niche: str, n: int = 6) -> List[str]:
    """
    Extract B-roll search queries from a script.
    Uses simple keyword extraction — replace with Claude call for higher quality.
    """
    # niche-specific fallback queries
    fallbacks = {
        "personal_finance_ai": [
            "money", "investment", "technology", "office", "city",
            "computer", "stock market", "financial planning"
        ],
        "food_recipes": [
            "cooking", "food", "kitchen", "vegetables", "meal prep",
            "restaurant", "ingredients", "chef"
        ],
    }

    # extract capitalized multi-word phrases and nouns from script
    words = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", script_text)
    common_stopwords = {"The", "This", "That", "When", "What", "How", "Why"}
    queries = [w for w in words if w not in common_stopwords]

    # deduplicate and mix with fallbacks
    seen = set()
    result = []
    for q in queries + fallbacks.get(niche, []):
        if q.lower() not in seen:
            seen.add(q.lower())
            result.append(q)
        if len(result) >= n:
            break

    return result


def fetch_broll_clips(
    script_text: str,
    niche: str,
    output_dir: str,
    num_clips: int = 8,
) -> List[str]:
    """
    Main entry: search + download B-roll clips for a video.
    Returns list of local file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    queries = extract_broll_queries(script_text, niche, n=num_clips)
    print(f"  [broll] Queries: {queries[:4]}...")

    clip_paths = []
    clip_index = 0

    for query in queries:
        if len(clip_paths) >= num_clips:
            break

        # try Pexels first, fallback to Pixabay
        urls = search_pexels_videos(query, per_page=2)
        if not urls:
            urls = search_pixabay_videos(query, per_page=2)

        for url in urls:
            if len(clip_paths) >= num_clips:
                break
            out = os.path.join(output_dir, f"broll_{clip_index:02d}.mp4")
            path = download_clip(url, out)
            if path:
                clip_paths.append(path)
                clip_index += 1

    print(f"  [broll] {len(clip_paths)} clips ready")
    return clip_paths


if __name__ == "__main__":
    clips = fetch_broll_clips(
        "investing money stock market financial freedom",
        "personal_finance_ai",
        "temp/broll_test",
        num_clips=3,
    )
    print(clips)
