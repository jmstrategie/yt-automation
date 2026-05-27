"""
modules/trends.py
Scrapes RSS feeds and Google Trends to surface hot topics for each channel.
Returns a ranked list of topic strings ready to feed into Claude.
"""

import feedparser
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict
from pytrends.request import TrendReq
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
                # parse publish date if available
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

    return list(dict.fromkeys(headlines))  # deduplicate, preserve order


def fetch_google_trends(keywords: List[str], geo: str = "US") -> List[str]:
    """Get related rising queries from Google Trends for seed keywords."""
    rising = []
    try:
        pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        # sample up to 5 seed keywords (Trends API limit)
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
) -> List[Dict]:
    """
    Ask Claude to pick the best video topics from raw headlines + trends.
    Returns a list of dicts:
      { title, angle, is_series, series_parts, series_titles, keywords }
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are a YouTube strategy expert specialising in the "{channel.niche}" niche.

Below are recent headlines and trending searches. Your job is to pick the {n} best YouTube video topics from them — or invent closely related evergreen topics if the headlines aren't strong enough.

HEADLINES:
{chr(10).join(f"- {h}" for h in headlines[:40])}

TRENDING SEARCHES:
{chr(10).join(f"- {t}" for t in trending[:20])}

CHANNEL SEED TOPICS (always relevant):
{chr(10).join(f"- {t}" for t in channel.topics)}

RULES:
1. Prioritise evergreen topics over pure news (unless the news is huge).
2. Each topic must work as a faceless voiceover + stock footage video.
3. If a topic is deep enough for a series ({"enabled" if channel.series_enabled else "disabled"} for this channel), mark is_series=true and provide {channel.series_max_parts} part titles.
4. Return ONLY a JSON array, no other text.

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
    # strip markdown code fences if present
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

    topics = rank_topics_with_claude(channel, headlines, trending, n=n)
    print(f"  Claude selected {len(topics)} topics")

    for i, t in enumerate(topics):
        series_note = f" [SERIES x{t['series_parts']}]" if t.get("is_series") else ""
        print(f"  {i+1}. {t['title']}{series_note}")

    return topics


if __name__ == "__main__":
    # quick test
    from config import CHANNEL_A
    topics = get_topics_for_channel(CHANNEL_A, n=3)
    print(json.dumps(topics, indent=2))
