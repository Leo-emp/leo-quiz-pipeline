# quiz_generator.py
# ============================================================
# Quiz content generation using Gemini 2.5 Flash.
# Generates quiz packs with answers, hints, fun facts,
# difficulty levels, and image prompts.
# Never-repeat system via history.json tracking.
# ============================================================
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import config


@dataclass
class QuizRound:
    """# One quiz question with all metadata needed for video generation."""
    answer: str            # The answer (e.g., "Lion")
    hint_question: str     # Playful clue for kids
    fun_fact: str          # Surprising fact under 15 words
    difficulty: str        # "easy", "medium", or "hard"
    image_prompt: str      # Gemini Imagen prompt for cartoon illustration
    pexels_search: str = "" # Search term for Pexels photo API (speed quiz format)


@dataclass
class QuizPack:
    """# A complete set of quiz rounds for one video."""
    category: str                              # Which category (animals, space, etc.)
    rounds: list[QuizRound] = field(default_factory=list)  # List of quiz rounds


def load_history(history_file: Path = None) -> dict:
    """# Load previously used answers from history.json to avoid repeats."""
    if history_file is None:
        history_file = config.HISTORY_FILE
    # Return empty dict if file doesn't exist yet
    if not history_file.exists():
        return {}
    with open(history_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history: dict, history_file: Path = None) -> None:
    """# Save updated history to history.json with timestamp."""
    if history_file is None:
        history_file = config.HISTORY_FILE
    # Add last updated timestamp for tracking
    history["last_updated"] = datetime.now().isoformat()
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def update_history(history: dict, pack: QuizPack) -> dict:
    """# Add new answers from a quiz pack to history. Skips duplicates."""
    category = pack.category
    # Initialize category list if first time
    if category not in history:
        history[category] = []

    # Track existing answers as set for O(1) duplicate check
    existing = set(history[category])
    for r in pack.rounds:
        if r.answer not in existing:
            history[category].append(r.answer)
            existing.add(r.answer)

    # Recalculate total count across all categories
    history["total_used"] = sum(
        len(v) for k, v in history.items()
        if k not in ("total_used", "last_updated") and isinstance(v, list)
    )
    return history


def parse_quiz_response(raw_json: str, category: str) -> QuizPack:
    """
    # Parse Gemini's JSON response into a QuizPack.
    # Handles JSON wrapped in markdown code fences (```json ... ```).
    """
    # Strip markdown code fences if Gemini wraps its output
    cleaned = raw_json.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    data = json.loads(cleaned)

    # Build QuizRound objects from each round in the response
    rounds = []
    for r in data.get("rounds", []):
        rounds.append(QuizRound(
            answer=r["answer"],
            hint_question=r["hint_question"],
            fun_fact=r["fun_fact"],
            difficulty=r.get("difficulty", "medium"),
            # Use custom prompt or fall back to template
            image_prompt=r.get("image_prompt",
                               config.IMAGE_PROMPT_TEMPLATE.format(answer=r["answer"])),
            # Pexels search term for speed quiz real photos
            pexels_search=r.get("pexels_search", r["answer"]),
        ))

    return QuizPack(category=category, rounds=rounds)


def generate_quiz_pack(category: str, num_rounds: int = None) -> QuizPack:
    """
    # Generate a fresh quiz pack using Gemini 2.5 Flash.
    # Loads history to avoid repeating past answers.
    # Returns a QuizPack with num_rounds unique questions.
    """
    from google import genai

    if num_rounds is None:
        num_rounds = config.ROUNDS_PER_SHORT

    # Load history for never-repeat system
    history = load_history()
    used_answers = history.get(category, [])

    # Build the category-specific prompt
    cat_info = config.CATEGORIES[category]

    # Craft prompt with strict JSON output format and exclusion list
    prompt = f"""You are a kids quiz content generator. Generate exactly {num_rounds} quiz questions about {cat_info['prompt_hint']}.

RULES:
- Each answer must be a specific, recognizable {cat_info['display'].lower()}
- Fun facts must be kid-appropriate, surprising, and under 15 words
- hint_question should be a playful clue (not the answer itself)
- Difficulty: {num_rounds} rounds with mix of easy (common, well-known), medium (less common but recognizable), and hard (rare/exotic)
- image_prompt should describe a cute cartoon illustration on pure white background
- NEVER use any of these previously used answers: {json.dumps(used_answers[-200:])}

Return ONLY valid JSON in this exact format:
{{
  "category": "{category}",
  "rounds": [
    {{
      "answer": "Lion",
      "hint_question": "This animal is called the king of the jungle!",
      "fun_fact": "Lions can sleep up to 20 hours a day!",
      "difficulty": "easy",
      "image_prompt": "Cute colorful cartoon illustration of a lion, kid-friendly style, bright vibrant colors, clean edges, full body view, centered, pure white background, no text, no watermark, high quality, children's book illustration style"
    }}
  ]
}}"""

    # Call Gemini 2.5 Flash for fast, cheap content generation
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # Parse the JSON response into structured QuizPack
    pack = parse_quiz_response(response.text, category)

    # Update and save history so these answers won't repeat
    history = update_history(history, pack)
    save_history(history)

    return pack


def generate_speed_quiz_pack(category: str,
                              num_rounds: int = None) -> QuizPack:
    """
    # Generate a speed quiz pack with 120 rounds across 4 difficulty tiers.
    # Each tier has 30 rounds: Easy → Medium → Hard → Impossible.
    # Includes pexels_search field for real photo fetching.
    # Generates in 4 batches of 30 to stay within Gemini output limits.
    """
    from google import genai

    if num_rounds is None:
        num_rounds = config.SPEED_ROUNDS

    # Load history for never-repeat system
    history = load_history()
    used_answers = history.get(category, [])
    cat_info = config.CATEGORIES[category]

    # Build the full quiz in 4 batches (one per difficulty tier)
    all_rounds = []
    rounds_per_tier = num_rounds // len(config.SPEED_DIFFICULTIES)

    for difficulty in config.SPEED_DIFFICULTIES:
        # Describe what this difficulty tier means
        difficulty_desc = {
            "EASY": "very common, everyday items that most 5-year-olds would recognize instantly",
            "MEDIUM": "recognizable but less common items that most 8-year-olds would know",
            "HARD": "uncommon items that would challenge a 12-year-old",
            "IMPOSSIBLE": "rare, exotic, or obscure items that would stump most adults",
        }

        # Collect all answers generated so far (within this video + history)
        current_answers = used_answers + [r.answer for r in all_rounds]

        prompt = f"""You are a kids quiz content generator creating a SPEED QUIZ video.
Generate exactly {rounds_per_tier} quiz questions about {cat_info['prompt_hint']}.

DIFFICULTY: {difficulty} — {difficulty_desc[difficulty]}

RULES:
- Each answer must be a specific, recognizable {cat_info['display'].lower()}
- Fun facts must be kid-appropriate, surprising, and under 15 words
- hint_question should be a playful clue (not the answer itself)
- pexels_search must be a good search term for finding a real photo on Pexels
  (e.g., for "Bengal Tiger" use "bengal tiger close up", for "Kangaroo" use "kangaroo")
- NEVER use any of these previously used answers: {json.dumps(current_answers[-300:])}

Return ONLY valid JSON:
{{
  "rounds": [
    {{
      "answer": "Lion",
      "hint_question": "This animal is called the king of the jungle!",
      "fun_fact": "Lions can sleep up to 20 hours a day!",
      "difficulty": "{difficulty.lower()}",
      "pexels_search": "lion close up portrait"
    }}
  ]
}}"""

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        # Parse this tier's rounds
        tier_pack = parse_quiz_response(response.text, category)
        for r in tier_pack.rounds:
            r.difficulty = difficulty.lower()
        all_rounds.extend(tier_pack.rounds)

        print(f"[QUIZ] Generated {len(tier_pack.rounds)} {difficulty} rounds")

    # Build final pack with all rounds in difficulty order
    pack = QuizPack(category=category, rounds=all_rounds)

    # Update history with all new answers
    history = update_history(history, pack)
    # Track video generation metadata for never-repeat videos
    if "video_log" not in history:
        history["video_log"] = []
    history["video_log"].append({
        "date": datetime.now().isoformat(),
        "category": category,
        "format": "speed",
        "num_rounds": len(all_rounds),
        "answers": [r.answer for r in all_rounds],
    })
    save_history(history)

    return pack
