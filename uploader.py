# uploader.py
# ============================================================
# Video upload to YouTube and TikTok.
# Handles authentication, metadata, and COPPA compliance.
# YouTube uses Data API v3, TikTok uses Content Posting API.
# ============================================================
import json
from pathlib import Path

import config


def upload_youtube(video_path: Path, metadata_path: Path,
                    thumbnail_path: Path = None) -> str:
    """
    # Upload a video to YouTube via the Data API v3.
    # Sets "Made for Kids" flag for COPPA compliance.
    # Requires client_secrets.json for OAuth2 authentication.
    # Returns the video URL on success.
    """
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow

    # Load metadata from JSON file
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # OAuth2 authentication (uses client_secrets.json — one-time browser flow)
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.PROJECT_ROOT / "client_secrets.json"), scopes
    )
    credentials = flow.run_local_server(port=0)
    youtube = build("youtube", "v3", credentials=credentials)

    # Build upload request body
    body = {
        "snippet": {
            "title": meta.get("title", "Leo Quiz"),
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
            "categoryId": "24",  # Entertainment category
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": True,  # COPPA compliance — required
        },
    }

    # Upload video file (resumable for reliability)
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = request.execute()
    video_id = response["id"]
    video_url = f"https://youtube.com/watch?v={video_id}"

    # Upload custom thumbnail if provided
    if thumbnail_path and thumbnail_path.exists():
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/png")
        ).execute()

    print(f"[UPLOAD] YouTube: {video_url}")
    return video_url


def upload_tiktok(video_path: Path, metadata_path: Path) -> str:
    """
    # Upload a video to TikTok via the Content Posting API.
    # Requires TikTok developer app setup.
    # Returns the post URL on success.
    """
    # TikTok upload requires developer app approval — placeholder for now
    print(f"[UPLOAD] TikTok upload not yet configured — skipping")
    print(f"[UPLOAD] Video ready at: {video_path}")
    return ""
