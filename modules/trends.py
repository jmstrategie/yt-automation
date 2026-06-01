"""
modules/trends.py
Scrapes RSS feeds + YouTube autocomplete for hot topics.
Uses VidIQ keyword data baked in as high-opportunity targets.
Tracks topic history via a local JSON file (persists between local runs).
"""

import feedparser
import json
import os
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import anthropic

from config import ChannelConfig, ANTHROPIC_API_KEY, CLAUDE_MODEL


# ── High-opportunity keywords from VidIQ research ─────────────────────────────
# Updated: May 2026 — sweet spot: volume >50K, competition <45
VIDIQ_KEYWORDS = {
    "personal_finance_ai": [
        # keyword, monthly_searches, competition_score
        ("budgeting for beginners", 128093, 31),
        ("budgeting", 190340, 36),
        ("saving money", 192675, 38),
        ("zero based budgeting", 28368, 26),
        ("frugal living", 113206, 41),
        ("how to save money", 254477, 48),
        ("budgeting tips", 39279, 41),
        ("personal finance tips", 218128, 46),
        ("ai personal finance", 13090, 32),
        ("chatgpt for finance", 5289, 20),
        ("how to make a budget", 22465, 24),
        ("money saving tips", 69409, 51),
    ],
    "dark_history": [
        ("dark history", 50000, 35),
        ("ancient mysteries", 80000, 40),
        ("lost civilizations", 60000, 38),
        ("historical mysteries", 45000, 32),
        ("untold history", 30000, 28),
        ("ancient secrets", 55000, 36),
        ("conspiracy history", 40000, 42),
        ("forgotten history", 35000, 30),
    ],
    "food_recipes": [
        ("meal prep", 500000, 55),
        ("easy dinner recipes", 300000, 48),
        ("5 ingredient meals", 150000, 35),
        ("high protein recipes", 200000, 42),
        ("budget meals", 120000, 38),
        ("air fryer recipes", 400000, 52),
    ],
}


def fetch_rss_headlines(feeds: List[str], max_age_days: int = 3) -> List[str]:
    """Pull recent headlines from RSS feed URLs."""
    headlines = []
    cutoff = datetime.now() - timedelta(days=max_age_days)

    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                if published and published < cutoff:
                    continue
                title = entry.get("title", "").strip()
                if title and len(title) > 10:
                    headlines.append(title)
        except Exception as e:
            print(f"  [trends] RSS error for {url}: {e}")

    return list(dict.fromkeys(headlines))


def fetch_youtube_autocomplete(keywords: List[str]) -> List[str]:
    """
    Get YouTube search autocomplete suggestions — free, no API key needed.
    Real YouTube search intent data.
    """
    suggestions = []
    for kw in keywords[:8]:
        try:
            url = "https://suggestqueries.google.com/complete/search"
            params = {"client": "youtube", "ds": "yt", "q": kw}
            r = requests.get(url, params=params, timeout=8)
            data = json.loads(r.text.split("(", 1)[1].rstrip(")"))
            for s in data[1]:
                if isinstance(s, list) and s:
                    suggestions.append(s[0])
                elif isinstance(s, str):
                    suggestions.append(s)
        except Exception:
            pass
        time.sleep(0.3)

    return list(dict.fromkeys(suggestions))[:30]


def fetch_google_trends(keywords: List[str], geo: str = "US") -> List[str]:
    """Get rising queries from Google Trends — graceful fallback on error."""
    rising = []
    try:
        from pytrends.request import TrendReq
        time.sleep(2)
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        sample = keywords[:5]
        pt.build_payload(sample, cat=0, timeframe="now 7-d", geo=geo)
        related = pt.related_queries()
        for kw in sample:
            if kw in related and related[kw]["rising"] is not None:
                for _, row in related[kw]["rising"].iterrows():
                    rising.append(str(row["query"]))
    except Exception as e:
        print(f"  [trends] Google Trends skipped: {e}")
    return rising[:20]


def get_high_opportunity_keywords(niche: str) -> str:
    """Format VidIQ keywords as a string for Claude's prompt."""
    keywords = VIDIQ_KEYWORDS.get(niche, [])
    if not keywords:
        return ""
    lines = []
    for kw, searches, comp in sorted(keywords, key=lambda x: x[1], reverse=True):
        opportunity = "⭐ LOW COMPETITION" if comp < 40 else "MEDIUM"
        lines.append(f"  - \"{kw}\" ({searches:,} searches/mo, competition {comp}/100) {opportunity}")
    return "\n".join(lines)


def rank_topics_with_claude(
    channel: ChannelConfig,
    headlines: List[str],
    trending: List[str],
    autocomplete: List[str],
    n: int = 5,
    recent_topics: List[str] = [],
) -> List[Dict]:
    """Ask Claude to pick the best video topics using all data sources."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    avoid_section = ""
    if recent_topics:
        avoid_section = f"""
RECENTLY PUBLISHED (DO NOT repeat or closely resemble):
{chr(10).join(f"- {t}" for t in recent_topics)}
"""

    keyword_section = get_high_opportunity_keywords(channel.niche)

    prompt = f"""You are a YouTube strategy expert for the "{channel.niche}" niche.

Pick the {n} best video topics that will rank well on YouTube and get views.

RSS HEADLINES (trending news):
{chr(10).join(f"- {h}" for h in headlines[:30])}

YOUTUBE AUTOCOMPLETE (what people actually search):
{chr(10).join(f"- {s}" for s in autocomplete[:20])}

HIGH-OPPORTUNITY KEYWORDS (VidIQ data — prioritise these):
{keyword_section}

CHANNEL SEED TOPICS:
{chr(10).join(f"- {t}" for t in channel.topics)}
{avoid_section}
RULES:
1. PRIORITISE topics that match the high-opportunity keywords above — these have proven search volume and low competition
2. Each topic must work as a faceless voiceover + stock footage video
3. Use specific numbers, years, or curiosity gaps in titles ("7 Ways...", "The Truth About...", "Why Nobody Talks About...")
4. If a topic suits a series ({channel.series_max_parts} parts max), mark is_series=true
5. Return ONLY a JSON array, no other text

JSON FORMAT:
[
  {{
    "title": "SEO-optimised title under 60 chars",
    "angle": "Unique angle in one sentence",
    "target_keyword": "primary keyword from the high-opportunity list",
    "is_series": false,
    "series_parts": 1,
    "series_titles": [],
    "keywords": ["kw1", "kw2", "kw3", "kw4", "kw5"]
  }}
]"""

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
    raw = raw.strip()

    return json.loads(raw)


def load_topic_history(channel: ChannelConfig) -> List[str]:
    """Load recent topic history from local file."""
    history_file = f"output/{channel.name}_topic_history.json"
    try:
        if os.path.exists(history_file):
            with open(history_file) as f:
                return json.load(f)[-20:]
    except Exception:
        pass
    return []


def save_topic_history(channel: ChannelConfig, topic_title: str) -> None:
    """Save a topic to history file."""
    history_file = f"output/{channel.name}_topic_history.json"
    try:
        os.makedirs("output", exist_ok=True)
        existing = load_topic_history(channel)
        existing.append(topic_title)
        with open(history_file, "w") as f:
            json.dump(existing[-30:], f, indent=2)
    except Exception as e:
        print(f"  [trends] Could not save topic history: {e}")


def get_topics_for_channel(channel: ChannelConfig, n: int = 5) -> List[Dict]:
    """Full pipeline: RSS + Autocomplete + Trends → Claude ranking."""
    print(f"\n[trends] Fetching topics for {channel.name}...")

    headlines = fetch_rss_headlines(channel.rss_feeds)
    print(f"  {len(headlines)} headlines from RSS")

    autocomplete = fetch_youtube_autocomplete(channel.topics[:6])
    print(f"  {len(autocomplete)} YouTube autocomplete suggestions")

    trending = fetch_google_trends(channel.topics)
    print(f"  {len(trending)} Google Trends queries")

    recent_topics = load_topic_history(channel)
    if recent_topics:
        print(f"  Avoiding {len(recent_topics)} recent topics")

    topics = rank_topics_with_claude(
        channel, headlines,
        trending + autocomplete,
        autocomplete,
        n=n,
        recent_topics=recent_topics,
    )

    print(f"  Claude selected {len(topics)} topics:")
    for i, t in enumerate(topics):
        kw = t.get("target_keyword", "")
        series_note = f" [SERIES x{t['series_parts']}]" if t.get("is_series") else ""
        print(f"  {i+1}. {t['title']}{series_note} → targeting: {kw}")

    if topics:
        save_topic_history(channel, topics[0]["title"])

    return topics


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from config import CHANNEL_A
    topics = get_topics_for_channel(CHANNEL_A, n=3)
    print(json.dumps(topics, indent=2))