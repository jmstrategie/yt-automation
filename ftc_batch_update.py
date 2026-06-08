"""
ftc_batch_update.py
Batch adds FTC disclosure to all existing video descriptions on both channels.
Run once: python3 ftc_batch_update.py
YouTube requires AI-generated content disclosure under 2025 FTC rules.
Penalty: $53,088 per violation.
"""

import os
import pickle
from dotenv import load_dotenv
load_dotenv()

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

FTC_DISCLOSURE = """
─────────────────────────────
⚠️ DISCLOSURE: This video was produced with AI assistance including AI-generated script, voiceover, and visuals. All information is reviewed for accuracy but does not constitute financial advice.
─────────────────────────────"""


def get_youtube_client(token_file: str, secrets_file: str):
    """Get authenticated YouTube client."""
    creds = None
    if os.path.exists(token_file):
        with open(token_file, "rb") as f:
            creds = pickle.load(f)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def add_ftc_to_channel(token_file: str, secrets_file: str, channel_name: str):
    """Add FTC disclosure to all videos on a channel."""
    print(f"\n📋 Processing {channel_name}...")

    try:
        youtube = get_youtube_client(token_file, secrets_file)
    except Exception as e:
        print(f"  Auth error: {e}")
        return

    # get all videos
    videos_response = youtube.search().list(
        part="id",
        forMine=True,
        type="video",
        maxResults=50,
    ).execute()

    video_ids = [item["id"]["videoId"] for item in videos_response.get("items", [])]
    print(f"  Found {len(video_ids)} videos")

    if not video_ids:
        return

    # get current descriptions
    videos = youtube.videos().list(
        part="snippet",
        id=",".join(video_ids),
    ).execute()

    updated = 0
    skipped = 0

    for video in videos.get("items", []):
        video_id = video["id"]
        snippet = video["snippet"]
        title = snippet.get("title", "")
        description = snippet.get("description", "")

        # skip if already has disclosure
        if "DISCLOSURE" in description or "AI assistance" in description:
            print(f"  ✓ Already has disclosure: '{title[:50]}'")
            skipped += 1
            continue

        # add disclosure at the end
        new_description = description.rstrip() + "\n" + FTC_DISCLOSURE

        try:
            youtube.videos().update(
                part="snippet",
                body={
                    "id": video_id,
                    "snippet": {
                        **snippet,
                        "description": new_description[:5000],
                    },
                },
            ).execute()
            print(f"  ✅ Updated: '{title[:50]}'")
            updated += 1
        except Exception as e:
            print(f"  ❌ Error on '{title[:50]}': {e}")

    print(f"\n  {channel_name} done: {updated} updated, {skipped} already compliant")


def main():
    print("🔒 FTC Disclosure Batch Updater")
    print("Adding AI disclosure to all video descriptions...\n")

    channels = [
        {
            "name": "Wealth Whale",
            "token": "secrets/token_channelA.json",
            "secrets": "secrets/client_secrets_channelA.json",
        },
        {
            "name": "Chucky's Untold Stories",
            "token": "secrets/token_channelB.json",
            "secrets": "secrets/client_secrets_channelB.json",
        },
    ]

    for ch in channels:
        if os.path.exists(ch["token"]):
            add_ftc_to_channel(ch["token"], ch["secrets"], ch["name"])
        else:
            print(f"⚠️  No token for {ch['name']} — skipping")

    print("\n✅ FTC batch update complete!")
    print("All future videos get disclosure automatically via the pipeline.")


if __name__ == "__main__":
    main()
