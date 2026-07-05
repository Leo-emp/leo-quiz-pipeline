# tests/test_narration.py
# ============================================================
# Tests for the narration module.
# Verifies varied phrase templates and round audio dataclass.
# ============================================================
import pytest

from narration import (
    RoundAudio, QUESTION_PHRASES, REVEAL_PHRASES, REACTION_PHRASES
)


def test_question_phrases_exist():
    """# Should have at least 5 varied question phrases."""
    assert len(QUESTION_PHRASES) >= 5


def test_reveal_phrases_exist():
    """# Should have at least 5 varied reveal phrases."""
    assert len(REVEAL_PHRASES) >= 5


def test_question_phrases_have_category_placeholder():
    """# Each question phrase should contain {category} for formatting."""
    for phrase in QUESTION_PHRASES:
        assert "{category}" in phrase, f"Missing {{category}} in: {phrase}"


def test_reveal_phrases_have_answer_placeholder():
    """# Each reveal phrase should contain {answer} for formatting."""
    for phrase in REVEAL_PHRASES:
        assert "{answer}" in phrase, f"Missing {{answer}} in: {phrase}"


def test_phrases_are_all_different():
    """# All phrases should be unique (no duplicates)."""
    assert len(set(QUESTION_PHRASES)) == len(QUESTION_PHRASES)
    assert len(set(REVEAL_PHRASES)) == len(REVEAL_PHRASES)


def test_phrase_rotation_varies_per_round():
    """# Different round indices should produce different phrases."""
    phrase_0 = QUESTION_PHRASES[0 % len(QUESTION_PHRASES)]
    phrase_1 = QUESTION_PHRASES[1 % len(QUESTION_PHRASES)]
    phrase_2 = QUESTION_PHRASES[2 % len(QUESTION_PHRASES)]
    assert phrase_0 != phrase_1
    assert phrase_1 != phrase_2


def test_reaction_phrases_exist():
    """# Should have at least 5 reaction interjections."""
    assert len(REACTION_PHRASES) >= 5


def test_reaction_phrases_are_short():
    """# Reactions should be short energetic phrases (under 30 chars)."""
    for phrase in REACTION_PHRASES:
        assert len(phrase) < 30, f"Reaction too long: {phrase}"


def test_round_audio_has_reaction_field():
    """# RoundAudio should have an optional reaction_path field."""
    from pathlib import Path
    ra = RoundAudio(
        question_path=Path("q.mp3"),
        reveal_path=Path("r.mp3"),
        fact_path=Path("f.mp3"),
    )
    # Default should be None
    assert ra.reaction_path is None
    # Should accept a path
    ra2 = RoundAudio(
        question_path=Path("q.mp3"),
        reveal_path=Path("r.mp3"),
        fact_path=Path("f.mp3"),
        reaction_path=Path("reaction.mp3"),
    )
    assert ra2.reaction_path == Path("reaction.mp3")
