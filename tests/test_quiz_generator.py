# tests/test_quiz_generator.py
import pytest
import json
from pathlib import Path

def test_quiz_round_dataclass():
    """# QuizRound should hold all fields for one quiz question."""
    from quiz_generator import QuizRound
    r = QuizRound(
        answer="Lion",
        hint_question="This animal is the king of the jungle!",
        fun_fact="Lions sleep up to 20 hours a day!",
        difficulty="easy",
        image_prompt="cartoon lion on white background"
    )
    assert r.answer == "Lion"
    assert r.difficulty == "easy"

def test_quiz_pack_dataclass():
    """# QuizPack should hold category and list of rounds."""
    from quiz_generator import QuizPack, QuizRound
    rounds = [
        QuizRound("Lion", "King of the jungle", "Sleeps 20 hrs", "easy", "lion prompt"),
        QuizRound("Tiger", "Striped big cat", "Can swim", "medium", "tiger prompt"),
    ]
    pack = QuizPack(category="animals", rounds=rounds)
    assert pack.category == "animals"
    assert len(pack.rounds) == 2

def test_load_history_empty(tmp_path):
    """# load_history should return empty dict when no file exists."""
    from quiz_generator import load_history
    result = load_history(tmp_path / "nonexistent.json")
    assert result == {}

def test_save_and_load_history(tmp_path):
    """# save_history then load_history should round-trip correctly."""
    from quiz_generator import save_history, load_history
    history_file = tmp_path / "history.json"
    data = {"animals": ["Lion", "Tiger"], "total_used": 2}
    save_history(data, history_file)
    loaded = load_history(history_file)
    assert loaded["animals"] == ["Lion", "Tiger"]
    assert loaded["total_used"] == 2

def test_update_history():
    """# update_history should add new answers without duplicates."""
    from quiz_generator import update_history, QuizRound, QuizPack
    history = {"animals": ["Lion"], "total_used": 1}
    pack = QuizPack(
        category="animals",
        rounds=[
            QuizRound("Tiger", "q", "f", "easy", "p"),
            QuizRound("Lion", "q", "f", "easy", "p"),  # duplicate
        ]
    )
    updated = update_history(history, pack)
    assert "Tiger" in updated["animals"]
    assert updated["animals"].count("Lion") == 1
    assert updated["total_used"] == 2

def test_parse_quiz_response():
    """# parse_quiz_response should extract QuizPack from Gemini JSON string."""
    from quiz_generator import parse_quiz_response
    raw_json = json.dumps({
        "category": "animals",
        "rounds": [
            {
                "answer": "Elephant",
                "hint_question": "Largest land animal!",
                "fun_fact": "Elephants can't jump!",
                "difficulty": "easy",
                "image_prompt": "cartoon elephant"
            }
        ]
    })
    pack = parse_quiz_response(raw_json, "animals")
    assert pack.category == "animals"
    assert len(pack.rounds) == 1
    assert pack.rounds[0].answer == "Elephant"
