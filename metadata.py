# metadata.py
# ============================================================
# Auto-generated video metadata (titles, descriptions, tags)
# using Gemini for SEO-optimized, platform-specific content.
# Generates metadata for all 4 platforms: YouTube, TikTok, Instagram, Facebook.
# ============================================================
import json
import re
from pathlib import Path

import config
from quiz_generator import QuizPack


def generate_metadata(quiz_pack: QuizPack, platform: str = "youtube") -> dict:
    """
    # Generate platform-optimized metadata for a quiz video.
    # Uses Gemini to create catchy titles, SEO descriptions, and tags.
    # Returns dict with title, description, tags, hashtags.
    """
    from google import genai

    category = quiz_pack.category
    cat_display = config.CATEGORIES[category]["display"]
    answers = [r.answer for r in quiz_pack.rounds]
    difficulties = [r.difficulty for r in quiz_pack.rounds]

    # Prompt Gemini for platform-specific metadata
    prompt = f"""Generate {platform} metadata for a kids quiz video.
Category: {cat_display}s
Answers featured: {', '.join(answers)}
Difficulty: {', '.join(difficulties)}
Format: Silhouette guess quiz with mascot "Leo the Lion"

Return ONLY JSON:
{{
  "title": "short catchy title under 60 chars, include emoji",
  "description": "SEO-optimized description with keywords, 2-3 sentences, include subscribe CTA",
  "tags": ["list", "of", "10-15", "relevant", "tags"],
  "hashtags": ["#hashtag1", "#hashtag2", "up to 5"]
}}

For YouTube: title should include "Guess the {cat_display}" and be kid-friendly.
For TikTok: title should be shorter, hashtag-heavy, max 150 chars.
For Instagram: caption should be engaging ('Can YOU guess all 6? 🤔 Comment your score!'), include up to 30 hashtags mixing broad and niche.
For Facebook: title should be shareable and parent-targeted ('How Many Animals Can Your Kids Guess? 🦁'), description encourages sharing, minimal hashtags.
Made for Kids content — keep everything family-friendly."""

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # Parse JSON response (handle code fences)
    text = response.text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    metadata = json.loads(text)

    # Add standard fields for COPPA compliance
    metadata["category"] = category
    metadata["made_for_kids"] = True
    metadata["answers"] = answers

    return metadata


def generate_speed_metadata(quiz_pack: QuizPack,
                             platform: str = "youtube") -> dict:
    """
    # Generate metadata for speed quiz using the PROVEN title formula.
    # Title pattern: "Guess 120 [Category] in 3 Seconds | Easy to Impossible"
    # This exact formula drives millions of views on Quiz Blitz.
    # No Gemini needed — deterministic titles are MORE reliable for SEO.
    """
    category = quiz_pack.category
    cat_display = config.CATEGORIES[category]["display"]
    num_rounds = len(quiz_pack.rounds)
    answers = [r.answer for r in quiz_pack.rounds]

    if platform == "youtube":
        title = f"Guess {num_rounds} {cat_display}s in 3 Seconds | Easy to Impossible"
        description = (
            f"Can you guess all {num_rounds} {cat_display.lower()}s in just 3 seconds each? "
            f"From EASY to IMPOSSIBLE - test your knowledge! 🧠\n\n"
            f"⏱️ You have only 3 SECONDS to guess each {cat_display.lower()}!\n"
            f"📊 Difficulty levels: Easy → Medium → Hard → Impossible\n\n"
            f"🕐 TIMESTAMPS:\n"
            f"0:00 Intro\n"
            f"0:10 EASY Level (1-30)\n"
            f"4:10 MEDIUM Level (31-60)\n"
            f"8:10 HARD Level (61-90)\n"
            f"12:10 IMPOSSIBLE Level (91-120)\n\n"
            f"💬 Comment how many YOU got right!\n"
            f"👍 Like & Subscribe for daily quizzes!\n\n"
            f"#quiz #guessthe{cat_display.lower()} #trivia #kids #challenge"
        )
        tags = [
            f"guess the {cat_display.lower()}", "quiz", "trivia",
            f"{cat_display.lower()} quiz", "guess in 3 seconds",
            "easy to impossible", "kids quiz", "family quiz",
            f"{cat_display.lower()} challenge", "brain teaser",
            "quiz game", "fun quiz", "guess the animal",
            "leo quiz", "speed quiz",
        ]
        hashtags = [
            f"#GuessThe{cat_display}", "#Quiz", "#Trivia",
            "#SpeedQuiz", "#KidsQuiz",
        ]
    elif platform == "tiktok":
        title = f"Guess {num_rounds} {cat_display}s in 3 Seconds! 🧠⏱️ #quiz #trivia"
        description = f"Can you guess them all? Easy to Impossible! Comment your score! 💬"
        tags = [f"{cat_display.lower()}quiz", "quiz", "trivia", "speedquiz", "challenge"]
        hashtags = ["#quiz", "#trivia", "#challenge", f"#{cat_display.lower()}quiz", "#fyp"]
    elif platform == "instagram":
        title = f"Guess {num_rounds} {cat_display}s in 3 Seconds! ⏱️"
        description = (
            f"Can YOU guess all {num_rounds}? 🤔 From Easy to IMPOSSIBLE!\n"
            f"Comment your score below! 💬\n\n"
            f"#quiz #trivia #{cat_display.lower()}quiz #challenge #speedquiz "
            f"#kidsquiz #familyfun #braingames #guessing #funfacts"
        )
        tags = ["quiz", "trivia", "challenge", "reels", "kids"]
        hashtags = [f"#{cat_display.lower()}quiz", "#quiz", "#trivia", "#reels", "#challenge"]
    else:
        title = f"How Many {cat_display}s Can You Guess in 3 Seconds? 🧠"
        description = (
            f"Challenge your family! {num_rounds} {cat_display.lower()}s from Easy to Impossible. "
            f"Share and comment your score!"
        )
        tags = ["quiz", "family", "challenge", "fun"]
        hashtags = ["#quiz", "#family", "#challenge"]

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "category": category,
        "made_for_kids": True,
        "answers": answers,
        "format": "speed",
    }


def save_metadata(metadata: dict, output_path: Path) -> Path:
    """# Save metadata dict to JSON file for upload reference."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    return output_path
