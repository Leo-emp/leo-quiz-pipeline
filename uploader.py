# uploader.py
# ============================================================
# Video upload to YouTube, TikTok, Instagram, and Facebook.
# Handles authentication, metadata, and COPPA compliance.
#
# YouTube: Data API v3 (OAuth2 via client_secrets.json)
# TikTok: Content Posting API v2 (direct post flow)
# Instagram: Graph API container-based Reels publish
# Facebook: Graph API video upload to Page
#
# Each uploader returns a platform URL on success, "" on failure.
# Token data is passed as dict (loaded from Vercel Blob in dashboard).
# ============================================================
import json
import os
import time
import functools
import logging
from pathlib import Path

import requests

import config

logger = logging.getLogger(__name__)


def _upload_to_blob(video_path: Path) -> str:
    """
    # Upload a video file to Vercel Blob and return the public URL.
    # Required for Instagram Graph API which needs a publicly accessible URL.
    # Falls back to empty string if BLOB_READ_WRITE_TOKEN is not set.
    """
    token = config.BLOB_READ_WRITE_TOKEN if hasattr(config, "BLOB_READ_WRITE_TOKEN") else os.environ.get("BLOB_READ_WRITE_TOKEN", "")
    if not token:
        logger.error("[UPLOAD] No BLOB_READ_WRITE_TOKEN — cannot upload to Blob for Instagram")
        return ""

    blob_name = f"ig-upload/{video_path.name}"
    with open(video_path, "rb") as f:
        resp = requests.put(
            f"https://blob.vercel-storage.com/{blob_name}",
            headers={
                "Authorization": f"Bearer {token}",
                "x-content-type": "video/mp4",
                "x-api-version": "7",
            },
            data=f,
        )

    if resp.ok:
        url = resp.json().get("url", "")
        logger.info(f"[UPLOAD] Video uploaded to Blob: {url}")
        return url

    logger.error(f"[UPLOAD] Blob upload failed: {resp.status_code} {resp.text}")
    return ""


def _delete_from_blob(blob_url: str) -> None:
    """Clean up temporary Blob upload after Instagram post."""
    token = config.BLOB_READ_WRITE_TOKEN if hasattr(config, "BLOB_READ_WRITE_TOKEN") else os.environ.get("BLOB_READ_WRITE_TOKEN", "")
    if not token or not blob_url:
        return
    try:
        requests.post(
            "https://blob.vercel-storage.com/delete",
            headers={"Authorization": f"Bearer {token}", "x-api-version": "7"},
            json={"urls": [blob_url]},
        )
    except Exception:
        pass


def retry_upload(max_attempts=3, backoff_base=2):
    """
    # Retry decorator for upload functions.
    # Retries on transient errors with exponential backoff (2s, 4s, 8s).
    # Skips retry for auth errors (401/403) since those won't self-heal.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = fn(*args, **kwargs)
                    if result:
                        return result
                    if attempt < max_attempts:
                        delay = backoff_base ** attempt
                        logger.warning(f"[UPLOAD] {fn.__name__} returned empty on attempt {attempt}, retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    return result
                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    if any(code in error_str for code in ["401", "403", "unauthorized", "forbidden"]):
                        logger.error(f"[UPLOAD] {fn.__name__} auth error (no retry): {e}")
                        return ""
                    if attempt < max_attempts:
                        delay = backoff_base ** attempt
                        logger.warning(f"[UPLOAD] {fn.__name__} attempt {attempt} failed: {e}, retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"[UPLOAD] {fn.__name__} failed after {max_attempts} attempts: {e}")
            return ""
        return wrapper
    return decorator


@retry_upload(max_attempts=3)
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


@retry_upload(max_attempts=3)
def upload_tiktok(video_path: Path, metadata_path: Path,
                   token: dict = None) -> str:
    """
    # Upload a video to TikTok via the Content Posting API v2.
    # Uses direct post flow (no user approval step).
    # Sets privacy to public and marks as kids content.
    # Returns post URL on success, "" on failure.
    """
    # Guard: no token = can't upload
    if token is None:
        print("[UPLOAD] TikTok: No token provided — skipping")
        return ""

    access_token = token.get("access_token", "")
    if not access_token:
        print("[UPLOAD] TikTok: Invalid token — skipping")
        return ""

    try:
        # Load metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # Read video file size for chunk upload
        video_size = video_path.stat().st_size

        # Step 1: Initialize video upload (direct post)
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        init_body = {
            "post_info": {
                "title": meta.get("title", "Leo Quiz")[:150],
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,
                "total_chunk_count": 1,
            },
        }

        resp = requests.post(init_url, headers=headers, json=init_body)
        if not resp.ok:
            print(f"[UPLOAD] TikTok init failed: {resp.status_code}")
            return ""

        data = resp.json().get("data", {})
        publish_id = data.get("publish_id", "")
        upload_url = data.get("upload_url", "")

        # Step 2: Upload video binary to the upload URL
        if upload_url:
            with open(video_path, "rb") as f:
                upload_resp = requests.put(
                    upload_url,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
                    },
                    data=f,
                )

        print(f"[UPLOAD] TikTok: Published (ID: {publish_id})")
        return f"https://www.tiktok.com/@leoquiz/video/{publish_id}"

    except Exception as e:
        logger.error(f"[UPLOAD] TikTok upload failed: {e}")
        raise


@retry_upload(max_attempts=3)
def upload_instagram(video_path: Path, metadata_path: Path,
                      token: dict = None) -> str:
    """
    # Upload a Reel to Instagram via the Graph API.
    # Uses container-based publish flow:
    # 1. Create media container with video URL
    # 2. Wait for processing
    # 3. Publish the container
    # Returns media URL on success, "" on failure.
    """
    # Guard: no token = can't upload
    if token is None:
        print("[UPLOAD] Instagram: No token provided — skipping")
        return ""

    access_token = token.get("access_token", "")
    ig_user_id = token.get("ig_user_id", "")
    if not access_token or not ig_user_id:
        print("[UPLOAD] Instagram: Invalid token — skipping")
        return ""

    try:
        # Load metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # Build caption from title + hashtags
        caption = meta.get("caption", meta.get("title", "Leo Quiz"))
        hashtags = meta.get("hashtags", [])
        if hashtags:
            caption += "\n\n" + " ".join(hashtags)

        # Upload to Vercel Blob first — Instagram API needs a public URL, not a local path
        blob_url = _upload_to_blob(video_path)
        if not blob_url:
            logger.error("[UPLOAD] Instagram: cannot upload without public video URL")
            return ""

        # Step 1: Create Reels media container
        create_url = f"https://graph.facebook.com/v21.0/{ig_user_id}/media"
        create_resp = requests.post(create_url, params={
            "media_type": "REELS",
            "video_url": blob_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": access_token,
        })

        if not create_resp.ok:
            logger.error(f"[UPLOAD] Instagram container failed: {create_resp.status_code}")
            _delete_from_blob(blob_url)
            return ""

        container_id = create_resp.json().get("id", "")

        # Step 2: Wait for video processing (poll status)
        status_url = f"https://graph.facebook.com/v21.0/{container_id}"
        for _ in range(30):
            status_resp = requests.get(status_url, params={
                "fields": "status_code",
                "access_token": access_token,
            })
            if status_resp.ok:
                status = status_resp.json().get("status_code", "")
                if status == "FINISHED":
                    break
                elif status == "ERROR":
                    print("[UPLOAD] Instagram: Video processing failed")
                    return ""
            time.sleep(2)

        # Step 3: Publish the container
        publish_url = f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish"
        pub_resp = requests.post(publish_url, params={
            "creation_id": container_id,
            "access_token": access_token,
        })

        if not pub_resp.ok:
            print(f"[UPLOAD] Instagram publish failed: {pub_resp.status_code}")
            return ""

        media_id = pub_resp.json().get("id", "")
        media_url = f"https://www.instagram.com/reel/{media_id}/"

        _delete_from_blob(blob_url)
        print(f"[UPLOAD] Instagram: {media_url}")
        return media_url

    except Exception as e:
        if 'blob_url' in locals():
            _delete_from_blob(blob_url)
        logger.error(f"[UPLOAD] Instagram upload failed: {e}")
        raise


@retry_upload(max_attempts=3)
def upload_facebook(video_path: Path, metadata_path: Path,
                     token: dict = None) -> str:
    """
    # Upload a Reel to a Facebook Page via the Graph API.
    # Uses resumable upload for reliability with large files.
    # Returns post URL on success, "" on failure.
    """
    # Guard: no token = can't upload
    if token is None:
        print("[UPLOAD] Facebook: No token provided — skipping")
        return ""

    page_token = token.get("page_access_token", "")
    page_id = token.get("page_id", "")
    if not page_token or not page_id:
        print("[UPLOAD] Facebook: Invalid token — skipping")
        return ""

    try:
        # Load metadata
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        title = meta.get("title", "Leo Quiz")
        description = meta.get("description", "")

        # Upload video to Facebook Page as a Reel
        upload_url = f"https://graph.facebook.com/v21.0/{page_id}/video_reels"

        with open(video_path, "rb") as f:
            resp = requests.post(
                upload_url,
                params={"access_token": page_token},
                files={"source": (video_path.name, f, "video/mp4")},
                data={
                    "description": f"{title}\n\n{description}",
                },
            )

        if not resp.ok:
            print(f"[UPLOAD] Facebook upload failed: {resp.status_code}")
            return ""

        post_id = resp.json().get("id", "")
        post_url = f"https://www.facebook.com/{page_id}/videos/{post_id}"

        print(f"[UPLOAD] Facebook: {post_url}")
        return post_url

    except Exception as e:
        logger.error(f"[UPLOAD] Facebook upload failed: {e}")
        raise
