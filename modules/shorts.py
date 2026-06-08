"""
modules/shorts.py
Generates YouTube Shorts (vertical 60-second videos) from long-form scripts.
Shorts are posted the day after the long-form video automatically.
Uses the hook section + key stat from the full script.
"""

import os
import json
import subprocess
import asyncio
from pathlib import Path
from typing import Optional
import anthropic

from config import ChannelConfig, ANTHROPIC_API_KEY, CLAUDE_MODEL


def generate_shorts_script(
    channel: ChannelConfig,
    long_form_script_hook: str,
    long_form_title: str,
    target_keyword: str,
) -> dict:
    """
    Generate a 45-60 second Shorts script from the long-form hook.
    Returns dict with script, title, description, tags.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are a YouTube Shorts scriptwriter specializing in {channel.niche}.

Take this long-form video hook and transform it into a punchy 45-60 second YouTube Short.

LONG-FORM TITLE: {long_form_title}
TARGET KEYWORD: {target_keyword}
LONG-FORM HOOK:
{long_form_hook[:500]}

SHORTS RULES:
- Open with a HOOK in the first 2 seconds — shocking stat, bold claim, or question
- Total script: 80-110 words MAX (45-60 seconds at speaking pace)
- No intro, no "welcome back", no subscribe begging at start
- Every sentence must earn its place — ruthless editing
- End with ONE clear action: "Follow for Part 2", "Save this", "Comment your answer"
- Write for vertical video — no visual references
- Format: conversational, fast-paced, energetic
- Title format: "[Number/Hook] [Benefit] #shorts"

Return ONLY valid JSON, no markdown:
{{
  "title": "Short punchy title under 60 chars with #shorts",
  "script": "Full 80-110 word script",
  "description": "50-word description with keyword and call to action",
  "tags": ["shorts", "tag2", "tag3", "tag4", "tag5"],
  "thumbnail_text": "3-4 bold words for thumbnail"
}}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    word_count = len(data["script"].split())
    print(f"  [shorts] Script: {word_count} words (~{word_count * 60 // 140}s)")
    return data


def generate_shorts_voiceover(
    channel: ChannelConfig,
    script: str,
    output_dir: str,
) -> str:
    """Generate voiceover MP3 for the Short."""
    os.makedirs(output_dir, exist_ok=True)
    mp3_path = os.path.join(output_dir, "shorts_voiceover.mp3")

    # use ElevenLabs if available, else edge-tts
    if channel.elevenlabs_voice_id:
        try:
            from elevenlabs import ElevenLabs
            from elevenlabs.types import VoiceSettings
            from config import ELEVENLABS_API_KEY

            client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            audio = client.text_to_speech.convert(
                voice_id=channel.elevenlabs_voice_id,
                text=script,
                model_id="eleven_turbo_v2",
                voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75),
            )
            with open(mp3_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            print(f"  [shorts] ElevenLabs voiceover done")
            return mp3_path
        except Exception as e:
            print(f"  [shorts] ElevenLabs failed: {e} — using edge-tts")

    # edge-tts fallback
    import edge_tts
    asyncio.run(
        edge_tts.Communicate(script, channel.voice).save(mp3_path)
    )
    print(f"  [shorts] edge-tts voiceover done")
    return mp3_path


def get_audio_duration(audio_path: str) -> float:
    """Get duration of audio file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip()) if result.returncode == 0 else 60.0


def render_shorts_video(
    audio_path: str,
    output_path: str,
    channel: ChannelConfig,
    thumbnail_text: str,
    bg_color: tuple = (10, 12, 28),
) -> str:
    """
    Render a vertical 1080x1920 Short video.
    Uses a solid colour background with large text overlay.
    For finance: dark background with bold green/white text.
    For horror: dark background with red accent text.
    """
    os.makedirs(Path(output_path).parent, exist_ok=True)
    duration = get_audio_duration(audio_path)

    # get accent color from channel
    accent_hex = channel.primary_color.lstrip("#")
    r = int(accent_hex[0:2], 16)
    g = int(accent_hex[2:4], 16)
    b = int(accent_hex[4:6], 16)

    # build text overlay filter
    words = thumbnail_text.upper().split()
    if len(words) <= 2:
        line1 = thumbnail_text.upper()
        line2 = ""
    else:
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])

    # FFmpeg filter for vertical short with text
    font_path = "assets/fonts/Roboto-Bold.ttf"

    if line2:
        text_filter = (
            f"drawtext=fontfile={font_path}:text='{line1}':"
            f"fontsize=120:fontcolor=white:x=(w-text_w)/2:y=(h/2)-150:"
            f"borderw=6:bordercolor=black,"
            f"drawtext=fontfile={font_path}:text='{line2}':"
            f"fontsize=120:fontcolor={channel.primary_color}:x=(w-text_w)/2:y=(h/2)+20:"
            f"borderw=6:bordercolor=black"
        )
    else:
        text_filter = (
            f"drawtext=fontfile={font_path}:text='{line1}':"
            f"fontsize=140:fontcolor=white:x=(w-text_w)/2:y=(h/2)-70:"
            f"borderw=6:bordercolor=black"
        )

    # channel name watermark
    watermark = f"@{channel.name}"
    text_filter += (
        f",drawtext=fontfile={font_path}:text='{watermark}':"
        f"fontsize=48:fontcolor=white@0.7:x=(w-text_w)/2:y=h-100"
    )

    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x{accent_hex[:2]}{accent_hex[2:4]}{accent_hex[4:]}@0.15:size=1080x1920:rate=30",
            "-i", audio_path,
            "-vf", text_filter,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-t", str(duration + 0.5),
            output_path,
        ], check=True, capture_output=True)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"  [shorts] Rendered: {Path(output_path).name} ({size_mb:.1f}MB, {duration:.0f}s)")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"  [shorts] Render error: {e.stderr.decode()[:200]}")
        # fallback: simple solid colour + audio
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:size=1080x1920:rate=30",
            "-i", audio_path,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path,
        ], check=True, capture_output=True)
        return output_path


def upload_short(
    channel: ChannelConfig,
    video_path: str,
    title: str,
    description: str,
    tags: list,
) -> str:
    """Upload a Short to YouTube. Returns video ID."""
    from modules.upload import get_youtube_client
    from googleapiclient.http import MediaFileUpload

    youtube = get_youtube_client(channel)

    # shorts description always includes #Shorts
    full_description = f"{description}\n\n#Shorts #shorts"

    body = {
        "snippet": {
            "title": title[:100],
            "description": full_description[:5000],
            "tags": tags + ["shorts"],
            "categoryId": "22",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,
    )

    print(f"  [shorts] Uploading '{title}'...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  [shorts] {int(status.progress() * 100)}% uploaded...", end="\r")

    video_id = response["id"]
    print(f"  [shorts] Upload complete: https://youtube.com/shorts/{video_id}")
    return video_id


def run_shorts_pipeline(
    channel: ChannelConfig,
    long_form_hook: str,
    long_form_title: str,
    target_keyword: str,
    output_dir: str,
    dry_run: bool = False,
) -> Optional[str]:
    """
    Full Shorts pipeline:
    1. Generate 60-second script from long-form hook
    2. Generate voiceover
    3. Render vertical video
    4. Upload to YouTube
    Returns video ID or None.
    """
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n  [shorts] Starting Shorts pipeline for: '{long_form_title}'")

    # 1. Script
    shorts_data = generate_shorts_script(
        channel, long_form_hook, long_form_title, target_keyword
    )
    print(f"  [shorts] Title: {shorts_data['title']}")

    if dry_run:
        print(f"\n  [shorts] DRY RUN — script only:")
        print(f"  Title: {shorts_data['title']}")
        print(f"  Script: {shorts_data['script'][:200]}...")
        return None

    # 2. Voiceover
    mp3_path = generate_shorts_voiceover(channel, shorts_data["script"], output_dir)

    # 3. Render vertical video
    video_path = os.path.join(output_dir, "short.mp4")
    render_shorts_video(
        audio_path=mp3_path,
        output_path=video_path,
        channel=channel,
        thumbnail_text=shorts_data["thumbnail_text"],
    )

    # 4. Upload
    video_id = upload_short(
        channel=channel,
        video_path=video_path,
        title=shorts_data["title"],
        description=shorts_data["description"],
        tags=shorts_data["tags"],
    )

    return video_id


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from config import CHANNEL_A

    run_shorts_pipeline(
        channel=CHANNEL_A,
        long_form_hook="Seventy-eight percent of Americans live paycheck to paycheck. Not because they don't earn enough, but because they never learned one fundamental skill: budgeting.",
        long_form_title="Budgeting for Beginners: 5 Steps to Your First Budget",
        target_keyword="budgeting for beginners",
        output_dir="temp/shorts_test",
        dry_run=True,
    )
