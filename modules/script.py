"""
modules/script.py
Uses Claude to write full video scripts with hook, body, and CTA.
Handles both standalone videos and multi-part series.
Generates SEO-optimised descriptions with chapter markers and consistent footer.
Supports niches: personal_finance_ai, food_recipes, dark_history, horror_fiction
"""

import json
import anthropic
from dataclasses import dataclass, field
from typing import List, Optional

from config import ChannelConfig, ANTHROPIC_API_KEY, CLAUDE_MODEL


@dataclass
class VideoScript:
    title: str
    description: str
    tags: List[str]
    hook: str
    body: str
    cta: str
    full_text: str
    chapters: List[dict]
    part: int = 1
    total_parts: int = 1
    series_title: Optional[str] = None
    thumbnail_text: str = ""


# ── Channel footers ────────────────────────────────────────────────────────────

CHANNEL_FOOTERS = {
    "personal_finance_ai": """
─────────────────────────────
🐋 WEALTH WHALE — AI-Powered Personal Finance
New videos every Monday, Wednesday & Friday

📌 SUBSCRIBE for weekly finance & AI tips:
https://www.youtube.com/@thewealthwhale

🔔 Turn on notifications so you never miss a video

─────────────────────────────
DISCLAIMER: This video is for educational purposes only and does not constitute financial advice. Always consult a qualified financial advisor before making investment decisions.
─────────────────────────────
#PersonalFinance #MoneyTips #FinancialFreedom #WealthWhale #Budgeting #Investing #AITools #MoneyManagement #SaveMoney #FinanceTips
""",
    "dark_history": """
─────────────────────────────
💀 CHUCKY'S UNTOLD STORIES — Dark History & Ancient Mysteries
New videos every Tuesday, Thursday & Saturday

📌 SUBSCRIBE for weekly untold stories:
https://www.youtube.com/@ChuckysUntoldStories

🔔 Turn on notifications — history's darkest secrets await

─────────────────────────────
DISCLAIMER: Content is for educational and entertainment purposes only.
─────────────────────────────
#DarkHistory #AncientMysteries #UntoldStories #History #Mysteries #LostCivilizations #HistoricalFacts #AncientSecrets
""",
    "horror_fiction": """
─────────────────────────────
💀 CHUCKY'S UNTOLD STORIES — Horror Fiction & Cursed Tales
New videos every Tuesday, Thursday & Saturday

📌 SUBSCRIBE for weekly horror stories:
https://www.youtube.com/@ChuckysUntoldStories

🔔 Turn on notifications — if you dare

─────────────────────────────
DISCLAIMER: All stories are fictional and created for entertainment purposes only. Any resemblance to real events or persons is purely coincidental.
─────────────────────────────
#HorrorStory #ScaryStory #CursedDoll #HorrorFiction #CreepyStory #HauntedDoll #HorrorNarration #ScaryTales #CreepyPasta #HorrorChannel
""",
}


# ── Script prompts ─────────────────────────────────────────────────────────────

FINANCE_SCRIPT_PROMPT = """You are a top YouTube scriptwriter for a faceless finance and AI channel.
Write an engaging, educational script for the following video.

VIDEO TITLE: {title}
TARGET KEYWORD: {target_keyword}
ANGLE: {angle}
PART: {part} of {total_parts}
TARGET LENGTH: {min_sec}–{max_sec} seconds of spoken audio (approx {min_words}–{max_words} words)

SCRIPT RULES:
- Open with a powerful hook — a surprising stat, bold claim, or relatable problem. First 3 sentences must grab attention immediately.
- Include the target keyword naturally in the first 30 seconds
- No filler phrases: never say "In this video I will...", "Don't forget to like and subscribe"
- Write for a neutral American voice — short sentences, conversational but authoritative
- Use real numbers, examples, and analogies to make complex ideas simple
- No on-camera references ("as you can see", "I'm holding", "look at this chart")
- Structure the body in 4-6 clear sections with distinct topic shifts (these become chapter markers)
- End with a specific, actionable CTA — not generic subscribe begging
- If part {part} of {total_parts}, briefly recap previous part (if part > 1) and tease next part at end
- IMPORTANT: Write the FULL script — minimum {min_words} words, target {max_words} words

Return ONLY valid JSON, no markdown fences:
{{
  "title": "Final YouTube title (under 60 chars, includes target keyword)",
  "hook": "First 30 seconds of script — at least 80 words",
  "body_sections": [
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}},
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}},
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}},
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}},
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}}
  ],
  "cta": "Closing 30-40 seconds — at least 80 words",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "thumbnail_text": "3-5 bold words for thumbnail overlay",
  "seo_description_intro": "First 150 chars of description — must include target keyword naturally and hook the reader"
}}"""


FOOD_SCRIPT_PROMPT = """You are a top YouTube scriptwriter for a faceless recipe and cooking channel.
Write an engaging, warm, practical script for the following video.

VIDEO TITLE: {title}
TARGET KEYWORD: {target_keyword}
ANGLE: {angle}
PART: {part} of {total_parts}
TARGET LENGTH: {min_sec}–{max_sec} seconds of spoken audio (approx {min_words}–{max_words} words)

SCRIPT RULES:
- Open by immediately naming the problem the viewer has
- No filler phrases or generic intros
- Write for a warm, friendly female American voice — encouraging, enthusiastic, clear
- Give step-by-step instructions in natural spoken language
- Include ingredient amounts naturally in speech
- No on-camera references — voiceover over stock footage
- Structure in 4-5 clear sections (intro, ingredients, steps, tips, outro)
- End with a tip, variation, or meal-prep suggestion
- IMPORTANT: Write the FULL script — minimum {min_words} words, target {max_words} words

Return ONLY valid JSON, no markdown fences:
{{
  "title": "Final YouTube title (under 60 chars, includes target keyword)",
  "hook": "First 30 seconds — at least 80 words",
  "body_sections": [
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}},
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}},
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}},
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}}
  ],
  "cta": "Closing 30 seconds — at least 60 words",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "thumbnail_text": "3-5 bold words for thumbnail overlay",
  "seo_description_intro": "First 150 chars — must include target keyword and hook the reader"
}}"""


DARK_HISTORY_SCRIPT_PROMPT = """You are a top YouTube scriptwriter for a dark history and ancient mysteries channel.
Write a compelling, suspenseful script for the following video.

VIDEO TITLE: {title}
TARGET KEYWORD: {target_keyword}
ANGLE: {angle}
PART: {part} of {total_parts}
TARGET LENGTH: {min_sec}–{max_sec} seconds of spoken audio (approx {min_words}–{max_words} words)

SCRIPT RULES:
- Open with a shocking, mysterious, or disturbing fact that most people don't know
- Build tension and curiosity throughout — use cliffhangers between sections
- Write for a deep, measured male American voice — serious, authoritative, slightly ominous
- Reference real historical sources, dates, and locations for credibility
- No on-camera references — pure voiceover narration
- Structure in 4-6 sections that build on each other dramatically
- End with a thought-provoking question or revelation that seeds the next video
- IMPORTANT: Write the FULL script — minimum {min_words} words, target {max_words} words

Return ONLY valid JSON, no markdown fences:
{{
  "title": "Final YouTube title (under 60 chars, includes target keyword)",
  "hook": "First 30 seconds — shocking opening fact or mystery — at least 80 words",
  "body_sections": [
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}},
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}},
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}},
    {{"section_title": "Short chapter name", "content": "Full section content — at least 150 words each"}}
  ],
  "cta": "Closing 30 seconds — revelation + tease next video — at least 60 words",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "thumbnail_text": "3-5 bold mysterious words for thumbnail",
  "seo_description_intro": "First 150 chars — mysterious hook that includes target keyword"
}}"""


HORROR_FICTION_SCRIPT_PROMPT = """You are a master horror storyteller writing scripts for a YouTube horror channel featuring cursed dolls and dark fiction.
Write a spine-chilling, atmospheric horror story script.

VIDEO TITLE: {title}
TARGET KEYWORD: {target_keyword}
ANGLE: {angle}
PART: {part} of {total_parts}
TARGET LENGTH: {min_sec}–{max_sec} seconds of spoken audio (approx {min_words}–{max_words} words)

SCRIPT RULES:
- Open with a shocking, specific detail that immediately creates dread — a date, a location, a strange event
- Build tension slowly — use pauses in pacing, repetition, and vivid sensory details (sounds, smells, textures, cold)
- Write for a deep, slow, measured male voice — deliberate pacing, ominous and hypnotic tone
- Blend fiction with real-sounding details (fake names, addresses, dates) to feel authentic and credible
- No on-camera references — pure atmospheric narration throughout
- Structure in 5-6 sections that escalate in dread and horror
- Each section must end on a disturbing revelation or cliffhanger that compels listening
- End with an unresolved question or shocking twist that seeds curiosity for the next video
- Never break the horror atmosphere — no humor, no lighthearted moments whatsoever
- IMPORTANT: Write the FULL script — minimum {min_words} words, target {max_words} words. This is critical.

Return ONLY valid JSON, no markdown fences:
{{
  "title": "Final YouTube title (under 60 chars, mysterious and compelling)",
  "hook": "First 30 seconds — shocking opening that creates immediate dread — minimum 100 words",
  "body_sections": [
    {{"section_title": "Short ominous chapter name", "content": "Full horror section — minimum 200 words each"}},
    {{"section_title": "Short ominous chapter name", "content": "Full horror section — minimum 200 words each"}},
    {{"section_title": "Short ominous chapter name", "content": "Full horror section — minimum 200 words each"}},
    {{"section_title": "Short ominous chapter name", "content": "Full horror section — minimum 200 words each"}},
    {{"section_title": "Short ominous chapter name", "content": "Full horror section — minimum 200 words each"}}
  ],
  "cta": "Closing 30-40 seconds — unsettling revelation that teases next story — minimum 80 words",
  "tags": ["horror story", "scary story", "cursed doll", "horror fiction", "creepy story", "haunted doll", "scary tales", "horror narration"],
  "thumbnail_text": "3-5 ominous words for thumbnail",
  "seo_description_intro": "First 150 chars — mysterious hook that draws viewers in, includes target keyword"
}}"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _words_from_seconds(sec: int) -> int:
    return int(sec * 140 / 60)


def _estimate_chapter_timestamps(hook: str, sections: List[dict], cta: str) -> List[dict]:
    chapters = [{"title": "Introduction", "seconds": 0}]
    words_so_far = len(hook.split())
    for section in sections:
        seconds = int(words_so_far / 140 * 60)
        chapters.append({"title": section["section_title"], "seconds": seconds})
        words_so_far += len(section["content"].split())
    cta_seconds = int(words_so_far / 140 * 60)
    chapters.append({"title": "Final Thoughts", "seconds": cta_seconds})
    return chapters


def _format_timestamp(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"


def _build_description(
    seo_intro: str,
    chapters: List[dict],
    niche: str,
    title: str,
    target_keyword: str,
) -> str:
    chapter_lines = [f"{_format_timestamp(ch['seconds'])} {ch['title']}" for ch in chapters]
    footer = CHANNEL_FOOTERS.get(niche, CHANNEL_FOOTERS["personal_finance_ai"])

    if niche == "horror_fiction":
        middle = f"Tonight's story explores the terrifying world of {target_keyword}. What you're about to hear has been documented, witnessed, and cannot be explained."
    else:
        middle = f"In this video, we break down everything you need to know about {target_keyword} in a clear, practical way — no fluff, no jargon."

    description = f"""{seo_intro}

📌 CHAPTERS:
{chr(10).join(chapter_lines)}

{middle}
{footer}"""

    return description.strip()


# ── Main script generator ──────────────────────────────────────────────────────

def generate_script(
    channel: ChannelConfig,
    topic: dict,
    part: int = 1,
    total_parts: int = 1,
) -> VideoScript:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    title = topic["series_titles"][part - 1] if topic.get("is_series") and topic.get("series_titles") else topic["title"]
    angle = topic.get("angle", "")
    target_keyword = topic.get("target_keyword", topic.get("keywords", [""])[0])

    min_words = _words_from_seconds(channel.min_video_length_sec)
    max_words = _words_from_seconds(channel.max_video_length_sec)

    if channel.niche == "food_recipes":
        prompt_template = FOOD_SCRIPT_PROMPT
    elif channel.niche == "dark_history":
        prompt_template = DARK_HISTORY_SCRIPT_PROMPT
    elif channel.niche == "horror_fiction":
        prompt_template = HORROR_FICTION_SCRIPT_PROMPT
    else:
        prompt_template = FINANCE_SCRIPT_PROMPT

    prompt = prompt_template.format(
        title=title,
        target_keyword=target_keyword,
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
        max_tokens=5000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)

    body_text = "\n\n".join(s["content"] for s in data["body_sections"])
    full_text = f"{data['hook']}\n\n{body_text}\n\n{data['cta']}"

    chapters = _estimate_chapter_timestamps(data["hook"], data["body_sections"], data["cta"])

    description = _build_description(
        seo_intro=data.get("seo_description_intro", title),
        chapters=chapters,
        niche=channel.niche,
        title=data["title"],
        target_keyword=target_keyword,
    )

    script = VideoScript(
        title=data["title"],
        description=description,
        tags=data.get("tags", topic.get("keywords", [])),
        hook=data["hook"],
        body=body_text,
        cta=data["cta"],
        full_text=full_text,
        chapters=chapters,
        part=part,
        total_parts=total_parts,
        series_title=topic["title"] if topic.get("is_series") else None,
        thumbnail_text=data.get("thumbnail_text", title[:30]),
    )

    word_count = len(full_text.split())
    print(f"  [script] Done — {word_count} words (~{word_count * 60 // 140}s) | {len(chapters)} chapters")

    return script


def generate_series_scripts(channel: ChannelConfig, topic: dict) -> List[VideoScript]:
    parts = topic.get("series_parts", 1)
    scripts = []
    for part_num in range(1, parts + 1):
        script = generate_script(channel, topic, part=part_num, total_parts=parts)
        scripts.append(script)
    return scripts


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from config import CHANNEL_B
    test_topic = {
        "title": "7 Cursed Dolls That Ruined Their Owners Lives",
        "angle": "Documented cases of cursed dolls with witnesses and evidence",
        "target_keyword": "cursed doll",
        "is_series": False,
        "series_parts": 1,
        "series_titles": [],
        "keywords": ["cursed doll", "haunted doll", "horror story", "scary story"],
    }
    script = generate_script(CHANNEL_B, test_topic)
    print(f"\nTitle: {script.title}")
    print(f"Word count: {len(script.full_text.split())}")
    print(f"Chapters: {script.chapters}")