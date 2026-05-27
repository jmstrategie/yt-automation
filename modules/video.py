"""
modules/video.py
Assembles final MP4 from B-roll clips + voiceover audio + subtitles using FFmpeg.
"""

import os
import subprocess
import random
from pathlib import Path
from typing import List, Optional

from config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, VIDEO_BITRATE, AUDIO_BITRATE


def get_audio_duration(audio_path: str) -> float:
    """Return duration of an audio file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip()) if result.returncode == 0 else 0.0


def get_clip_duration(clip_path: str) -> float:
    """Return duration of a video clip in seconds."""
    return get_audio_duration(clip_path)


def build_video(
    clip_paths: List[str],
    audio_path: str,
    srt_path: Optional[str],
    output_path: str,
    intro_image: Optional[str] = None,
    outro_image: Optional[str] = None,
) -> str:
    """
    Assemble final video:
    1. Loop/trim B-roll clips to match audio duration
    2. Mix audio
    3. Burn in subtitles (if SRT provided)
    4. Encode to H.264 MP4

    Returns path to rendered MP4.
    """
    os.makedirs(Path(output_path).parent, exist_ok=True)

    audio_dur = get_audio_duration(audio_path)
    print(f"  [video] Audio duration: {audio_dur:.1f}s")
    print(f"  [video] B-roll clips: {len(clip_paths)}")

    # ── Step 1: build concat list, looping clips to fill audio duration ──────
    concat_file = output_path.replace(".mp4", "_concat.txt")
    total_filled = 0.0
    clip_sequence = []

    if not clip_paths:
        raise ValueError("No B-roll clips provided — cannot assemble video")

    # shuffle clips for variety
    shuffled = clip_paths.copy()
    random.shuffle(shuffled)

    # loop through clips until we've filled the audio duration
    i = 0
    while total_filled < audio_dur:
        clip = shuffled[i % len(shuffled)]
        clip_dur = get_clip_duration(clip)
        if clip_dur <= 0:
            i += 1
            continue
        clip_sequence.append(clip)
        total_filled += clip_dur
        i += 1
        if i > 200:  # safety valve
            break

    with open(concat_file, "w") as f:
        for clip in clip_sequence:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    print(f"  [video] Concat list: {len(clip_sequence)} clips ({total_filled:.1f}s)")

    # ── Step 2: concatenate B-roll ─────────────────────────────────────────────
    broll_raw = output_path.replace(".mp4", "_broll_raw.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
               f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
               f"fps={VIDEO_FPS}",
        "-c:v", "libx264", "-preset", "fast",
        "-t", str(audio_dur),
        "-an",
        broll_raw,
    ], check=True, capture_output=True)

    # ── Step 3: combine video + audio ─────────────────────────────────────────
    if False and srt_path and os.path.exists(srt_path):
        # copy SRT to /tmp to avoid spaces in path (FFmpeg subtitle filter limitation)
        import shutil
        srt_safe = "/tmp/voiceover.srt"
        shutil.copy(srt_path, srt_safe)
        subtitle_filter = (
            f"subtitles='{srt_safe}':"
            f"force_style='FontName=Arial,FontSize=18,PrimaryColour=&HFFFFFF&,"
            f"OutlineColour=&H000000&,Outline=2,Bold=1,"
            f"Alignment=2,MarginV=40'"
        )
        combined = output_path.replace(".mp4", "_nosubs.mp4")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", broll_raw,
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "fast", "-b:v", VIDEO_BITRATE,
            "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest",
            combined,
        ], check=True, capture_output=True)

        subprocess.run([
            "ffmpeg", "-y",
            "-i", combined,
            "-vf", subtitle_filter,
            "-c:v", "libx264", "-preset", "fast", "-b:v", VIDEO_BITRATE,
            "-c:a", "copy",
            output_path,
        ], check=True, capture_output=True)

        os.remove(combined)
    else:
        # no subtitles
        subprocess.run([
            "ffmpeg", "-y",
            "-i", broll_raw,
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "fast", "-b:v", VIDEO_BITRATE,
            "-c:a", "aac", "-b:a", AUDIO_BITRATE,
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest",
            output_path,
        ], check=True, capture_output=True)

    # ── Cleanup temp files ─────────────────────────────────────────────────────
    for tmp in [concat_file, broll_raw]:
        try:
            os.remove(tmp)
        except FileNotFoundError:
            pass

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  [video] Rendered: {Path(output_path).name} ({size_mb:.1f} MB)")
    return output_path


if __name__ == "__main__":
    # quick smoke test — requires real files
    print("video.py — import OK")
