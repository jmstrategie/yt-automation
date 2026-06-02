"""
modules/broll.py
Downloads free stock video clips from Pexels and Pixabay.
For horror_fiction niche: generates dark atmospheric images with GPT Image
and converts them to video clips using FFmpeg (Ken Burns zoom effect).
Uses Claude to extract cinematic, meaningful B-roll search queries from the script.
"""

import os
import json
import base64
import subprocess
import requests
from typing import List, Optional
from pathlib import Path

from config import PEXELS_API_KEY, PIXABAY_API_KEY


# ── Claude B-roll query extraction ────────────────────────────────────────────

def extract_broll_queries(script_text: str, niche: str, n: int = 6) -> List[str]:
    """Use Claude to extract meaningful visual B-roll search queries from the script."""
    from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
    import anthropic

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
        "dark_history": [
            "ancient ruins stone", "dark forest foggy",
            "old manuscript candlelight", "archaeological dig site",
            "ancient temple exterior", "historical map parchment",
            "medieval castle dark", "ancient artifacts museum",
            "stormy dramatic sky", "ancient civilization ruins",
        ],
        "horror_fiction": [
            "dark abandoned hallway", "candlelight Victorian room",
            "creepy old house exterior", "dark forest night",
            "dusty attic shadows", "old rocking chair empty room",
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
- Queries must work as stock footage search terms on Pexels
- Vary the queries — cover different parts of the script, don't repeat concepts
- Prefer cinematic, professional-looking footage descriptions

GOOD examples for finance: "stock market trading screen", "person checking investment app", "AI data visualization", "money coins stacking"
GOOD examples for horror: "dark abandoned hallway", "candlelight Victorian room", "creepy old house exterior", "foggy dark forest night"
BAD examples: "An", "But", "money", "here is why", "trading"

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


# ── GPT Image horror scene generation ─────────────────────────────────────────

def _generate_horror_scene_prompts(script_text: str, n: int = 8) -> List[str]:
    """Use Claude to extract cinematic horror scene descriptions from the script."""
    from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are a horror cinematographer creating visual scenes for a YouTube horror video.

Read this script and generate {n} image prompts for dark atmospheric horror scenes.

SCRIPT:
{script_text[:2000]}

RULES:
- Each prompt must describe a specific cinematic horror scene
- Style: hyper-realistic, cinematic, dark atmospheric horror
- Settings: Victorian rooms, abandoned houses, dark forests, candlelit rooms, dusty attics, old basements
- Lighting: single candle, moonlight through broken window, dim lamp, deep shadows
- Mood: ominous, unsettling, dread-inducing, suffocating
- Include a creepy porcelain or ragdoll in most scenes — positioned unnervingly
- No text in images, no faces of real people
- Deep brown, black, sepia color palette with occasional blood red accent
- Film grain, atmospheric fog, dust particles in air, cobwebs
- Vary the scenes — different settings and angles for visual interest
- NEVER describe nature landscapes, icicles, or abstract imagery

Return ONLY a JSON array of {n} strings, no other text, no markdown:
["prompt 1", "prompt 2", ...]"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    prompts = json.loads(raw.strip())
    return prompts[:n]


def _image_to_video_clip(img_path: str, clip_path: str, duration: int = 8) -> Optional[str]:
    """Convert a static image to a video clip with subtle Ken Burns zoom effect."""
    try:
        frames = duration * 30
        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", img_path,
            "-vf", (
                f"scale=2048:1152:force_original_aspect_ratio=increase,"
                f"crop=1920:1080,"
                f"zoompan=z='if(lte(zoom,1.0),1.05,zoom+0.0005)'"
                f":d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":s=1920x1080:fps=30"
            ),
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            clip_path,
        ], check=True, capture_output=True)
        return clip_path
    except subprocess.CalledProcessError as e:
        print(f"  [broll] Zoom error — trying simple version")
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", img_path,
                "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-r", "30",
                clip_path,
            ], check=True, capture_output=True)
            return clip_path
        except Exception as e2:
            print(f"  [broll] Simple clip error: {e2}")
            return None


def fetch_horror_images_as_clips(
    script_text: str,
    output_dir: str,
    num_clips: int = 8,
) -> List[str]:
    """
    Generate dark atmospheric images with GPT Image model
    and convert each to an 8-second video clip with Ken Burns zoom effect.
    """
    from config import OPENAI_API_KEY
    from openai import OpenAI

    os.makedirs(output_dir, exist_ok=True)

    if not OPENAI_API_KEY:
        print("  [broll] No OpenAI key — falling back to stock footage")
        return []

    client = OpenAI(api_key=OPENAI_API_KEY)
    scene_prompts = _generate_horror_scene_prompts(script_text, num_clips)
    clip_paths = []

    for i, scene_prompt in enumerate(scene_prompts):
        try:
            print(f"  [broll] GPT Image generating horror scene {i+1}/{len(scene_prompts)}...")

            response = client.images.generate(
                model="gpt-image-1",
                prompt=scene_prompt,
                size="1536x1024",
                quality="standard",
                n=1,
            )

            # gpt-image-1 returns base64, not URL
            b64_data = response.data[0].b64_json
            img_data = base64.b64decode(b64_data)

            # save image
            img_path = os.path.join(output_dir, f"horror_img_{i:02d}.jpg")
            with open(img_path, "wb") as f:
                f.write(img_data)

            # convert image to video clip with Ken Burns zoom
            clip_path = os.path.join(output_dir, f"broll_{i:02d}.mp4")
            result = _image_to_video_clip(img_path, clip_path, duration=8)

            # clean up source image
            try:
                os.remove(img_path)
            except Exception:
                pass

            if result:
                clip_paths.append(clip_path)
                print(f"  [broll] Horror clip {i+1} ready")

        except Exception as e:
            print(f"  [broll] Horror scene {i+1} error: {e}")

    print(f"  [broll] {len(clip_paths)} horror clips ready")
    return clip_paths


# ── Local horror footage library ──────────────────────────────────────────────

def fetch_from_local_library(
    output_dir: str,
    num_clips: int = 10,
    library_dir: str = "assets/horror_footage",
) -> List[str]:
    """Pick random clips from the local horror footage library."""
    import random
    import shutil

    manifest_path = os.path.join(library_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return []

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)

        all_clips = [c["path"] for c in manifest["clips"] if os.path.exists(c["path"])]
        if not all_clips:
            return []

        selected = random.sample(all_clips, min(num_clips, len(all_clips)))
        os.makedirs(output_dir, exist_ok=True)

        copied = []
        for i, src in enumerate(selected):
            dst = os.path.join(output_dir, f"broll_{i:02d}.mp4")
            shutil.copy2(src, dst)
            copied.append(dst)

        print(f"  [broll] {len(copied)} clips from local library")
        return copied

    except Exception as e:
        print(f"  [broll] Local library error: {e}")
        return []


# ── Pexels / Pixabay stock footage ────────────────────────────────────────────

def search_pexels_videos(query: str, per_page: int = 5) -> List[str]:
    """Search Pexels for video clips. Returns list of direct video URLs."""
    if not PEXELS_API_KEY:
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
    """Search Pixabay for video clips."""
    if not PIXABAY_API_KEY:
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


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_broll_clips(
    script_text: str,
    niche: str,
    output_dir: str,
    num_clips: int = 10,
) -> List[str]:
    """
    Main entry: route to correct B-roll strategy based on niche.
    Horror fiction priority:
      1. Local library (fast, free)
      2. GPT Image generated scenes (unique, on-brand)
      3. Pexels/Pixabay fallback
    All other niches: Claude queries → Pexels/Pixabay
    """
    os.makedirs(output_dir, exist_ok=True)

    if niche == "horror_fiction":
        # try local library first
        local_clips = fetch_from_local_library(output_dir, num_clips)
        if len(local_clips) >= num_clips // 2:
            # mix local clips with GPT Image scenes for variety
            dalle_dir = output_dir + "_dalle"
            dalle_clips = fetch_horror_images_as_clips(script_text, dalle_dir, num_clips=3)
            combined = local_clips[:num_clips - len(dalle_clips)] + dalle_clips
            print(f"  [broll] Hybrid: {len(local_clips)} local + {len(dalle_clips)} GPT Image")
            return combined[:num_clips]

        # fallback to pure GPT Image if no local library
        print("  [broll] No local library — using GPT Image only")
        clips = fetch_horror_images_as_clips(script_text, output_dir, num_clips)
        if clips:
            return clips

    # all other niches + horror fallback: Claude queries + Pexels/Pixabay
    queries = extract_broll_queries(script_text, niche, n=num_clips)
    clip_paths = []
    clip_index = 0

    for query in queries:
        if len(clip_paths) >= num_clips:
            break

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

    test_script = """
    In 1987, a family in rural Ohio found a porcelain doll sitting in their daughter's rocking chair.
    The doll had not been there the night before. Its eyes were painted open, staring at the bedroom door.
    What happened next would destroy the family completely.
    """
    clips = fetch_broll_clips(
        test_script,
        "horror_fiction",
        "temp/broll_horror_test",
        num_clips=4,
    )
    print(f"Generated {len(clips)} clips: {clips}")
