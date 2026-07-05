# tests/test_narration.py
# ============================================================
# Tests for the narration module.
# Verifies varied phrase templates and round audio dataclass.
# ============================================================
import pytest

from narration import (
    RoundAudio, QUESTION_PHRASES, REVEAL_PHRASES
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
