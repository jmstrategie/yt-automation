"""
YouTube Automation — Channel Configuration
Edit this file to control both channels, voices, schedules, and niches.
API keys are loaded from environment variables (GitHub Secrets / .env file).
"""

import os
from dataclasses import dataclass, field
from typing import List

# ── API Keys (never hardcode these) ──────────────────────────────────────────
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")   # optional
OPENAI_API_KEY      = os.environ.get("OPENAI_API_KEY", "")       # for DALL-E thumbnails (optional)

# ── Model ─────────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-5"

# ── Channel Definitions ───────────────────────────────────────────────────────
@dataclass
class ChannelConfig:
    name: str
    channel_id: str                  # YouTube channel ID
    secrets_file: str                # path to OAuth client_secrets JSON
    token_file: str                  # where to cache the OAuth token
    niche: str                       # short niche label
    topics: List[str]                # seed topics for Claude
    rss_feeds: List[str]             # RSS feeds to monitor for trends
    voice: str                       # edge-tts voice name
    elevenlabs_voice_id: str         # ElevenLabs voice ID (if used)
    thumbnail_style: str             # "finance" | "food"
    primary_color: str               # hex — thumbnail accent colour
    upload_schedule: str             # cron expression (UTC)
    videos_per_week: int
    series_enabled: bool             # whether to detect & create series
    series_max_parts: int            # max parts in a series (2 or 3)
    min_video_length_sec: int        # target minimum audio length
    max_video_length_sec: int

CHANNEL_A = ChannelConfig(
    name                = "WealthWhale",
    channel_id          = "UCoPwmRtesRrED9WKTtFU1Cg",
    secrets_file        = "secrets/client_secrets_channelA.json",
    token_file          = "secrets/token_channelA.json",
    niche               = "personal_finance_ai",
    topics              = [
        "personal finance", "budgeting", "investing for beginners",
        "AI tools", "ChatGPT", "Claude AI", "automation",
        "credit cards", "saving money", "passive income",
        "stock market", "ETFs", "financial freedom",
        "AI news", "machine learning explained",
    ],
    rss_feeds           = [
        "https://feeds.feedburner.com/PocketNow",
        "https://www.theverge.com/rss/index.xml",
        "https://techcrunch.com/feed/",
        "https://feeds.a.dj.com/rss/RSSPersonalFinance.xml",
        "https://www.reddit.com/r/personalfinance/.rss",
        "https://www.reddit.com/r/artificial/.rss",
    ],
    voice               = "en-US-GuyNeural",        # free edge-tts
    elevenlabs_voice_id = "ZT9u07TYPVl83ejeLakq",                        # add if upgrading
    thumbnail_style     = "finance",
    primary_color       = "#1DB954",                 # green
    upload_schedule     = "0 14 * * 1,3,5",         # Mon/Wed/Fri 2pm UTC
    videos_per_week     = 4,
    series_enabled      = True,
    series_max_parts    = 3,
    min_video_length_sec = 360,                      # 6 min
    max_video_length_sec = 600,                      # 10 min
)

CHANNEL_B = ChannelConfig(
    name                = "ChuckysUntoldStories",
    channel_id          = "UCffQwNxThKwuaBkV16j6b3g",
    secrets_file        = "secrets/client_secrets_channelB.json",
    token_file          = "secrets/token_channelB.json",
    niche               = "dark_history",
    topics              = [
        "dark history", "ancient mysteries", "lost civilizations",
        "historical cover-ups", "forgotten empires", "ancient secrets",
        "untold history", "historical mysteries", "ancient discoveries",
        "dark secrets history", "hidden history", "conspiracy history",
        "ancient civilizations", "historical dark facts", "unsolved mysteries",
    ],
    rss_feeds           = [
        "https://www.history.com/feeds/articles",
        "https://www.ancient-origins.net/rss.xml",
        "https://www.livescience.com/feeds/all",
        "https://www.smithsonianmag.com/rss/history-archaeology/",
        "https://www.reddit.com/r/history/.rss",
        "https://www.reddit.com/r/UnresolvedMysteries/.rss",
        "https://www.reddit.com/r/AncientCivilizations/.rss",
    ],
    voice               = "en-US-GuyNeural",
    elevenlabs_voice_id = "",
    thumbnail_style     = "dark_history",
    primary_color       = "#8B0000",
    upload_schedule     = "0 16 * * 2,4,6",
    videos_per_week     = 3,
    series_enabled      = True,
    series_max_parts    = 3,
    min_video_length_sec = 480,
    max_video_length_sec = 720,
)

ALL_CHANNELS = [CHANNEL_A, CHANNEL_B]

# ── Video / Render Settings ───────────────────────────────────────────────────
VIDEO_WIDTH   = 1920
VIDEO_HEIGHT  = 1080
VIDEO_FPS     = 30
VIDEO_BITRATE = "4000k"
AUDIO_BITRATE = "192k"

# ── Thumbnail Settings ────────────────────────────────────────────────────────
THUMB_WIDTH  = 1280
THUMB_HEIGHT = 720
THUMB_FONT   = "assets/fonts/Roboto-Bold.ttf"   # downloaded at setup

# ── B-roll Sources (free APIs) ────────────────────────────────────────────────
PEXELS_API_KEY  = os.environ.get("PEXELS_API_KEY", "")   # free at pexels.com/api
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY", "")  # free at pixabay.com/api

# ── Paths ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR  = "output"
TEMP_DIR    = "temp"
SECRETS_DIR = "secrets"
