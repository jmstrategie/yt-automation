"""
pipeline.py
Main orchestrator — runs the full YouTube automation pipeline for one or both channels.

Usage:
  python pipeline.py                          # run both channels
  python pipeline.py --channel A              # channel A only
  python pipeline.py --channel B              # channel B only
  python pipeline.py --channel A --dry-run    # generate script only, no upload
  python pipeline.py --channel A --topics 3  # generate 3 topic options
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
from config import CHANNEL_A, CHANNEL_B, ALL_CHANNELS, OUTPUT_DIR, TEMP_DIR, SECRETS_DIR
from modules.trends import get_topics_for_channel
from modules.script import generate_script, generate_series_scripts
from modules.voiceover import generate_voiceover
from modules.broll import fetch_broll_clips
from modules.video import build_video
from modules.thumbnail import generate_thumbnail
from modules.upload import upload_video, schedule_series_uploads


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


# ── Single video pipeline ─────────────────────────────────────────────────────

def run_single_video(channel, topic: dict, dry_run: bool = False) -> dict:
    """
    Full pipeline for one standalone video.
    Returns a result dict with paths and metadata.
    """
    slug = topic["title"].lower().replace(" ", "_")[:40]
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{channel.name}_{slug}_{timestamp}"

    work_dir = os.path.join(TEMP_DIR, run_id)
    out_dir = os.path.join(OUTPUT_DIR, channel.name)
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    log(f"Starting: '{topic['title']}' [{channel.name}]")

    # ── 1. Script ──────────────────────────────────────────────────────────────
    log("Step 1/5: Generating script...")
    script = generate_script(channel, topic)

    if dry_run:
        log("Dry run — stopping after script generation")
        print(f"\n{'='*60}")
        print(f"TITLE: {script.title}")
        print(f"THUMBNAIL TEXT: {script.thumbnail_text}")
        print(f"\nHOOK:\n{script.hook}")
        print(f"\nBODY (first 300 chars):\n{script.body[:300]}...")
        print(f"\nCTA:\n{script.cta}")
        return {"dry_run": True, "script": script}

    # ── 2. Voiceover ───────────────────────────────────────────────────────────
    log("Step 2/5: Generating voiceover...")
    mp3_path, srt_path = generate_voiceover(
        channel, script.full_text, work_dir, "voiceover"
    )

    # ── 3. B-roll ──────────────────────────────────────────────────────────────
    log("Step 3/5: Fetching B-roll clips...")
    broll_dir = os.path.join(work_dir, "broll")
    clip_paths = fetch_broll_clips(
        script_text=script.full_text,
        niche=channel.niche,
        output_dir=broll_dir,
        num_clips=10,
    )

    if not clip_paths:
        log("No B-roll clips found — using colour card fallback", "WARN")
        # create a simple solid-colour clip as fallback
        fallback = os.path.join(work_dir, "fallback.mp4")
        os.system(
            f'ffmpeg -y -f lavfi -i color=c=0x0f0f19:size=1920x1080:rate=30 '
            f'-t 10 -c:v libx264 "{fallback}" -loglevel quiet'
        )
        clip_paths = [fallback]

    # ── 4. Video render ────────────────────────────────────────────────────────
    log("Step 4/5: Rendering video...")
    video_path = os.path.join(out_dir, f"{run_id}.mp4")
    build_video(
        clip_paths=clip_paths,
        audio_path=mp3_path,
        srt_path=srt_path,
        output_path=video_path,
    )

    # ── 5. Thumbnail ───────────────────────────────────────────────────────────
    log("Step 5/5: Generating thumbnail...")
    thumb_path = os.path.join(out_dir, f"{run_id}_thumb.jpg")
    generate_thumbnail(
        channel=channel,
        thumbnail_text=script.thumbnail_text,
        output_path=thumb_path,
        bg_query=topic["keywords"][0] if topic.get("keywords") else None,
    )

    # ── Cleanup temp ───────────────────────────────────────────────────────────
    try:
        shutil.rmtree(work_dir)
    except Exception:
        pass

    result = {
        "run_id": run_id,
        "title": script.title,
        "video_path": video_path,
        "thumbnail_path": thumb_path,
        "script": script,
        "topic": topic,
    }

    log(f"Video ready: {video_path}")
    return result


# ── Series pipeline ────────────────────────────────────────────────────────────

def run_series(channel, topic: dict, dry_run: bool = False) -> list:
    """Run pipeline for all parts of a series. Returns list of result dicts."""
    log(f"Series detected: '{topic['title']}' ({topic['series_parts']} parts)")
    scripts = generate_series_scripts(channel, topic)

    if dry_run:
        for s in scripts:
            print(f"\n[Part {s.part}/{s.total_parts}] {s.title}")
            print(f"Hook: {s.hook[:150]}...")
        return [{"dry_run": True}]

    results = []
    for i, script in enumerate(scripts):
        part_topic = dict(topic)
        part_topic["title"] = script.title
        part_topic["_override_script"] = script

        result = run_single_video(channel, part_topic, dry_run=False)
        result["script"] = script
        results.append(result)

    return results


# ── Channel runner ─────────────────────────────────────────────────────────────

def run_channel(channel, dry_run: bool = False, num_topics: int = 1) -> None:
    """Run the full pipeline for a channel — scrape topics, produce video(s), upload."""
    log(f"{'='*50}")
    log(f"Channel: {channel.name} | niche: {channel.niche}")
    log(f"{'='*50}")

    # get topics
    topics = get_topics_for_channel(channel, n=max(num_topics, 3))
    # pick the best one (first = highest ranked by Claude)
    topic = topics[0]

    if topic.get("is_series") and channel.series_enabled:
        results = run_series(channel, topic, dry_run=dry_run)
        if dry_run:
            return

        # upload series
        log("Uploading series to YouTube...")
        schedule_series_uploads(
            channel=channel,
            videos=results,
            series_title=topic["title"],
        )
    else:
        result = run_single_video(channel, topic, dry_run=dry_run)
        if dry_run:
            return

        # upload single video
        log("Uploading to YouTube...")
        upload_video(
            channel=channel,
            video_path=result["video_path"],
            thumbnail_path=result["thumbnail_path"],
            title=result["script"].title,
            description=result["script"].description,
            tags=result["script"].tags,
        )

    log(f"Channel {channel.name} — DONE")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="YouTube Automation Pipeline")
    parser.add_argument("--channel", choices=["A", "B", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true", help="Script only, no upload")
    parser.add_argument("--topics", type=int, default=1, help="Number of topic candidates")
    args = parser.parse_args()

    # validate API key
    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        log("ANTHROPIC_API_KEY not set. Add it to your .env or GitHub Secrets.", "ERROR")
        sys.exit(1)

    channels = {
        "A": [CHANNEL_A],
        "B": [CHANNEL_B],
        "both": ALL_CHANNELS,
    }[args.channel]

    for channel in channels:
        try:
            run_channel(channel, dry_run=args.dry_run, num_topics=args.topics)
        except Exception as e:
            log(f"Pipeline failed for {channel.name}: {e}", "ERROR")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
