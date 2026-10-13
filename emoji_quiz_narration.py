# emoji_quiz_narration.py
# ============================================================
# Voiceover narration for Emoji Quiz format.
# Generates ElevenLabs voice clips for every round:
#
# Structure:
#   - Intro: "Oh no! Leo mixed all the [category] into emojis!
#             Can you figure them out? Subscribe and let's go!"
#   - Per-round question: "Can you guess this [category]?"
#                         (with variations to stay interesting)
#   - Per-round reveal: "That's right! It's a [answer]!"
#                       (with varied excited reactions)
#   - Section card: "Easy level! Let's start simple!"
#   - Outro: "Amazing job! You got [score] out of [total]!
#            Subscribe for more emoji quizzes!"
#
# Uses Gemini to generate varied phrase templates so every
# round sounds slightly different (not robotic repetition).
# ============================================================
import json
import os
import re
import time as _time
from dataclasses import dataclass, field
from pathlib import Path

import config
from quiz_generator import _gemini_with_retry


@dataclass
class EmojiNarrationPack:
    """# All voiceover clips and scripts for one emoji quiz video."""
    intro_path: Path = None               # "Leo mixed all the animals into emojis!"
    subscribe_path: Path = None            # "Subscribe and let's go!"
    section_paths: dict = field(default_factory=dict)  # {difficulty: Path}
    question_paths: list[Path] = field(default_factory=list)  # per-round "Can you guess?"
    reveal_paths: list[Path] = field(default_factory=list)    # per-round "It's a [X]!"
    outro_path: Path = None                # "Amazing job! Subscribe!"
    # Script text for speech bubbles / word-by-word subtitles
    script: dict = field(default_factory=dict)
    # --- Duration tracking (seconds) to prevent overlap ---
    intro_duration: float = 0.0            # actual length of intro voice clip
    subscribe_duration: float = 0.0        # actual length of subscribe clip
    section_durations: dict = field(default_factory=dict)  # {difficulty: seconds}
    question_durations: list[float] = field(default_factory=list)  # per-round
    reveal_durations: list[float] = field(default_factory=list)    # per-round
    outro_duration: float = 0.0
    # --- Script text per clip (for word-by-word subtitles) ---
    intro_text: str = ""
    subscribe_text: str = ""
    section_texts: dict = field(default_factory=dict)  # {difficulty: text}
    question_texts: list[str] = field(default_factory=list)
    reveal_texts: list[str] = field(default_factory=list)
    outro_text: str = ""


def _get_clip_duration(path: Path) -> float:
    """
    # Measure the duration of an audio clip in seconds.
    # Uses pydub to read the file and return length.
    """
    if path and path.exists() and path.stat().st_size > 1000:
        try:
            from pydub import AudioSegment
            clip = AudioSegment.from_file(str(path))
            return len(clip) / 1000.0  # ms to seconds
        except Exception:
            pass
    return 0.0


def _generate_voice_clip(text: str, output_path: Path) -> Path:
    """
    # Generate a single ElevenLabs voice clip.
    # Uses the same voice ID and settings as the main pipeline.
    """
    import urllib.request

    api_key = config.ELEVENLABS_API_KEY
    voice_id = config.ELEVENLABS_VOICE_ID

    if not api_key or not voice_id:
        print(f"[EMOJI NARR] ElevenLabs not configured — skipping: {text[:40]}...")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = json.dumps({
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": config.ELEVENLABS_STABILITY,
            "similarity_boost": config.ELEVENLABS_SIMILARITY_BOOST,
            "style": config.ELEVENLABS_STYLE,
            "use_speaker_boost": config.ELEVENLABS_USE_SPEAKER_BOOST,
        }
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    })

    try:
        response = urllib.request.urlopen(req, timeout=30)
        with open(output_path, "wb") as f:
            f.write(response.read())
        return output_path
    except Exception as e:
        print(f"[EMOJI NARR] Voice gen failed: {e}")
        return None


def generate_emoji_narration(category: str, output_dir: Path,
                              num_rounds: int, answers: list[str]
                              ) -> EmojiNarrationPack:
    """
    # Generate all voiceover clips for an emoji quiz video.
    #
    # Steps:
    #   1. Use Gemini to generate varied phrase templates
    #   2. Generate intro + subscribe + section + outro voice clips
    #   3. Generate per-round question + reveal clips
    #
    # Caches clips in output_dir/narration/ for re-runs.
    """
    from google import genai

    narr_dir = output_dir / "narration"
    narr_dir.mkdir(parents=True, exist_ok=True)

    cat_info = config.EMOJI_CATEGORIES.get(category, {})
    display = cat_info.get("display", category).lower()

    pack = EmojiNarrationPack()

    # ================================================================
    # Step 1: Generate varied phrase templates via Gemini
    # ================================================================
    script_path = narr_dir / "script.json"
    if script_path.exists():
        with open(script_path, "r", encoding="utf-8") as f:
            script = json.load(f)
    else:
        prompt = f"""Generate SHORT voiceover scripts for a kids emoji quiz video about {display}s.

The host is Leo, a fun quiz host for children.

CRITICAL LENGTH RULES:
- section phrases: MAX 5 words each (e.g. "Easy level! Here we go!")
- question_templates: MAX 6 words each (e.g. "Can you guess this {display}?")
- reveal_templates: MAX 5 words each (e.g. "It's a {{answer}}!")
- subscribe: MAX 8 words
- intro: MAX 20 words
- outro: MAX 15 words

Generate these in JSON format:
{{
    "intro": "Leo mixed all the {display}s into emojis! Can you guess them all? Subscribe and let's go!",
    "subscribe": "Subscribe and hit that bell!",
    "sections": {{
        "EASY": "Easy level! Here we go!",
        "MEDIUM": "Medium level! Getting tricky!",
        "HARD": "Hard level! Good luck!",
        "IMPOSSIBLE": "Impossible level! Can you?"
    }},
    "question_templates": [
        "Can you guess this {display}?",
        "What {display} is this?",
        "Do you know this one?",
        "Tricky one! What {display}?",
        "What {display} is it?",
        "Can you figure it out?",
        "What do you think?",
        "Guess this {display}!"
    ],
    "reveal_templates": [
        "It's a {{answer}}!",
        "{{answer}}! Did you guess?",
        "{{answer}}! Great job!",
        "{{answer}}! How cool!",
        "It's a {{answer}}! Amazing!",
        "{{answer}}! Nice one!",
        "{{answer}}! Well done!",
        "{{answer}}! Awesome!"
    ],
    "outro": "Great job! Subscribe for more emoji quizzes!"
}}

KEEP EVERY PHRASE SHORT. Return ONLY valid JSON."""

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        response = _gemini_with_retry(client, prompt)

        # Parse JSON
        raw = response.text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        script = json.loads(raw)

        # Save for cache
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script, f, indent=2, ensure_ascii=False)

    pack.script = script

    # ================================================================
    # Step 2: Generate structural voice clips (intro, sections, outro)
    # Also measure each clip's duration to prevent overlap.
    # ================================================================

    # --- Intro ---
    intro_text = script.get("intro", "")
    pack.intro_text = intro_text
    intro_path = narr_dir / "intro.mp3"
    if intro_path.exists() and intro_path.stat().st_size > 1000:
        pack.intro_path = intro_path
    else:
        print(f"[EMOJI NARR] Generating intro voiceover...")
        pack.intro_path = _generate_voice_clip(intro_text, intro_path)
    pack.intro_duration = _get_clip_duration(pack.intro_path)

    # --- Subscribe ---
    sub_text = script.get("subscribe", "")
    pack.subscribe_text = sub_text
    sub_path = narr_dir / "subscribe.mp3"
    if sub_path.exists() and sub_path.stat().st_size > 1000:
        pack.subscribe_path = sub_path
    else:
        print(f"[EMOJI NARR] Generating subscribe voiceover...")
        pack.subscribe_path = _generate_voice_clip(sub_text, sub_path)
    pack.subscribe_duration = _get_clip_duration(pack.subscribe_path)

    # --- Section cards ---
    sections = script.get("sections", {})
    for diff in config.EMOJI_DIFFICULTIES:
        sec_text = sections.get(diff, f"{diff} level!")
        pack.section_texts[diff] = sec_text
        sec_path = narr_dir / f"section_{diff.lower()}.mp3"
        if sec_path.exists() and sec_path.stat().st_size > 1000:
            pack.section_paths[diff] = sec_path
        else:
            print(f"[EMOJI NARR] Generating {diff} section voiceover...")
            pack.section_paths[diff] = _generate_voice_clip(sec_text, sec_path)
        pack.section_durations[diff] = _get_clip_duration(pack.section_paths.get(diff))

    # --- Outro ---
    outro_text = script.get("outro", "")
    pack.outro_text = outro_text
    outro_path = narr_dir / "outro.mp3"
    if outro_path.exists() and outro_path.stat().st_size > 1000:
        pack.outro_path = outro_path
    else:
        print(f"[EMOJI NARR] Generating outro voiceover...")
        pack.outro_path = _generate_voice_clip(outro_text, outro_path)
    pack.outro_duration = _get_clip_duration(pack.outro_path)

    # ================================================================
    # Step 3: Generate per-round voice clips (question + reveal)
    # ================================================================
    question_templates = script.get("question_templates", [
        f"Can you guess this {display}?"])
    reveal_templates = script.get("reveal_templates", [
        "It's a {answer}!"])

    reveals_dir = narr_dir / "reveals"
    reveals_dir.mkdir(exist_ok=True)
    questions_dir = narr_dir / "questions"
    questions_dir.mkdir(exist_ok=True)

    for i, answer in enumerate(answers):
        # --- Question clip ---
        q_text = question_templates[i % len(question_templates)]
        pack.question_texts.append(q_text)

        q_path = questions_dir / f"question_{i+1}.mp3"
        if q_path.exists() and q_path.stat().st_size > 1000:
            pack.question_paths.append(q_path)
        else:
            print(f"[EMOJI NARR] Question {i+1}: {q_text[:40]}...")
            result = _generate_voice_clip(q_text, q_path)
            pack.question_paths.append(result or q_path)
        pack.question_durations.append(_get_clip_duration(
            pack.question_paths[-1]))

        # --- Reveal clip ---
        r_template = reveal_templates[i % len(reveal_templates)]
        try:
            r_text = r_template.format(answer=answer)
        except (KeyError, IndexError):
            r_text = f"It's a {answer}!"
        pack.reveal_texts.append(r_text)

        r_path = reveals_dir / f"reveal_{i+1}.mp3"
        if r_path.exists() and r_path.stat().st_size > 1000:
            pack.reveal_paths.append(r_path)
        else:
            print(f"[EMOJI NARR] Reveal {i+1}: {r_text[:40]}...")
            result = _generate_voice_clip(r_text, r_path)
            pack.reveal_paths.append(result or r_path)
        pack.reveal_durations.append(_get_clip_duration(
            pack.reveal_paths[-1]))

    # --- Summary ---
    total_intro = pack.intro_duration + pack.subscribe_duration
    print(f"[EMOJI NARR] Intro voice: {pack.intro_duration:.1f}s + "
          f"subscribe: {pack.subscribe_duration:.1f}s = {total_intro:.1f}s total")
    print(f"[EMOJI NARR] Generated {len(pack.question_paths)} question + "
          f"{len(pack.reveal_paths)} reveal clips")

    return pack


def load_cached_emoji_narration(output_dir: Path,
                                 num_rounds: int) -> EmojiNarrationPack:
    """# Load a previously generated narration pack from cache.
    # Also measures durations and extracts texts for subtitle rendering.
    """
    narr_dir = output_dir / "narration"
    pack = EmojiNarrationPack()

    # Script
    script_path = narr_dir / "script.json"
    if script_path.exists():
        with open(script_path, "r", encoding="utf-8") as f:
            pack.script = json.load(f)

    # --- Extract script texts ---
    pack.intro_text = pack.script.get("intro", "")
    pack.subscribe_text = pack.script.get("subscribe", "")
    pack.outro_text = pack.script.get("outro", "")
    sections = pack.script.get("sections", {})
    for diff in config.EMOJI_DIFFICULTIES:
        pack.section_texts[diff] = sections.get(diff, f"{diff} level!")

    # Structural clips + durations
    intro = narr_dir / "intro.mp3"
    if intro.exists():
        pack.intro_path = intro
        pack.intro_duration = _get_clip_duration(intro)
    sub = narr_dir / "subscribe.mp3"
    if sub.exists():
        pack.subscribe_path = sub
        pack.subscribe_duration = _get_clip_duration(sub)
    outro = narr_dir / "outro.mp3"
    if outro.exists():
        pack.outro_path = outro
        pack.outro_duration = _get_clip_duration(outro)

    for diff in config.EMOJI_DIFFICULTIES:
        sec = narr_dir / f"section_{diff.lower()}.mp3"
        if sec.exists():
            pack.section_paths[diff] = sec
            pack.section_durations[diff] = _get_clip_duration(sec)

    # Per-round clips + durations + texts
    question_templates = pack.script.get("question_templates", [
        "Can you guess this one?"])
    reveal_templates = pack.script.get("reveal_templates", [
        "It's a {answer}!"])

    for i in range(num_rounds):
        q = narr_dir / "questions" / f"question_{i+1}.mp3"
        pack.question_paths.append(q if q.exists() else None)
        pack.question_durations.append(_get_clip_duration(q))
        pack.question_texts.append(
            question_templates[i % len(question_templates)])

        r = narr_dir / "reveals" / f"reveal_{i+1}.mp3"
        pack.reveal_paths.append(r if r.exists() else None)
        pack.reveal_durations.append(_get_clip_duration(r))
        # Reveal text needs the actual answer — we don't have it here,
        # so leave empty; main pipeline fills it in
        pack.reveal_texts.append("")

    return pack
