"""
modules/broll.py
Downloads free stock video clips from Pexels and Pixabay.
Uses Claude to extract cinematic, meaningful B-roll search queries from the script.
"""

import os
import json
import requests
from typing import List, Optional
from pathlib import Path

from config import PEXELS_API_KEY, PIXABAY_API_KEY


def extract_broll_queries(script_text: str, niche: str, n: int = 6) -> List[str]:
    """
    Use Claude to extract meaningful visual B-roll search queries from the script.
    Falls back to niche defaults if Claude call fails.
    """
    from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
    import anthropic

    # niche-specific fallbacks if Claude fails
    fallbacks = {
        "personal_finance_ai": [
            "stock market trading screen", "person using smartphone app",
            "money and coins close up", "financial planning desk",
            "AI technology data visualization", "Wall Street building exterior",
            "person reviewing investment portfolio", "credit card payment",
            "laptop with financial charts", "businessman walking city",
        ],
        "food_recipes": [
            "chef cooking in kitchen", "fresh vegetables cutting board",
            "meal prep containers", "food ingredients flat lay",
            "cooking pan on stove", "healthy meal plating",
            "grocery shopping produce", "food close up appetizing",
            "kitchen utensils countertop", "family eating dinner table",
        ],
    }

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        prompt = f"""You are a professional video editor choosing B-roll footage for a YouTube video.

Read this script and return exactly {n} specific visual search queries to find relevant stock footage on Pexels.

SCRIPT:
{script_text[:2000]}

NICHE: {niche}

RULES:
- Each query must be 2-4 words, highly visual and concrete
- Think like a cinematographer — what would you actually film to illustrate each section?
- NO abstract words, NO single words, NO pronouns, NO filler words
- Queries must work as stock footage search terms
- Vary the queries — cover different parts of the script, don't repeat concepts
- Prefer cinematic, professional-looking footage descriptions

GOOD examples: "stock market trading screen", "person checking investment app", "AI data visualization", "money coins stacking", "financial advisor meeting", "cryptocurrency price chart"
BAD examples: "An", "But", "money", "Robinhood", "here is why", "trading"

Return ONLY a JSON array of {n} strings, no other text, no markdown:
["query 1", "query 2", "query 3", "query 4", "query 5", "query 6"]"""

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        queries = json.loads(raw)
        print(f"  [broll] Claude queries: {queries}")
        return queries[:n]

    except Exception as e:
        print(f"  [broll] Claude query error: {e} — using fallbacks")
        return fallbacks.get(niche, fallbacks["personal_finance_ai"])[:n]


def search_pexels_videos(query: str, per_page: int = 5) -> List[str]:
    """Search Pexels for video clips. Returns list of direct video URLs."""
    if not PEXELS_API_KEY:
        print("  [broll] No Pexels API key — skipping Pexels")
        return []

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": "landscape",
        "size": "large",
        "min_duration": 5,
        "max_duration": 30,
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        videos = r.json().get("videos", [])
        links = []
        for v in videos:
            duration = v.get("duration", 0)
            if duration < 5:
                continue
            files = sorted(v.get("video_files", []), key=lambda f: f.get("width", 0), reverse=True)
            best = next((f for f in files if f.get("width", 0) >= 1920 and f.get("file_type") == "video/mp4"), None)
            if not best:
                best = next((f for f in files if f.get("width", 0) >= 1280 and f.get("file_type") == "video/mp4"), None)
            if best:
                links.append(best["link"])
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
        "order": "popular",
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

        # verify it's a real video with sufficient duration
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", output_path],
            capture_output=True, text=True,
        )
        duration = float(result.stdout.strip()) if result.returncode == 0 else 0
        if duration < 4:
            print(f"  [broll] Skipping {Path(output_path).name} — too short ({duration:.1f}s)")
            os.remove(output_path)
            return None

        print(f"  [broll] Downloaded {Path(output_path).name} ({size_mb:.1f} MB, {duration:.1f}s)")
        return output_path
    except Exception as e:
        print(f"  [broll] Download error: {e}")
        return None


def fetch_broll_clips(
    script_text: str,
    niche: str,
    output_dir: str,
    num_clips: int = 10,
) -> List[str]:
    """
    Main entry: Claude query generation → Pexels search → download clips.
    Returns list of local file paths.
    """
    os.makedirs(output_dir, exist_ok=True)

    # get cinematic queries from Claude
    queries = extract_broll_queries(script_text, niche, n=num_clips)

    clip_paths = []
    clip_index = 0

    for query in queries:
        if len(clip_paths) >= num_clips:
            break

        # try Pexels first (higher quality), fallback to Pixabay
        urls = search_pexels_videos(query, per_page=2)
        if not urls:
            urls = search_pixabay_videos(query, per_page=2)

        if not urls:
            print(f"  [broll] No results for '{query}' — skipping")
            continue

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
    from dotenv import load_dotenv
    load_dotenv()
    clips = fetch_broll_clips(
        "Robinhood just launched AI trading bots that buy and sell stocks automatically. "
        "78% of retail traders using algorithmic strategies lose money. "
        "We explain what's really happening with AI investing apps.",
        "personal_finance_ai",
        "temp/broll_test",
        num_clips=6,
    )
    print(clips)