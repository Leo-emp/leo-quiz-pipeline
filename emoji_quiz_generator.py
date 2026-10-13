# emoji_quiz_generator.py
# ============================================================
# Emoji Quiz content generation using Gemini Flash.
# Generates "Guess the X by Emoji" quiz packs where 2-3 emoji
# serve as clues for the answer.
#
# FORMAT: Monkey Quiz style (18M+ views per video)
#   - 2-3 emoji displayed as clues (e.g., 🌮 + 🔔 = Taco Bell)
#   - 40 rounds across 4 difficulty tiers
#   - Categories: animals, food, restaurants, candy, countries, movies, sports
#
# Each round has:
#   - answer: the thing to guess (e.g., "Dolphin")
#   - emoji_clues: list of 2-3 emoji (e.g., ["🐬", "🌊"])
#   - fun_fact: short fun fact for the reveal phase
#   - difficulty: easy/medium/hard/impossible
# ============================================================
import json
import re
import time as _time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import config
from quiz_generator import _gemini_with_retry, load_history, save_history


@dataclass
class EmojiQuizRound:
    """# One emoji quiz question with emoji clues and answer."""
    answer: str                    # The answer (e.g., "Dolphin")
    emoji_clues: list[str]         # 2-3 emoji characters (e.g., ["🐬", "🌊"])
    fun_fact: str                  # Surprising fact under 15 words
    difficulty: str                # "easy", "medium", "hard", or "impossible"


@dataclass
class EmojiQuizPack:
    """# A complete set of emoji quiz rounds for one video."""
    category: str                  # Which emoji category (animals, food, etc.)
    rounds: list[EmojiQuizRound] = field(default_factory=list)


def generate_emoji_quiz_pack(category: str,
                              num_rounds: int = None) -> EmojiQuizPack:
    """
    # Generate an emoji quiz pack with rounds across 4 difficulty tiers.
    # Each tier has num_rounds/4 rounds: Easy → Medium → Hard → Impossible.
    # Generates in 4 batches to stay within Gemini output limits.
    #
    # Args:
    #   category: one of the EMOJI_CATEGORIES keys (animals, food, etc.)
    #   num_rounds: total number of rounds (default from config)
    #
    # Returns:
    #   EmojiQuizPack with all rounds in difficulty order
    """
    from google import genai

    if num_rounds is None:
        num_rounds = config.EMOJI_ROUNDS

    # --- Load history to avoid repeating past answers ---
    history = load_history()
    emoji_history_key = f"emoji_{category}"
    used_answers = history.get(emoji_history_key, [])

    # --- Get category info for prompt ---
    cat_info = config.EMOJI_CATEGORIES.get(category, {
        "display": category.upper(),
        "prompt_hint": f"{category} items",
    })

    # --- Build the quiz in batches (one per difficulty tier) ---
    # Proportional scaling when total rounds < config sum (e.g. --rounds 4)
    all_rounds = []
    rpd = config.EMOJI_ROUNDS_PER_DIFFICULTY
    tier_round_counts = {}
    if isinstance(rpd, dict):
        total_config = sum(rpd.get(d, 10) for d in config.EMOJI_DIFFICULTIES)
        assigned = 0
        for i, d in enumerate(config.EMOJI_DIFFICULTIES):
            if i == len(config.EMOJI_DIFFICULTIES) - 1:
                tier_round_counts[d] = num_rounds - assigned
            else:
                tier_round_counts[d] = round(num_rounds * rpd.get(d, 10) / total_config)
                assigned += tier_round_counts[d]
    else:
        for d in config.EMOJI_DIFFICULTIES:
            tier_round_counts[d] = num_rounds // len(config.EMOJI_DIFFICULTIES)

    for difficulty in config.EMOJI_DIFFICULTIES:
        rounds_per_tier = tier_round_counts.get(difficulty, 0)
        if rounds_per_tier <= 0:
            continue
        # --- Describe what each difficulty tier means ---
        difficulty_desc = {
            "EASY": "very common, everyday items that most 5-year-olds would recognize instantly from emoji",
            "MEDIUM": "recognizable but less common items that most 8-year-olds would get",
            "HARD": "uncommon items that would challenge a 12-year-old, emoji clues are trickier",
            "IMPOSSIBLE": "rare or obscure items that would stump most adults, emoji clues are abstract",
        }

        # --- Collect all answers generated so far (within this video + history) ---
        current_answers = used_answers + [r.answer for r in all_rounds]

        prompt = f"""You are generating content for a "Guess the {cat_info['display']} by Emoji" quiz video.
Generate exactly {rounds_per_tier} quiz questions about {cat_info['prompt_hint']}.

DIFFICULTY: {difficulty} — {difficulty_desc[difficulty]}

CRITICAL — WORDPLAY CLUES:
The emoji must represent SYLLABLES or SOUNDS of the answer word, NOT the answer itself.
This is a word puzzle! Viewers decode the answer by combining what each emoji represents.

EXAMPLES OF CORRECT WORDPLAY:
- "Hamster" → 🐷⭐ (ham + star → hamster)
- "Butterfly" → 🧈🪰 (butter + fly → butterfly)
- "Seahorse" → 🌊🐴 (sea + horse → seahorse)
- "Jellyfish" → 🍇🐟 (jelly + fish → jellyfish)
- "Sunflower" → ☀️🌺 (sun + flower → sunflower)
- "Pineapple" → 🌲🍎 (pine + apple → pineapple)
- "Taco Bell" → 🌮🔔 (taco + bell → Taco Bell)
- "Starbucks" → ⭐🦌 (star + bucks → Starbucks)

RULES:
- Each answer must be a specific, recognizable {cat_info['display'].lower()}
- emoji_clues must be exactly 2 or 3 emoji characters that represent PARTS of the word
  - Break the answer word into syllables or component words
  - Find an emoji that sounds like each syllable/part
  - For harder difficulties, the sound matches are more abstract
  - Each emoji must be a SINGLE emoji character (no text, no modifiers)
  - NEVER use the emoji that directly represents the answer (no 🐬 for dolphin!)
- fun_fact must be kid-appropriate, surprising, and under 15 words
- NEVER use any of these previously used answers: {json.dumps(current_answers[-300:])}

Return ONLY valid JSON:
{{
  "rounds": [
    {{
      "answer": "Hamster",
      "emoji_clues": ["🐷", "⭐"],
      "fun_fact": "Hamsters can run 5 miles on their wheel each night!",
      "difficulty": "{difficulty.lower()}"
    }},
    {{
      "answer": "Butterfly",
      "emoji_clues": ["🧈", "🪰"],
      "fun_fact": "Butterflies taste with their feet!",
      "difficulty": "{difficulty.lower()}"
    }}
  ]
}}"""

        # --- Call Gemini with retry on 503 ---
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        response = _gemini_with_retry(client, prompt)

        # --- Parse the JSON response ---
        tier_rounds = _parse_emoji_response(response.text, difficulty)
        all_rounds.extend(tier_rounds)

        print(f"[EMOJI QUIZ] Generated {len(tier_rounds)} {difficulty} rounds")

    # --- Build final pack with all rounds in difficulty order ---
    pack = EmojiQuizPack(category=category, rounds=all_rounds)

    # --- Update history with all new answers ---
    if emoji_history_key not in history:
        history[emoji_history_key] = []
    existing = set(history[emoji_history_key])
    for r in all_rounds:
        if r.answer not in existing:
            history[emoji_history_key].append(r.answer)
            existing.add(r.answer)

    # --- Track video generation metadata ---
    if "video_log" not in history:
        history["video_log"] = []
    history["video_log"].append({
        "date": datetime.now().isoformat(),
        "category": f"emoji_{category}",
        "format": "emoji",
        "num_rounds": len(all_rounds),
        "answers": [r.answer for r in all_rounds],
    })
    save_history(history)

    return pack


def _parse_emoji_response(raw_json: str, difficulty: str) -> list[EmojiQuizRound]:
    """
    # Parse Gemini's JSON response into a list of EmojiQuizRound.
    # Handles JSON wrapped in markdown code fences.
    """
    # --- Strip markdown code fences if present ---
    cleaned = raw_json.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    data = json.loads(cleaned)

    rounds = []
    for r in data.get("rounds", []):
        emoji_clues = r.get("emoji_clues", [])
        # --- Validate: must have 2-3 emoji ---
        if len(emoji_clues) < 2:
            emoji_clues = emoji_clues + ["❓"] * (2 - len(emoji_clues))
        elif len(emoji_clues) > 3:
            emoji_clues = emoji_clues[:3]

        rounds.append(EmojiQuizRound(
            answer=r["answer"],
            emoji_clues=emoji_clues,
            fun_fact=r.get("fun_fact", ""),
            difficulty=difficulty.lower(),
        ))

    return rounds


def serialize_emoji_pack(pack: EmojiQuizPack) -> dict:
    """# Serialize EmojiQuizPack to dict for JSON caching."""
    return {
        "category": pack.category,
        "format": "emoji",
        "rounds": [
            {
                "answer": r.answer,
                "emoji_clues": r.emoji_clues,
                "fun_fact": r.fun_fact,
                "difficulty": r.difficulty,
            }
            for r in pack.rounds
        ]
    }


def deserialize_emoji_pack(data: dict) -> EmojiQuizPack:
    """# Deserialize cached JSON back into EmojiQuizPack."""
    pack = EmojiQuizPack(category=data.get("category", "animals"))
    for rd in data.get("rounds", []):
        pack.rounds.append(EmojiQuizRound(
            answer=rd["answer"],
            emoji_clues=rd.get("emoji_clues", ["❓", "❓"]),
            fun_fact=rd.get("fun_fact", ""),
            difficulty=rd.get("difficulty", "medium"),
        ))
    return pack
