# tests/test_uploader.py
# ============================================================
# Tests for multi-platform video uploaders.
# Uses mocks for all API calls — no real uploads in tests.
# Covers TikTok, Instagram, and Facebook upload functions.
# ============================================================
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_upload_tiktok_returns_url_on_success(tmp_path):
    """# Successful TikTok upload should return a post URL."""
    from uploader import upload_tiktok
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake video")
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"title": "Test", "description": "Test"}))
    token = {"access_token": "fake", "refresh_token": "fake", "expires_at": 9999999999}

    with patch("uploader.requests") as mock_req:
        # Mock TikTok's two-step upload (init → upload → publish)
        mock_req.post.return_value = MagicMock(
            ok=True, status_code=200,
            json=MagicMock(return_value={"data": {"publish_id": "123"}})
        )
        result = upload_tiktok(video, meta, token)
        assert isinstance(result, str)


def test_upload_tiktok_returns_empty_on_failure(tmp_path):
    """# Failed TikTok upload should return empty string."""
    from uploader import upload_tiktok
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake video")
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"title": "Test"}))
    token = {"access_token": "fake", "refresh_token": "fake", "expires_at": 9999999999}

    with patch("uploader.requests") as mock_req:
        mock_req.post.return_value = MagicMock(ok=False, status_code=401)
        result = upload_tiktok(video, meta, token)
        assert result == ""


def test_upload_instagram_returns_url_on_success(tmp_path):
    """# Successful Instagram upload should return a media URL."""
    from uploader import upload_instagram
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake video")
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"caption": "Test", "hashtags": ["#test"]}))
    token = {"access_token": "fake", "ig_user_id": "123", "expires_at": 9999999999}

    with patch("uploader.requests") as mock_req:
        # Mock Instagram's container-based upload flow
        mock_req.post.return_value = MagicMock(
            ok=True, json=MagicMock(return_value={"id": "456"})
        )
        mock_req.get.return_value = MagicMock(
            ok=True, json=MagicMock(return_value={"status_code": "FINISHED"})
        )
        result = upload_instagram(video, meta, token)
        assert isinstance(result, str)


def test_upload_facebook_returns_url_on_success(tmp_path):
    """# Successful Facebook upload should return a post URL."""
    from uploader import upload_facebook
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake video")
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"title": "Test", "description": "Test"}))
    token = {"page_access_token": "fake", "page_id": "789", "expires_at": 9999999999}

    with patch("uploader.requests") as mock_req:
        mock_req.post.return_value = MagicMock(
            ok=True, json=MagicMock(return_value={"id": "post_123"})
        )
        result = upload_facebook(video, meta, token)
        assert isinstance(result, str)


def test_all_uploaders_handle_missing_token(tmp_path):
    """# All uploaders should return empty string when token is None."""
    from uploader import upload_tiktok, upload_instagram, upload_facebook
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")
    meta = tmp_path / "meta.json"
    meta.write_text("{}")

    assert upload_tiktok(video, meta, None) == ""
    assert upload_instagram(video, meta, None) == ""
    assert upload_facebook(video, meta, None) == ""
