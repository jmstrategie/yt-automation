"""
modules/upload.py
Handles YouTube Data API v3 uploads:
- OAuth2 authentication (cached token per channel)
- Video upload with metadata
- Thumbnail upload
- Playlist creation and management (for series)
- Scheduled publishing
"""

import os
import json
import pickle
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import ChannelConfig

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def get_youtube_client(channel: ChannelConfig):
    """Authenticate and return a YouTube API client for the given channel."""
    creds = None
    token_path = channel.token_file

    # load cached token if it exists
    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    # refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(channel.secrets_file):
                raise FileNotFoundError(
                    f"client_secrets not found: {channel.secrets_file}\n"
                    "Download it from Google Cloud Console → APIs & Services → Credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                channel.secrets_file, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # save token for future runs
        os.makedirs(Path(token_path).parent, exist_ok=True)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def get_or_create_playlist(
    youtube,
    title: str,
    description: str = "",
) -> str:
    """Find an existing playlist by title or create a new one. Returns playlist ID."""
    # search existing playlists
    response = youtube.playlists().list(
        part="snippet",
        mine=True,
        maxResults=50,
    ).execute()

    for playlist in response.get("items", []):
        if playlist["snippet"]["title"].lower() == title.lower():
            print(f"  [upload] Found existing playlist: {title}")
            return playlist["id"]

    # create new playlist
    response = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "defaultLanguage": "en",
            },
            "status": {"privacyStatus": "public"},
        },
    ).execute()

    playlist_id = response["id"]
    print(f"  [upload] Created playlist: {title} ({playlist_id})")
    return playlist_id


def add_to_playlist(youtube, video_id: str, playlist_id: str) -> None:
    """Add a video to a playlist."""
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        },
    ).execute()
    print(f"  [upload] Added {video_id} to playlist {playlist_id}")


def upload_video(
    channel: ChannelConfig,
    video_path: str,
    thumbnail_path: str,
    title: str,
    description: str,
    tags: list,
    publish_at: Optional[datetime] = None,
    playlist_title: Optional[str] = None,
) -> str:
    """
    Upload video to YouTube.
    publish_at: if set, schedules the video (must be UTC, future time).
    Returns the YouTube video ID.
    """
    print(f"\n  [upload] Authenticating for {channel.name}...")
    youtube = get_youtube_client(channel)

    # determine privacy status
    if publish_at:
        privacy = "private"  # scheduled videos must start as private
        publish_str = publish_at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    else:
        privacy = "public"
        publish_str = None

    body = {
        "snippet": {
            "title": title[:100],          # YouTube max
            "description": description[:5000],
            "tags": tags[:500],            # YouTube max 500 chars total
            "categoryId": "22",            # People & Blogs (use 26 for Howto, 28 for Sci&Tech)
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    if publish_str:
        body["status"]["publishAt"] = publish_str

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 10,  # 10 MB chunks
    )

    print(f"  [upload] Uploading '{title}'...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  [upload] {pct}% uploaded...", end="\r")

    video_id = response["id"]
    print(f"  [upload] Upload complete: https://youtube.com/watch?v={video_id}")

    # upload thumbnail
    if os.path.exists(thumbnail_path):
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
        ).execute()
        print(f"  [upload] Thumbnail set")

    # add to playlist if series
    if playlist_title:
        playlist_id = get_or_create_playlist(
            youtube,
            title=playlist_title,
            description=f"Full series: {playlist_title}",
        )
        add_to_playlist(youtube, video_id, playlist_id)

    return video_id


def schedule_series_uploads(
    channel: ChannelConfig,
    videos: list,          # list of dicts with video_path, thumbnail_path, script
    series_title: str,
    start_time: Optional[datetime] = None,
) -> list:
    """
    Upload all parts of a series, scheduling each 24h apart.
    Returns list of video IDs.
    """
    if start_time is None:
        # default: start in 1 hour
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)

    video_ids = []
    for i, video in enumerate(videos):
        publish_at = start_time + timedelta(days=i)
        vid_id = upload_video(
            channel=channel,
            video_path=video["video_path"],
            thumbnail_path=video["thumbnail_path"],
            title=video["script"].title,
            description=video["script"].description,
            tags=video["script"].tags,
            publish_at=publish_at,
            playlist_title=series_title,
        )
        video_ids.append(vid_id)

    return video_ids


if __name__ == "__main__":
    print("upload.py — import OK")
    print("Run pipeline.py to trigger a full upload.")
