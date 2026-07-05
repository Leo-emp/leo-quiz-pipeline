# tests/test_music_downloader.py
# ============================================================
# Tests for the music downloader module.
# Verifies curated tracks config, download logic, and ensure_music.
# ============================================================
import pytest
from pathlib import Path
from unittest.mock import patch

import config
from music_downloader import (
    ensure_music, _download_track, CURATED_TRACKS, CATEGORY_SEARCH
)


def test_curated_tracks_cover_all_categories():
    """# Every quiz category should have a curated music track."""
    for category in config.CATEGORIES:
        assert category in CURATED_TRACKS, f"Missing track for: {category}"


def test_curated_tracks_have_required_fields():
    """# Each curated track entry should have url, name, and artist."""
    for category, info in CURATED_TRACKS.items():
        assert "url" in info, f"{category} missing url"
        assert "name" in info, f"{category} missing name"
        assert "artist" in info, f"{category} missing artist"
        assert info["url"].startswith("https://"), f"{category} url not https"


def test_category_search_covers_all_categories():
    """# Every category should have a search term for API fallback."""
    for category in config.CATEGORIES:
        assert category in CATEGORY_SEARCH, f"Missing search for: {category}"


def test_download_track_skips_existing(tmp_path):
    """# If a track file already exists, skip downloading."""
    with patch.object(config, "MUSIC_DIR", tmp_path):
        # Create a fake existing file
        (tmp_path / "animals.mp3").write_bytes(b"fake audio")
        result = _download_track("animals")
        assert result is True


def test_ensure_music_skips_when_all_present(tmp_path, capsys):
    """# When all tracks exist, ensure_music should print 'already installed'."""
    with patch.object(config, "MUSIC_DIR", tmp_path):
        # Create all category files
        for cat in config.CATEGORIES:
            (tmp_path / f"{cat}.mp3").write_bytes(b"audio")

        ensure_music()
        captured = capsys.readouterr()
        assert "already installed" in captured.out


def test_download_track_handles_network_error(tmp_path):
    """# Network errors should be caught and return False."""
    import urllib.error
    with patch.object(config, "MUSIC_DIR", tmp_path):
        with patch("music_downloader.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("No internet")):
            result = _download_track("animals")
            assert result is False
