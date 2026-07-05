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
    # 6 rounds per short = ~66s total (TikTok requires 60s+ for monetization)
    assert ROUNDS_PER_SHORT == 6
    assert INTRO_DURATION == 2.0
    assert OUTRO_DURATION == 4.0

def test_longform_timing():
    """# Long-form round timing constants must be valid."""
    from config import (LONGFORM_ROUND_DURATION, LONGFORM_ROUNDS,
                        LONGFORM_TIMER_SECONDS, LONGFORM_INTRO_DURATION,
                        LONGFORM_OUTRO_DURATION, LONGFORM_SECTION_CARD_DURATION)
    # 8-second rounds for long-form
    assert LONGFORM_ROUND_DURATION == 8.0
    # 60 rounds for ~10 min
    assert LONGFORM_ROUNDS == 60
    # 5-second countdown timer
    assert LONGFORM_TIMER_SECONDS == 5
    # Intro and outro durations
    assert LONGFORM_INTRO_DURATION == 3.0
    assert LONGFORM_OUTRO_DURATION == 5.0
    # Milestone card duration (motivational hype cards at 25/50/75%)
    assert LONGFORM_SECTION_CARD_DURATION == 2.0


def test_longform_round_sub_timings():
    """# Long-form round phases must fit within LONGFORM_ROUND_DURATION."""
    from config import (LONGFORM_ROUND_DURATION, LONGFORM_SILHOUETTE_START,
                        LONGFORM_COUNTDOWN_START, LONGFORM_REVEAL_START,
                        LONGFORM_FUN_FACT_START, LONGFORM_TRANSITION_START)
    # All sub-timings must be within the round
    assert LONGFORM_SILHOUETTE_START == 0.0
    assert LONGFORM_COUNTDOWN_START == 0.5
    assert LONGFORM_REVEAL_START == 5.5
    assert LONGFORM_FUN_FACT_START == 6.5
    assert LONGFORM_TRANSITION_START == 7.7
    # Last phase must end before round ends
    assert LONGFORM_TRANSITION_START < LONGFORM_ROUND_DURATION


def test_mega_timing():
    """# Mega quiz timing constants must be valid."""
    from config import (MEGA_ROUND_DURATION, MEGA_ROUNDS, MEGA_TIMER_SECONDS,
                        MEGA_INTRO_DURATION, MEGA_OUTRO_DURATION)
    assert MEGA_ROUND_DURATION == 7.0
    assert MEGA_ROUNDS == 100
    assert MEGA_TIMER_SECONDS == 4
    assert MEGA_INTRO_DURATION == 4.0
    assert MEGA_OUTRO_DURATION == 6.0


def test_mega_round_sub_timings():
    """# Mega quiz round phases must fit within MEGA_ROUND_DURATION."""
    from config import (MEGA_ROUND_DURATION, MEGA_SILHOUETTE_START,
                        MEGA_COUNTDOWN_START, MEGA_REVEAL_START,
                        MEGA_FUN_FACT_START, MEGA_TRANSITION_START)
    assert MEGA_SILHOUETTE_START == 0.0
    assert MEGA_COUNTDOWN_START == 0.3
    assert MEGA_REVEAL_START == 4.8
    assert MEGA_FUN_FACT_START == 5.6
    assert MEGA_TRANSITION_START == 6.7
    assert MEGA_TRANSITION_START < MEGA_ROUND_DURATION


def test_longform_total_duration():
    """# Total long-form video should be approximately 10 minutes."""
    from config import (LONGFORM_ROUND_DURATION, LONGFORM_ROUNDS,
                        LONGFORM_INTRO_DURATION, LONGFORM_OUTRO_DURATION)
    total = LONGFORM_INTRO_DURATION + LONGFORM_ROUNDS * LONGFORM_ROUND_DURATION + LONGFORM_OUTRO_DURATION
    # Should be between 8 and 12 minutes
    assert 480 <= total <= 720


def test_mega_total_duration():
    """# Total mega quiz should be between 11 and 20 minutes."""
    from config import (MEGA_ROUND_DURATION, MEGA_ROUNDS,
                        MEGA_INTRO_DURATION, MEGA_OUTRO_DURATION)
    total = MEGA_INTRO_DURATION + MEGA_ROUNDS * MEGA_ROUND_DURATION + MEGA_OUTRO_DURATION
    # 100*7 + 4 + 6 = 710s ≈ 11.8 min
    assert 660 <= total <= 1200


def test_elevenlabs_voice_settings():
    """# Voice tuning settings should be in valid ranges for ElevenLabs API."""
    from config import (ELEVENLABS_STABILITY, ELEVENLABS_SIMILARITY_BOOST,
                        ELEVENLABS_STYLE, ELEVENLABS_USE_SPEAKER_BOOST)
    assert 0.0 <= ELEVENLABS_STABILITY <= 1.0
    assert 0.0 <= ELEVENLABS_SIMILARITY_BOOST <= 1.0
    assert 0.0 <= ELEVENLABS_STYLE <= 1.0
    assert isinstance(ELEVENLABS_USE_SPEAKER_BOOST, bool)
