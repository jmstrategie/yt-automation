"""
modules/voiceover.py
Converts script text to MP3 using edge-tts (free) or ElevenLabs (premium).
Also generates an SRT subtitle file for burned-in captions.
"""

import asyncio
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

import edge_tts

from config import ChannelConfig, ELEVENLABS_API_KEY


# ── Edge TTS (free) ────────────────────────────────────────────────────────────

async def _edge_tts_generate(text: str, voice: str, output_path: str) -> None:
    """Async edge-tts call."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def generate_voiceover_free(
    text: str,
    voice: str,
    output_path: str,
) -> str:
    """Generate MP3 using edge-tts (Microsoft neural voices, completely free)."""
    print(f"  [voice] edge-tts → {Path(output_path).name} ({voice})")
    asyncio.run(_edge_tts_generate(text, voice, output_path))
    size_kb = os.path.getsize(output_path) // 1024
    print(f"  [voice] Done — {size_kb} KB")
    return output_path


# ── ElevenLabs (premium, better quality) ──────────────────────────────────────

def generate_voiceover_elevenlabs(
    text: str,
    voice_id: str,
    output_path: str,
) -> str:
    """Generate MP3 using ElevenLabs API. Requires ELEVENLABS_API_KEY."""
    from elevenlabs import ElevenLabs
    from elevenlabs.types import VoiceSettings

    print(f"  [voice] ElevenLabs → {Path(output_path).name}")
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

    audio_generator = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_turbo_v2",
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.75,
        ),
    )

    with open(output_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)

    size_kb = os.path.getsize(output_path) // 1024
    print(f"  [voice] Done — {size_kb} KB")
    return output_path


# ── SRT subtitle generation ───────────────────────────────────────────────────

def generate_srt(text: str, audio_path: str, srt_path: str) -> str:
    """
    Generate a basic SRT file by estimating word timing from audio duration.
    For production quality, swap this with Whisper transcription of the audio.
    """
    # get audio duration via ffprobe
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True,
    )
    duration = float(result.stdout.strip()) if result.returncode == 0 else 60.0

    # split text into ~6-word chunks
    words = text.split()
    chunk_size = 6
    chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

    if not chunks:
        return srt_path

    time_per_chunk = duration / len(chunks)

    def fmt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks):
            start = i * time_per_chunk
            end = start + time_per_chunk - 0.1
            f.write(f"{i+1}\n")
            f.write(f"{fmt_time(start)} --> {fmt_time(end)}\n")
            f.write(f"{chunk}\n\n")

    print(f"  [voice] SRT generated — {len(chunks)} subtitle blocks")
    return srt_path


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_voiceover(
    channel: ChannelConfig,
    text: str,
    output_dir: str,
    filename_base: str,
) -> tuple[str, str]:
    """
    Generate voiceover MP3 + SRT subtitle file.
    Returns (mp3_path, srt_path).
    Uses ElevenLabs if voice_id is set, otherwise edge-tts.
    """
    os.makedirs(output_dir, exist_ok=True)
    mp3_path = os.path.join(output_dir, f"{filename_base}.mp3")
    srt_path = os.path.join(output_dir, f"{filename_base}.srt")

    # clean text for TTS (remove markdown, double spaces)
    clean_text = re.sub(r"\*+", "", text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    if channel.elevenlabs_voice_id and ELEVENLABS_API_KEY:
        generate_voiceover_elevenlabs(clean_text, channel.elevenlabs_voice_id, mp3_path)
    else:
        generate_voiceover_free(clean_text, channel.voice, mp3_path)

    generate_srt(clean_text, mp3_path, srt_path)

    return mp3_path, srt_path


if __name__ == "__main__":
    from config import CHANNEL_A
    test_text = "Welcome to today's video. We're going to talk about how to save money fast. Let's dive in."
    mp3, srt = generate_voiceover(CHANNEL_A, test_text, "temp", "test_voice")
    print(f"MP3: {mp3}")
    print(f"SRT: {srt}")
