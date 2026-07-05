# tests/test_config.py
import pytest

def test_categories_exist():
    from config import CATEGORIES
    # All 6 categories must be defined
    assert "animals" in CATEGORIES
    assert "dinosaurs" in CATEGORIES
    assert "space" in CATEGORIES
    assert "vehicles" in CATEGORIES
    assert "fruits" in CATEGORIES
    assert "flags" in CATEGORIES

def test_category_colors():
    from config import CATEGORY_COLORS
    # Each category must have primary + secondary hex colors
    for cat in ["animals", "dinosaurs", "space", "vehicles", "fruits", "flags"]:
        assert cat in CATEGORY_COLORS
        assert "primary" in CATEGORY_COLORS[cat]
        assert "secondary" in CATEGORY_COLORS[cat]
        assert CATEGORY_COLORS[cat]["primary"].startswith("#")

def test_get_today_category():
    from config import get_today_category
    result = get_today_category()
    assert result in ["animals", "dinosaurs", "space", "vehicles", "fruits", "flags", "mixed"]

def test_video_sizes():
    from config import SHORTS_SIZE, LONGFORM_SIZE
    assert SHORTS_SIZE == (1080, 1920)
    assert LONGFORM_SIZE == (1920, 1080)

def test_round_timing():
    from config import ROUND_DURATION, ROUNDS_PER_SHORT, INTRO_DURATION, OUTRO_DURATION
    assert ROUND_DURATION == 10.0
    assert ROUNDS_PER_SHORT == 5
    assert INTRO_DURATION == 2.0
    assert OUTRO_DURATION == 4.0

def test_elevenlabs_voice_settings():
    """# Voice tuning settings should be in valid ranges for ElevenLabs API."""
    from config import (ELEVENLABS_STABILITY, ELEVENLABS_SIMILARITY_BOOST,
                        ELEVENLABS_STYLE, ELEVENLABS_USE_SPEAKER_BOOST)
    assert 0.0 <= ELEVENLABS_STABILITY <= 1.0
    assert 0.0 <= ELEVENLABS_SIMILARITY_BOOST <= 1.0
    assert 0.0 <= ELEVENLABS_STYLE <= 1.0
    assert isinstance(ELEVENLABS_USE_SPEAKER_BOOST, bool)
