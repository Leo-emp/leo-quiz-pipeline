# tests/test_longform_assembler.py
# ============================================================
# Tests for the long-form video assembler (16:9 landscape).
# Verifies timeline building, milestone cards, frame rendering,
# and landscape layout dimensions.
# ============================================================
import pytest
import numpy as np
from pathlib import Path

import config


def test_longform_timeline_has_intro_rounds_outro():
    """# Timeline should have intro + N rounds + milestone cards + outro events."""
    from longform_assembler import build_longform_timeline
    timeline = build_longform_timeline(10, config.LONGFORM_ROUND_DURATION, "long")
    # First event should be intro
    phases = [e["phase"] for e in timeline]
    assert phases[0] == "intro"
    # Last event should be outro
    assert phases[-1] == "outro"
    # Should have round events (at least one per round)
    round_events = [e for e in timeline if e["round"] >= 0]
    assert len(round_events) >= 10


def test_longform_timeline_round_timing():
    """# Each round should span exactly LONGFORM_ROUND_DURATION seconds."""
    from longform_assembler import build_longform_timeline
    timeline = build_longform_timeline(5, config.LONGFORM_ROUND_DURATION, "long")
    # Find first round's events
    round_0_events = [e for e in timeline if e["round"] == 0]
    first_start = round_0_events[0]["start"]
    last_end = round_0_events[-1]["end"]
    assert pytest.approx(last_end - first_start, abs=0.1) == config.LONGFORM_ROUND_DURATION


def test_mega_timeline_uses_mega_duration():
    """# Mega quiz timeline should use MEGA_ROUND_DURATION."""
    from longform_assembler import build_longform_timeline
    timeline = build_longform_timeline(5, config.MEGA_ROUND_DURATION, "mega")
    round_0_events = [e for e in timeline if e["round"] == 0]
    first_start = round_0_events[0]["start"]
    last_end = round_0_events[-1]["end"]
    assert pytest.approx(last_end - first_start, abs=0.1) == config.MEGA_ROUND_DURATION


def test_longform_timeline_total_duration():
    """# Total timeline duration should match expected video length."""
    from longform_assembler import build_longform_timeline
    timeline = build_longform_timeline(60, config.LONGFORM_ROUND_DURATION, "long")
    total = timeline[-1]["end"]
    # 3s intro + 60*8s rounds + milestone cards (4 × 2s) + 5s outro
    # Milestones add extra time, so total should be >= base duration
    base = config.LONGFORM_INTRO_DURATION + 60 * config.LONGFORM_ROUND_DURATION + config.LONGFORM_OUTRO_DURATION
    assert total >= base
    # Should not exceed base + 5 milestone cards × 2s each
    assert total <= base + 5 * config.LONGFORM_SECTION_CARD_DURATION + 1.0


def test_longform_timeline_has_milestone_cards():
    """# 60-round long-form should have milestone cards at 25%, 50%, 75% + final question."""
    from longform_assembler import build_longform_timeline
    timeline = build_longform_timeline(60, config.LONGFORM_ROUND_DURATION, "long")
    # Find all milestone events
    milestones = [e for e in timeline if e["phase"] == "milestone"]
    # Should have at least 3 milestones (25%, 50%, 75%) + final question
    assert len(milestones) >= 3


def test_mega_timeline_has_milestone_cards():
    """# 100-round mega should have milestone cards at 25%, 50%, 75% + final question."""
    from longform_assembler import build_longform_timeline
    timeline = build_longform_timeline(100, config.MEGA_ROUND_DURATION, "mega")
    milestones = [e for e in timeline if e["phase"] == "milestone"]
    assert len(milestones) >= 3


def test_longform_context_creation():
    """# LongformContext should accept all required fields."""
    from longform_assembler import LongformContext
    ctx = LongformContext(
        width=1920, height=1080,
        category="animals",
        rounds=[], image_paths=[], silhouette_paths=[],
        mascot_images={}, particle_system=None,
        themed_decorations=None,
        format_type="long",
        total_rounds=60,
    )
    assert ctx.width == 1920
    assert ctx.height == 1080
    assert ctx.format_type == "long"
    assert ctx.total_rounds == 60


def test_render_longform_frame_returns_rgb_array():
    """# render_longform_frame should return (1080, 1920, 3) numpy array."""
    from longform_assembler import LongformContext, render_longform_frame, build_longform_timeline
    from animations import ParticleSystem
    from effects import ThemedDecorations

    timeline = build_longform_timeline(2, config.LONGFORM_ROUND_DURATION, "long")
    ctx = LongformContext(
        width=1920, height=1080,
        category="animals",
        rounds=[], image_paths=[], silhouette_paths=[],
        mascot_images={},
        particle_system=ParticleSystem(1920, 1080, count=5),
        themed_decorations=ThemedDecorations("animals", 1920, 1080),
        format_type="long",
        total_rounds=2,
        timeline=timeline,
    )
    # Render an intro frame
    frame = render_longform_frame(0.5, ctx)
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (1080, 1920, 3)
    assert frame.dtype == np.uint8


def test_render_longform_frame_landscape_dimensions():
    """# Frame dimensions must be 1920x1080 (16:9 landscape)."""
    from longform_assembler import LongformContext, render_longform_frame, build_longform_timeline
    from animations import ParticleSystem
    from effects import ThemedDecorations

    timeline = build_longform_timeline(1, config.LONGFORM_ROUND_DURATION, "long")
    ctx = LongformContext(
        width=1920, height=1080,
        category="space",
        rounds=[], image_paths=[], silhouette_paths=[],
        mascot_images={},
        particle_system=ParticleSystem(1920, 1080, count=5),
        themed_decorations=ThemedDecorations("space", 1920, 1080),
        format_type="long",
        total_rounds=1,
        timeline=timeline,
    )
    frame = render_longform_frame(0.0, ctx)
    # Height, Width, Channels
    assert frame.shape[0] == 1080
    assert frame.shape[1] == 1920
