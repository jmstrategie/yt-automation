"""
modules/trends.py
Scrapes RSS feeds and Google Trends to surface hot topics for each channel.
Tracks topic history to avoid repeating recent subjects.
Returns a ranked list of topic dicts ready to feed into Claude.
"""

import feedparser
import json
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict
import anthropic

from config import ChannelConfig, ANTHROPIC_API_KEY, CLAUDE_MODEL


def fetch_rss_headlines(feeds: List[str], max_age_days: int = 3) -> List[str]:
    """Pull recent headlines from a list of RSS feed URLs."""
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


def fetch_google_trends(keywords: List[str], geo: str = "US") -> List[str]:
    """Get related rising queries from Google Trends for seed keywords."""
    rising = []
    try:
        from pytrends.request import TrendReq
        time.sleep(2)  # avoid 429 rate limit
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25), retries=1, backoff_factor=0.5)
        sample = keywords[:5]
        pt.build_payload(sample, cat=0, timeframe="now 7-d", geo=geo)
        related = pt.related_queries()
        for kw in sample:
            if kw in related and related[kw]["rising"] is not None:
                for _, row in related[kw]["rising"].iterrows():
                    rising.append(str(row["query"]))
    except Exception as e:
        print(f"  [trends] Google Trends error: {e}")
    return rising[:20]


def rank_topics_with_claude(
    channel: ChannelConfig,
    headlines: List[str],
    trending: List[str],
    n: int = 5,
    recent_topics: List[str] = [],
) -> List[Dict]:
    """
    Ask Claude to pick the best video topics from raw headlines + trends.
    Avoids recently used topics.
    Returns a list of dicts:
      { title, angle, is_series, series_parts, series_titles, keywords }
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    avoid_section = ""
    if recent_topics:
        avoid_section = f"""
RECENTLY PUBLISHED TOPICS (DO NOT repeat or closely resemble any of these):
{chr(10).join(f"- {t}" for t in recent_topics)}
"""

    prompt = f"""You are a YouTube strategy expert specialising in the "{channel.niche}" niche.

Below are recent headlines and trending searches. Your job is to pick the {n} best YouTube video topics — fully different from recently published ones.

HEADLINES:
{chr(10).join(f"- {h}" for h in headlines[:40])}

TRENDING SEARCHES:
{chr(10).join(f"- {t}" for t in trending[:20])}

CHANNEL SEED TOPICS (always relevant):
{chr(10).join(f"- {t}" for t in channel.topics)}
{avoid_section}
RULES:
1. Prioritise evergreen topics over pure news (unless the news is huge).
2. Each topic must work as a faceless voiceover + stock footage video.
3. NEVER pick a topic similar to the recently published list above.
4. Vary the topics — different subtopics, different angles, different formats.
5. If a topic is deep enough for a series ({"enabled" if channel.series_enabled else "disabled"} for this channel), mark is_series=true and provide {channel.series_max_parts} part titles.
6. Return ONLY a JSON array, no other text.

JSON FORMAT:
[
  {{
    "title": "Short punchy video title (under 60 chars)",
    "angle": "One sentence describing the unique angle",
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

    topics = json.loads(raw)
    return topics


def get_topics_for_channel(channel: ChannelConfig, n: int = 5) -> List[Dict]:
    """Full pipeline: RSS → Trends → Claude ranking. Returns n topics."""
    print(f"\n[trends] Fetching topics for {channel.name}...")

    headlines = fetch_rss_headlines(channel.rss_feeds)
    print(f"  {len(headlines)} headlines collected")

    trending = fetch_google_trends(channel.topics)
    print(f"  {len(trending)} trending queries collected")

    # load recent topic history to avoid repetition
    history_file = f"output/{channel.name}_topic_history.json"
    recent_topics = []
    try:
        if os.path.exists(history_file):
            with open(history_file) as f:
                recent_topics = json.load(f)[-20:]  # last 20 topics
    except Exception:
        pass

    if recent_topics:
        print(f"  Avoiding {len(recent_topics)} recent topics")

    topics = rank_topics_with_claude(
        channel, headlines, trending, n=n, recent_topics=recent_topics
    )
    print(f"  Claude selected {len(topics)} topics")

    # save top topic to history
    try:
        os.makedirs("output", exist_ok=True)
        history = recent_topics + [topics[0]["title"]] if topics else recent_topics
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass

    for i, t in enumerate(topics):
        series_note = f" [SERIES x{t['series_parts']}]" if t.get("is_series") else ""
        print(f"  {i+1}. {t['title']}{series_note}")

    return topics


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from config import CHANNEL_A
    topics = get_topics_for_channel(CHANNEL_A, n=3)
    print(json.dumps(topics, indent=2))