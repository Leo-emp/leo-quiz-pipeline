# tests/test_compiler.py
import pytest
from pathlib import Path
import json

def test_collect_week_rounds(tmp_path):
    """# Should find and load all quiz packs from a week's output dirs."""
    from compiler import collect_week_rounds

    # Create fake daily output dirs with quiz pack JSON
    for day in ["2026-07-01_animals", "2026-07-02_dinosaurs"]:
        day_dir = tmp_path / day
        day_dir.mkdir()
        pack = {
            "category": day.split("_")[1],
            "rounds": [{"answer": "Lion", "hint_question": "q",
                         "fun_fact": "f", "difficulty": "easy",
                         "image_prompt": "p"}]
        }
        with open(day_dir / "quiz_pack.json", "w") as f:
            json.dump(pack, f)

    rounds = collect_week_rounds([tmp_path / "2026-07-01_animals",
                                   tmp_path / "2026-07-02_dinosaurs"])
    assert len(rounds) == 2
