# tests/test_font_downloader.py
# ============================================================
# Tests for the font downloader module.
# Verifies font file lookup, download logic, and ensure_fonts.
# ============================================================
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import config
from font_downloader import ensure_fonts, _download_and_extract, FONT_FILE_MAP


def test_font_file_map_has_all_fonts():
    """# Verify the FONT_FILE_MAP contains entries for both fonts."""
    assert "Baloo2" in FONT_FILE_MAP
    assert "FredokaOne" in FONT_FILE_MAP


def test_font_file_map_has_target_names():
    """# Each font entry should have a target_name and search_patterns."""
    for key, info in FONT_FILE_MAP.items():
        assert "target_name" in info, f"{key} missing target_name"
        assert "search_patterns" in info, f"{key} missing search_patterns"
        assert len(info["search_patterns"]) > 0, f"{key} has no search patterns"


def test_download_and_extract_skips_existing(tmp_path):
    """# If the target font file already exists, skip downloading."""
    with patch.object(config, "FONTS_DIR", tmp_path):
        # Create a fake existing font file
        target = tmp_path / "Baloo2-Bold.ttf"
        target.write_bytes(b"fake font data")

        # Should return True without downloading
        result = _download_and_extract("Baloo2")
        assert result is True


def test_ensure_fonts_skips_when_all_present(tmp_path, capsys):
    """# When both fonts exist, ensure_fonts should print 'already installed'."""
    with patch.object(config, "FONTS_DIR", tmp_path):
        # Create both font files
        (tmp_path / "Baloo2-Bold.ttf").write_bytes(b"font1")
        (tmp_path / "FredokaOne-Regular.ttf").write_bytes(b"font2")

        ensure_fonts()
        captured = capsys.readouterr()
        assert "already installed" in captured.out


def test_download_and_extract_handles_network_error(tmp_path):
    """# Network errors should be caught and return False."""
    import urllib.error
    with patch.object(config, "FONTS_DIR", tmp_path):
        with patch("font_downloader.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("No internet")):
            result = _download_and_extract("Baloo2")
            assert result is False
