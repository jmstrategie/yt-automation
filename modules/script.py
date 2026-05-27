"""
modules/script.py
Uses Claude to write full video scripts with hook, body, and CTA.
Handles both standalone videos and multi-part series.
"""

import json
import anthropic
from dataclasses import dataclass
from typing import List, Optional

from config import ChannelConfig, ANTHROPIC_API_KEY, CLAUDE_MODEL


@dataclass
class VideoScript:
    title: str
    description: str          # YouTube description (SEO optimised)
    tags: List[str]           # YouTube tags
    hook: str                 # first 30 seconds — must grab attention
    body: str                 # main content
    cta: str                  # call to action / outro
    full_text: str            # hook + body + cta combined for TTS
    part: int = 1             # 1 for standalone, 1/2/3 for series
    total_parts: int = 1
    series_title: Optional[str] = None
    thumbnail_text: str = ""  # bold text overlay on thumbnail (max 5 words)


FINANCE_SCRIPT_PROMPT = """You are a top YouTube scriptwriter for a faceless finance and AI channel.
Write an engaging, educational script for the following video.

VIDEO TITLE: {title}
ANGLE: {angle}
PART: {part} of {total_parts}
TARGET LENGTH: {min_sec}–{max_sec} seconds of spoken audio (approx {min_words}–{max_words} words)

SCRIPT RULES:
- Open with a powerful hook (a surprising stat, bold claim, or relatable problem) — first 3 sentences must grab attention
- No filler phrases: never say "In this video I will...", "Don't forget to like and subscribe"
- Write for a neutral American voice — short sentences, conversational but authoritative
- Use real numbers, examples, and analogies to explain complex ideas simply
- No on-camera references (no "as you can see", "I'm holding", "look at this chart")
- End with a clear, specific CTA related to the topic (not generic subscribe begging)
- If this is part {part} of {total_parts}, briefly recap the previous part's key point (if part > 1) and tease the next part at the end

Return ONLY valid JSON, no markdown fences:
{{
  "title": "Final YouTube title (under 60 chars, SEO optimised)",
  "description": "YouTube description (150–200 words, includes keywords naturally, ends with relevant links placeholder)",
  "tags": ["tag1", "tag2", ...],
  "hook": "First 30 seconds of script",
  "body": "Main body of script",
  "cta": "Closing 20–30 seconds",
  "thumbnail_text": "3–5 bold words for thumbnail overlay"
}}"""


FOOD_SCRIPT_PROMPT = """You are a top YouTube scriptwriter for a faceless recipe and cooking channel.
Write an engaging, warm, practical script for the following video.

VIDEO TITLE: {title}
ANGLE: {angle}
PART: {part} of {total_parts}
TARGET LENGTH: {min_sec}–{max_sec} seconds of spoken audio (approx {min_words}–{max_words} words)

SCRIPT RULES:
- Open by immediately naming the problem the viewer has (e.g. "You get home at 7pm, exhausted, and you still need to cook dinner")
- No filler phrases or generic intros
- Write for a warm, friendly female American voice — encouraging, enthusiastic, clear
- Give step-by-step instructions in natural spoken language (not bullet points)
- Include ingredient amounts naturally in speech ("two tablespoons of olive oil")
- No on-camera references — this is a voiceover over stock footage
- End with a tip, variation, or meal-prep suggestion as the CTA

Return ONLY valid JSON, no markdown fences:
{{
  "title": "Final YouTube title (under 60 chars, SEO optimised)",
  "description": "YouTube description (150–200 words, appetising, includes keywords naturally)",
  "tags": ["tag1", "tag2", ...],
  "hook": "First 30 seconds of script",
  "body": "Main body of script (full recipe walkthrough)",
  "cta": "Closing 20–30 seconds (tip or variation)",
  "thumbnail_text": "3–5 bold words for thumbnail overlay"
}}"""


def _words_from_seconds(sec: int) -> int:
    """Average speaking pace: ~140 words per minute."""
    return int(sec * 140 / 60)


def generate_script(
    channel: ChannelConfig,
    topic: dict,
    part: int = 1,
    total_parts: int = 1,
) -> VideoScript:
    """Generate a full video script for a given topic dict."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    title = topic["series_titles"][part - 1] if topic.get("is_series") and topic.get("series_titles") else topic["title"]
    angle = topic.get("angle", "")

    min_words = _words_from_seconds(channel.min_video_length_sec)
    max_words = _words_from_seconds(channel.max_video_length_sec)

    prompt_template = FOOD_SCRIPT_PROMPT if channel.thumbnail_style == "food" else FINANCE_SCRIPT_PROMPT

    prompt = prompt_template.format(
        title=title,
        angle=angle,
        part=part,
        total_parts=total_parts,
        min_sec=channel.min_video_length_sec,
        max_sec=channel.max_video_length_sec,
        min_words=min_words,
        max_words=max_words,
    )

    print(f"  [script] Generating script: '{title}' (part {part}/{total_parts})...")

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)

    full_text = f"{data['hook']}\n\n{data['body']}\n\n{data['cta']}"

    script = VideoScript(
        title=data["title"],
        description=data["description"],
        tags=data.get("tags", topic.get("keywords", [])),
        hook=data["hook"],
        body=data["body"],
        cta=data["cta"],
        full_text=full_text,
        part=part,
        total_parts=total_parts,
        series_title=topic["title"] if topic.get("is_series") else None,
        thumbnail_text=data.get("thumbnail_text", title[:30]),
    )

    word_count = len(full_text.split())
    print(f"  [script] Done — {word_count} words (~{word_count * 60 // 140} seconds)")

    return script


def generate_series_scripts(channel: ChannelConfig, topic: dict) -> List[VideoScript]:
    """Generate all parts of a series topic."""
    parts = topic.get("series_parts", 1)
    scripts = []
    for part_num in range(1, parts + 1):
        script = generate_script(channel, topic, part=part_num, total_parts=parts)
        scripts.append(script)
    return scripts


if __name__ == "__main__":
    from config import CHANNEL_A
    test_topic = {
        "title": "How to Save $1000 in 30 Days",
        "angle": "A practical day-by-day challenge with real tactics",
        "is_series": False,
        "series_parts": 1,
        "series_titles": [],
        "keywords": ["save money", "budgeting", "personal finance", "money challenge"],
    }
    script = generate_script(CHANNEL_A, test_topic)
    print(f"\nTitle: {script.title}")
    print(f"Thumbnail text: {script.thumbnail_text}")
    print(f"\nHOOK:\n{script.hook[:200]}...")
