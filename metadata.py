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


def save_metadata(metadata: dict, output_path: Path) -> Path:
    """# Save metadata dict to JSON file for upload reference."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    return output_path
