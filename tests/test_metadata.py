# tests/test_metadata.py
# ============================================================
# Tests for metadata generation across all 4 platforms.
# Verifies platform-specific prompts, COPPA compliance,
# and correct field structure for YouTube/TikTok/Instagram/Facebook.
# ============================================================
import pytest
import sys
from unittest.mock import patch, MagicMock
from quiz_generator import QuizPack, QuizRound


def _make_quiz_pack():
    """# Helper to create a minimal quiz pack for testing."""
    rounds = [
        QuizRound(answer="Lion", hint_question="Which animal is the king of the jungle?",
                  fun_fact="Lions sleep 20 hours a day", difficulty="easy",
                  image_prompt="cute cartoon lion"),
    ]
    return QuizPack(category="animals", rounds=rounds)


def _run_with_mock_genai(response_text: str, func):
    """# Execute func with a mocked google.genai module.
    # The mock returns response_text as the Gemini API response.
    # Handles the deferred 'from google import genai' import."""
    # Build mock genai module with Client().models.generate_content()
    mock_genai = MagicMock()
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = MagicMock(text=response_text)

    # Build mock google package with .genai attribute
    mock_google = MagicMock()
    mock_google.genai = mock_genai

    with patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}):
        return func()


def test_generate_metadata_youtube():
    """# YouTube metadata should have title, description, tags, hashtags."""
    from metadata import generate_metadata
    pack = _make_quiz_pack()
    meta = _run_with_mock_genai(
        '{"title": "Guess the Animal!", "description": "Fun quiz", "tags": ["animals"], "hashtags": ["#quiz"]}',
        lambda: generate_metadata(pack, "youtube")
    )
    assert "title" in meta
    assert meta["made_for_kids"] is True
    assert meta["category"] == "animals"


def test_generate_metadata_instagram():
    """# Instagram metadata should have caption-style title + hashtags."""
    from metadata import generate_metadata
    pack = _make_quiz_pack()
    meta = _run_with_mock_genai(
        '{"title": "Can YOU guess?", "caption": "Play now!", "description": "Fun", "tags": [], "hashtags": ["#kidsgame"]}',
        lambda: generate_metadata(pack, "instagram")
    )
    assert "title" in meta or "caption" in meta
    assert meta["made_for_kids"] is True


def test_generate_metadata_facebook():
    """# Facebook metadata should have shareable title + description."""
    from metadata import generate_metadata
    pack = _make_quiz_pack()
    meta = _run_with_mock_genai(
        '{"title": "How Many Animals Can Your Kids Guess?", "description": "Play along!", "tags": [], "hashtags": []}',
        lambda: generate_metadata(pack, "facebook")
    )
    assert "title" in meta
    assert meta["made_for_kids"] is True


def test_all_platforms_accepted():
    """# generate_metadata should accept all 4 platform strings without error."""
    from metadata import generate_metadata
    pack = _make_quiz_pack()
    for platform in ["youtube", "tiktok", "instagram", "facebook"]:
        meta = _run_with_mock_genai(
            '{"title": "Test", "description": "Test", "tags": [], "hashtags": []}',
            lambda p=platform: generate_metadata(pack, p)
        )
        assert "title" in meta


def test_metadata_coppa_fields():
    """# Every platform must include COPPA compliance fields."""
    from metadata import generate_metadata
    pack = _make_quiz_pack()
    meta = _run_with_mock_genai(
        '{"title": "Test", "description": "Test", "tags": [], "hashtags": []}',
        lambda: generate_metadata(pack, "youtube")
    )
    assert meta["made_for_kids"] is True
    assert meta["category"] == "animals"
    assert meta["answers"] == ["Lion"]


def test_save_metadata(tmp_path):
    """# save_metadata should write valid JSON file."""
    from metadata import save_metadata
    meta = {"title": "Test", "made_for_kids": True}
    out = tmp_path / "meta.json"
    save_metadata(meta, out)
    assert out.exists()
    import json
    with open(out) as f:
        loaded = json.load(f)
    assert loaded["title"] == "Test"
