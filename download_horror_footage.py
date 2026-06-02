"""
download_horror_footage.py
One-time script to build a local horror footage library.
Downloads ~100 dark atmospheric clips from Pexels and Mixkit.
Run once: python3 download_horror_footage.py
Pipeline will then use these clips randomly instead of downloading each run.
"""

import os
import json
import time
import requests
import subprocess
from pathlib import Path
from typing import List, Optional

# ── Config ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "assets/horror_footage"
TARGET_CLIPS = 100
MIN_DURATION = 5   # seconds
MAX_DURATION = 30  # seconds

# Horror-specific Pexels search queries
PEXELS_QUERIES = [
    # Atmospheric / Environmental
    "dark foggy forest night",
    "abandoned house exterior night",
    "candle flame dark room",
    "dark hallway shadows",
    "old wooden staircase dark",
    "dusty attic sunbeam",
    "fog rolling dark road",
    "stormy dark sky lightning",
    "dark basement concrete walls",
    "old cemetery fog",
    "burning candles Victorian",
    "dark window rain",
    "abandoned asylum hallway",
    "dark forest path",
    "moonlight through window",
    # Objects / Details
    "old rocking chair empty",
    "antique clock pendulum",
    "dusty old books shelf",
    "cobwebs dark corner",
    "old mirror reflection dark",
    "vintage photograph sepia",
    "rusty door handle",
    "old typewriter dark",
    "broken window glass",
    "old wooden music box",
    "antique lamp flickering",
    "old locked door",
    "moth eaten curtain window",
    "vintage wallpaper peeling",
    "old bloodstained floor",
    # Mood / Texture
    "dark smoke atmospheric",
    "shadow on wall movement",
    "flickering light dark room",
    "raindrops window night",
    "fire embers dark",
    "dark water reflection",
    "dust particles light beam",
    "dark concrete texture",
    "old wooden floor creak",
    "black crow perched",
]

# Mixkit free horror clips (direct download URLs — no API needed)
MIXKIT_QUERIES = [
    "dark",
    "horror",
    "fog",
    "night",
    "abandoned",
    "dark-forest",
    "candle",
    "storm",
    "smoke",
    "shadow",
]


def get_pexels_clips(query: str, api_key: str, per_page: int = 5) -> List[dict]:
    """Search Pexels for video clips matching query."""
    if not api_key:
        return []
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": api_key},
            params={
                "query": query,
                "per_page": per_page,
                "orientation": "landscape",
                "size": "large",
                "min_duration": MIN_DURATION,
                "max_duration": MAX_DURATION,
            },
            timeout=15,
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        results = []
        for v in videos:
            duration = v.get("duration", 0)
            if duration < MIN_DURATION:
                continue
            files = sorted(v.get("video_files", []), key=lambda f: f.get("width", 0), reverse=True)
            best = next((f for f in files if f.get("width", 0) >= 1280 and f.get("file_type") == "video/mp4"), None)
            if best:
                results.append({
                    "url": best["link"],
                    "duration": duration,
                    "source": "pexels",
                    "query": query,
                })
        return results
    except Exception as e:
        print(f"  Pexels error for '{query}': {e}")
        return []


def download_clip(url: str, output_path: str) -> Optional[str]:
    """Download a video clip and verify it's valid."""
    try:
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        # verify duration
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", output_path],
            capture_output=True, text=True,
        )
        duration = float(result.stdout.strip()) if result.returncode == 0 else 0
        if duration < MIN_DURATION:
            os.remove(output_path)
            return None

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"    ✓ {Path(output_path).name} ({size_mb:.1f}MB, {duration:.0f}s)")
        return output_path

    except Exception as e:
        print(f"    ✗ Download failed: {e}")
        try:
            os.remove(output_path)
        except Exception:
            pass
        return None


def build_manifest(footage_dir: str) -> dict:
    """Build a JSON manifest of all downloaded clips with metadata."""
    clips = []
    for f in sorted(Path(footage_dir).glob("*.mp4")):
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(f)],
            capture_output=True, text=True,
        )
        duration = float(result.stdout.strip()) if result.returncode == 0 else 0
        clips.append({
            "filename": f.name,
            "path": str(f),
            "duration": duration,
        })

    manifest = {
        "total_clips": len(clips),
        "total_duration_minutes": round(sum(c["duration"] for c in clips) / 60, 1),
        "clips": clips,
    }

    manifest_path = os.path.join(footage_dir, "manifest.json")
    with open(manifest_path, "w") as mf:
        json.dump(manifest, mf, indent=2)

    return manifest


def main():
    from dotenv import load_dotenv
    load_dotenv()

    pexels_key = os.environ.get("PEXELS_API_KEY", "")

    print("🎬 Horror Footage Library Builder")
    print(f"Target: {TARGET_CLIPS} clips → {OUTPUT_DIR}/\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # check what's already downloaded
    existing = list(Path(OUTPUT_DIR).glob("*.mp4"))
    print(f"Already have {len(existing)} clips\n")

    downloaded = len(existing)
    clip_index = len(existing)

    # ── Pexels downloads ──────────────────────────────────────────────────────
    if pexels_key:
        print(f"📥 Downloading from Pexels ({len(PEXELS_QUERIES)} queries)...\n")

        for query in PEXELS_QUERIES:
            if downloaded >= TARGET_CLIPS:
                break

            print(f"  Searching: '{query}'")
            clips = get_pexels_clips(query, pexels_key, per_page=3)

            for clip in clips:
                if downloaded >= TARGET_CLIPS:
                    break

                out_path = os.path.join(OUTPUT_DIR, f"horror_{clip_index:03d}.mp4")

                # skip if similar clip already exists
                if os.path.exists(out_path):
                    clip_index += 1
                    continue

                result = download_clip(clip["url"], out_path)
                if result:
                    downloaded += 1
                    clip_index += 1

            time.sleep(0.5)  # rate limit respect

    else:
        print("⚠️  No PEXELS_API_KEY found — skipping Pexels\n")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"Building manifest...")
    manifest = build_manifest(OUTPUT_DIR)

    print(f"\n✅ Horror footage library ready!")
    print(f"   Total clips:    {manifest['total_clips']}")
    print(f"   Total duration: {manifest['total_duration_minutes']} minutes")
    print(f"   Location:       {OUTPUT_DIR}/")
    print(f"\nThe pipeline will now use these clips automatically for Channel B.")
    print(f"Run this script again anytime to add more clips.")


if __name__ == "__main__":
    main()
