# compiler.py
# ============================================================
# Utilities for collecting short-form quiz rounds from daily
# output directories. Used by longform_assembler.py for
# weekly compilations.
# ============================================================
import json
from datetime import datetime, timedelta
from pathlib import Path

import config
from quiz_generator import QuizRound


def collect_week_rounds(day_dirs: list[Path]) -> list[dict]:
    """
    # Collect all quiz rounds from a list of daily output directories.
    # Reads quiz_pack.json from each dir and builds a combined list.
    # Returns list of dicts with round data + image/silhouette paths.
    """
    all_rounds = []
    for day_dir in day_dirs:
        pack_file = day_dir / "quiz_pack.json"
        # Skip dirs without quiz pack data
        if not pack_file.exists():
            continue

        with open(pack_file, "r", encoding="utf-8") as f:
            pack_data = json.load(f)

        category = pack_data.get("category", "animals")
        rounds_dir = day_dir / "rounds"

        # Build round objects with paths to associated media files
        for i, r in enumerate(pack_data.get("rounds", [])):
            all_rounds.append({
                "round": QuizRound(**r) if isinstance(r, dict) else r,
                "category": category,
                "image_path": rounds_dir / f"round_{i+1}_image.png",
                "silhouette_path": rounds_dir / f"round_{i+1}_silhouette.png",
            })

    return all_rounds


def find_week_dirs(shorts_dir: Path = None) -> list[Path]:
    """
    # Find all daily output directories from the past 7 days.
    # Scans the shorts output folder for date-prefixed directories.
    """
    if shorts_dir is None:
        shorts_dir = config.SHORTS_DIR

    if not shorts_dir.exists():
        return []

    week_dirs = []
    today = datetime.now()

    # Check each of the last 7 days
    for i in range(7):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        # Find directories matching this date prefix
        for d in shorts_dir.iterdir():
            if d.is_dir() and d.name.startswith(date_str):
                week_dirs.append(d)

    return sorted(week_dirs)


