# speed_narration.py
# ============================================================
# Cheerful voiceover system for speed quiz format.
# Every video gets DIFFERENT wording in the same energetic style
# so it never sounds robotic or repetitive across daily uploads.
#
# Uses Gemini to generate fresh scripts per video, then
# ElevenLabs to voice them with energetic kid-friendly delivery.
#
# Script structure per video:
# 1. Intro hype (unique opener)
# 2. Subscribe prompt (varied CTA)
# 3. 4 section transition lines (one per difficulty)
# 4. 120 answer reveal lines — one per round ("It's a Lion!")
# 5. ~12 cheering reactions spread across 120 rounds
# 6. Outro celebration (unique closer)
#
# Total: ~140 narration clips per video.
# Gemini generates ~20 varied phrase templates, then each round
# gets a random template with the answer filled in — so "Lion"
# might get "It's a Lion!" while "Eagle" gets "Eagle! How cool!"
# All cached in output dir — unique per video, reusable on re-render.
# ============================================================
import json
import re
import random
from pathlib import Path
from dataclasses import dataclass, field

import config


@dataclass
class SpeedNarrationPack:
    """# All voiceover clips and scripts for one speed quiz video."""
    intro_path: Path = None           # "Can you guess 120 animals in 3 seconds?"
    subscribe_path: Path = None       # "Subscribe before we start!"
    section_paths: dict = field(default_factory=dict)  # {"EASY": Path, "MEDIUM": Path, ...}
    # Per-round answer reveal clips — voice says the answer on every round
    round_reveal_paths: list[Path] = field(default_factory=list)  # 120 paths
    reaction_paths: list[Path] = field(default_factory=list)  # ~12 cheering clips
    outro_path: Path = None           # "How many did you get right?"
    # The actual script text (for subtitles/debugging)
    script: dict = field(default_factory=dict)


def generate_speed_script(category: str, num_rounds: int = 120) -> dict:
    """
    # Generate a FRESH cheerful voiceover script using Gemini.
    # Includes ~20 answer reveal templates so each round sounds different.
    # Every video gets different wording — never repetitive.
    """
    from google import genai

    cat_display = config.CATEGORIES[category]["display"]

    prompt = f"""You are writing a voiceover script for Leo — a cute lion cub mascot who hosts
a kids quiz YouTube channel called "Leo Quiz". Leo is the BRAND AMBASSADOR and HOST.
He speaks in first person, is cheerful, energetic, and talks directly to the viewer like a friend.

The video is "Guess {num_rounds} {cat_display}s in 3 Seconds" — a speed quiz for kids.
Leo is the one presenting every question and announcing every answer on camera.

Generate a FRESH, UNIQUE script where Leo speaks AS HIMSELF (first person).
He should sound like a real kids YouTuber — excited, encouraging, fun, with his own personality.
He introduces himself by name at least once in the intro.

IMPORTANT: Leo is a character. He should say "I" and "me", not narrate in third person.
Keep lines SHORT and punchy — these play over fast-paced quiz rounds.

Return ONLY valid JSON:
{{
  "intro": "Leo's energetic opening (10-15 words). He says hi, hypes the challenge. Example energy: 'Hey everyone, I'm Leo! Can you guess {num_rounds} {cat_display.lower()}s in just 3 seconds?'",
  "subscribe": "Leo's fun subscribe ask (8-12 words). Playful, not pushy. Example: 'Hit that subscribe button for me before we start!'",
  "sections": {{
    "EASY": "Leo encouraging the viewer for easy level (8-12 words). Example: 'Alright, let's warm up! These ones are easy, I promise!'",
    "MEDIUM": "Leo acknowledging it's getting harder (8-12 words). Example: 'Okay okay, now it gets a bit trickier! Ready?'",
    "HARD": "Leo hyping up the hard level (8-12 words). Example: 'Woah, hard mode! Only true champions get these right!'",
    "IMPOSSIBLE": "Leo's dramatic impossible level intro (8-12 words). Example: 'The IMPOSSIBLE round! Even I struggle with these ones!'"
  }},
  "reveal_templates": [
    "20 different SHORT phrases Leo uses to announce answers. Use {{answer}} as placeholder.",
    "Leo speaks in first person — he's revealing the answer to the viewer.",
    "Keep each 2-6 words. Examples: 'It's a {{answer}}!', '{{answer}}! I love those!', 'That's a {{answer}}!', 'Boom, {{answer}}!', '{{answer}}! Did you get it?', 'Yep, {{answer}}!', 'A {{answer}}! So cool right?', '{{answer}}! Amazing!', 'It was a {{answer}}!', '{{answer}}! I knew you'd get that!'",
    "IMPORTANT: Every template MUST contain {{answer}} exactly once. No two should feel the same."
  ],
  "reactions": [
    "12 different short reactions from Leo (2-5 words each). He's cheering the viewer on.",
    "Mix: celebrating, encouraging, amazement, hype. Examples: 'You got it!', 'No way, that was tough!', 'You're on fire!', 'Ooh tricky one!', 'I'm impressed!', 'Nice one!'"
  ],
  "outro": "Leo's celebratory closing (12-18 words). He congratulates the viewer, mentions their score, asks them to subscribe. Sounds genuinely impressed and grateful."
}}

Make Leo sound NATURAL — like a real character talking, not a script being read.
Vary sentence structure. Use contractions. Give Leo a warm, playful personality."""

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # Parse JSON response
    text = response.text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    script = json.loads(text)

    # Ensure reactions is a flat list of strings
    reactions = script.get("reactions", [])
    if reactions and isinstance(reactions[0], list):
        reactions = reactions[0]
    script["reactions"] = reactions

    # Ensure reveal_templates is a flat list of strings with {answer}
    templates = script.get("reveal_templates", [])
    if templates and isinstance(templates[0], list):
        templates = templates[0]
    # Filter to only valid templates that contain {answer}
    valid_templates = [t for t in templates
                       if isinstance(t, str) and "{answer}" in t]
    # Fallback templates in case Gemini returns bad ones
    if len(valid_templates) < 5:
        valid_templates = [
            "It's a {answer}!", "{answer}! Amazing!", "That's a {answer}!",
            "Boom, {answer}!", "{answer}! Wow!", "A {answer}! So cool!",
            "Yep, it's {answer}!", "{answer}! Did you get it?",
            "{answer}! Nice one!", "It was {answer}!",
            "{answer}! How cool is that!", "That's right, {answer}!",
            "{answer}! Awesome!", "Look, it's a {answer}!",
            "{answer}! You got it!", "A {answer}! Love it!",
            "{answer}! Super cool!", "It's {answer}! Easy right?",
            "{answer}! Fantastic!", "Whoa, {answer}!",
        ]
    script["reveal_templates"] = valid_templates

    return script


def _generate_voice_clip(text: str, output_path: Path) -> Path:
    """
    # Generate one voice clip via ElevenLabs.
    # Uses tuned settings for energetic, kid-friendly delivery.
    """
    if not config.ELEVENLABS_API_KEY or not config.ELEVENLABS_VOICE_ID:
        print(f"[NARRATION] No ElevenLabs config — skipping: {text[:40]}...")
        return None

    from elevenlabs import ElevenLabs
    import base64

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Skip if already generated (for re-runs)
    if output_path.exists():
        return output_path

    try:
        client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

        response = client.text_to_speech.convert_with_timestamps(
            text=text,
            voice_id=config.ELEVENLABS_VOICE_ID,
            model_id="eleven_multilingual_v2",
            voice_settings={
                "stability": config.ELEVENLABS_STABILITY,
                "similarity_boost": config.ELEVENLABS_SIMILARITY_BOOST,
                "style": config.ELEVENLABS_STYLE,
                "use_speaker_boost": config.ELEVENLABS_USE_SPEAKER_BOOST,
            },
        )

        audio_bytes = b""
        for chunk in response:
            if hasattr(chunk, "audio_base64") and chunk.audio_base64:
                audio_bytes += base64.b64decode(chunk.audio_base64)

        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        print(f"[NARRATION] Generated: {text[:50]}...")
        return output_path

    except Exception as e:
        print(f"[NARRATION] Failed to generate '{text[:40]}': {e}")
        return None


def _generate_round_reveals(answers: list[str], templates: list[str],
                            narration_dir: Path) -> list[Path]:
    """
    # Generate a voice clip for each round's answer reveal.
    # Picks a random template for each answer so no two rounds
    # sound the same — "It's a Lion!" vs "Eagle! Wow!" vs "Boom, Tiger!"
    # Caches on disk so re-runs skip already-generated clips.
    """
    reveals_dir = narration_dir / "reveals"
    reveals_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    # Shuffle templates to avoid predictable patterns
    template_cycle = list(templates)
    random.shuffle(template_cycle)

    for i, answer in enumerate(answers):
        # Pick template — cycle through shuffled list so we use all of them
        template = template_cycle[i % len(template_cycle)]
        text = template.format(answer=answer)

        output_path = reveals_dir / f"reveal_{i:03d}.mp3"
        path = _generate_voice_clip(text, output_path)
        paths.append(path)

        # Progress update every 20 rounds
        if (i + 1) % 20 == 0:
            print(f"[NARRATION]   Voiced {i + 1}/{len(answers)} answer reveals...")

    return paths


def generate_speed_narration(category: str, output_dir: Path,
                              num_rounds: int = 120,
                              answers: list[str] = None) -> SpeedNarrationPack:
    """
    # Generate ALL voiceover clips for a speed quiz video.
    # Step 1: Gemini generates a fresh script with varied templates
    # Step 2: ElevenLabs voices structure clips (intro/subscribe/sections/reactions/outro)
    # Step 3: ElevenLabs voices each round's answer reveal using random templates
    #
    # Total clips: ~140 (7 structure + ~12 reactions + 120 reveals)
    # answers: list of answer strings for all rounds (e.g. ["Lion", "Eagle", ...])
    """
    narration_dir = output_dir / "narration"
    narration_dir.mkdir(parents=True, exist_ok=True)

    pack = SpeedNarrationPack()

    # Step 1: Generate fresh script via Gemini
    print("[NARRATION] Generating fresh voiceover script...")
    script = generate_speed_script(category, num_rounds)
    pack.script = script

    # Save script to disk for reference
    script_path = narration_dir / "script.json"
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)

    # Step 2: Voice structure clips via ElevenLabs

    # Intro
    print("[NARRATION] Voicing intro...")
    pack.intro_path = _generate_voice_clip(
        script["intro"], narration_dir / "intro.mp3"
    )

    # Subscribe prompt
    print("[NARRATION] Voicing subscribe prompt...")
    pack.subscribe_path = _generate_voice_clip(
        script["subscribe"], narration_dir / "subscribe.mp3"
    )

    # Section transitions
    print("[NARRATION] Voicing section transitions...")
    for difficulty, line in script.get("sections", {}).items():
        path = _generate_voice_clip(
            line, narration_dir / f"section_{difficulty.lower()}.mp3"
        )
        pack.section_paths[difficulty] = path

    # Cheering reactions (12 clips)
    print("[NARRATION] Voicing cheering reactions...")
    reactions = script.get("reactions", [])
    for i, reaction in enumerate(reactions):
        if isinstance(reaction, str) and reaction.strip():
            path = _generate_voice_clip(
                reaction, narration_dir / f"reaction_{i}.mp3"
            )
            if path:
                pack.reaction_paths.append(path)

    # Outro
    print("[NARRATION] Voicing outro...")
    pack.outro_path = _generate_voice_clip(
        script["outro"], narration_dir / "outro.mp3"
    )

    # Step 3: Voice every round's answer reveal
    if answers:
        print(f"[NARRATION] Voicing {len(answers)} answer reveals...")
        templates = script.get("reveal_templates", [])
        pack.round_reveal_paths = _generate_round_reveals(
            answers, templates, narration_dir
        )

    clip_count = sum(1 for x in [
        pack.intro_path, pack.subscribe_path, pack.outro_path
    ] if x) + len(pack.section_paths) + len(pack.reaction_paths) + \
        len(pack.round_reveal_paths)

    print(f"[NARRATION] Generated {clip_count} voice clips for this video")
    return pack
