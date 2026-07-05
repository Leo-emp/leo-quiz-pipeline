# narration.py
# ============================================================
# Voice narration generation using ElevenLabs.
# Generates individual audio clips per quiz round with
# word-level timestamps for synced text animation.
# ============================================================
from dataclasses import dataclass, field
from pathlib import Path

import config
from quiz_generator import QuizRound


@dataclass
class RoundAudio:
    """# All audio clips and timing data for one quiz round."""
    question_path: Path    # "What animal is this?" audio
    reveal_path: Path      # "It's a Lion!" audio
    fact_path: Path        # Fun fact narration audio
    fact_timestamps: list[dict] = field(default_factory=list)
    # Each timestamp: {"word": str, "start": float, "end": float}
    reaction_path: Path = None  # Short interjection ("Amazing!", "Let's go!")


# --- Varied narration phrases ---
# Top creators never repeat the same line every round.
# These rotate per round_index to keep kids engaged.

QUESTION_PHRASES = [
    "What {category} is this? Can you guess?",
    "Hmm, here's a tricky one! What {category} do you see?",
    "Take a close look! What {category} is hiding?",
    "Can you figure this one out? What {category} is it?",
    "Think carefully! What {category} could this be?",
]

REVEAL_PHRASES = [
    "It's a {answer}! Did you get it right?",
    "The answer is {answer}! Amazing!",
    "It's a {answer}! Great job if you guessed it!",
    "That's right, it's a {answer}! How cool is that?",
    "Wow, it's a {answer}! Did you know that one?",
]

# --- Reaction interjections ---
# Short energetic phrases played between rounds.
# Makes it feel like a real host reacting, not a text reader.
# These are pre-generated once and cached in assets/sfx/reactions/.
REACTION_PHRASES = [
    "Amazing!",
    "You're on fire!",
    "Let's keep going!",
    "Here comes the next one!",
    "Get ready!",
]


def generate_narration(text: str, output_path: Path) -> tuple[Path, list[dict]]:
    """
    # Generate speech audio from text using ElevenLabs.
    # UPGRADED: uses tuned voice_settings for energetic, expressive delivery.
    # Returns (audio_path, word_timestamps).
    # word_timestamps is a list of {"word", "start", "end"} dicts
    # used for synced text animation in the video.
    """
    from elevenlabs import ElevenLabs

    # Initialize ElevenLabs client
    client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

    # Voice settings tuned for kids content — expressive, clear, energetic
    voice_settings = {
        "stability": config.ELEVENLABS_STABILITY,
        "similarity_boost": config.ELEVENLABS_SIMILARITY_BOOST,
        "style": config.ELEVENLABS_STYLE,
        "use_speaker_boost": config.ELEVENLABS_USE_SPEAKER_BOOST,
    }

    # Generate with word-level timestamps for text sync
    response = client.text_to_speech.convert_with_timestamps(
        text=text,
        voice_id=config.ELEVENLABS_VOICE_ID,
        model_id="eleven_multilingual_v2",
        voice_settings=voice_settings,
    )

    # Collect audio bytes and word timestamps from streaming response
    audio_bytes = b""
    word_timestamps = []

    for chunk in response:
        # Collect audio data
        if hasattr(chunk, "audio_base64") and chunk.audio_base64:
            import base64
            audio_bytes += base64.b64decode(chunk.audio_base64)
        # Collect word-level timing data
        if hasattr(chunk, "alignment") and chunk.alignment:
            if hasattr(chunk.alignment, "words") and chunk.alignment.words:
                for w in chunk.alignment.words:
                    word_timestamps.append({
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                    })

    # Save audio file to disk
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    return output_path, word_timestamps


def _ensure_reaction(round_idx: int) -> Path:
    """
    # Generate a short reaction interjection clip if it doesn't exist.
    # Reactions are cached in assets/sfx/reactions/ and reused across videos.
    # Each round gets a different phrase (cycles through REACTION_PHRASES).
    # Returns the path to the reaction audio file, or None if generation fails.
    """
    reactions_dir = config.SFX_DIR / "reactions"
    reactions_dir.mkdir(parents=True, exist_ok=True)

    phrase_idx = round_idx % len(REACTION_PHRASES)
    reaction_path = reactions_dir / f"reaction_{phrase_idx}.mp3"

    # Already generated — reuse it
    if reaction_path.exists():
        return reaction_path

    # Generate via ElevenLabs (same voice, short clip)
    phrase = REACTION_PHRASES[phrase_idx]
    try:
        print(f"[NARRATION] Generating reaction: \"{phrase}\"")
        generate_narration(phrase, reaction_path)
        return reaction_path
    except Exception as e:
        print(f"[NARRATION] Could not generate reaction: {e}")
        return None


def generate_round_narration(round_data: QuizRound, category: str,
                              output_dir: Path) -> RoundAudio:
    """
    # Generate all narration clips for one quiz round.
    # Creates 3 audio files: question, reveal, and fun fact.
    # Returns RoundAudio with paths and timestamps.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    cat_display = config.CATEGORIES[category]["display"]

    # Pick varied question phrase based on round index (cycles through 5 variants)
    round_idx = getattr(round_data, '_round_index', 0)
    q_template = QUESTION_PHRASES[round_idx % len(QUESTION_PHRASES)]
    q_text = q_template.format(category=cat_display.lower())
    q_path, _ = generate_narration(q_text, output_dir / "question.mp3")

    # Pick varied reveal phrase (different from question rotation)
    r_template = REVEAL_PHRASES[round_idx % len(REVEAL_PHRASES)]
    r_text = r_template.format(answer=round_data.answer)
    r_path, _ = generate_narration(r_text, output_dir / "reveal.mp3")

    # Fun fact line (with timestamps for word-by-word animation)
    f_path, f_timestamps = generate_narration(
        round_data.fun_fact, output_dir / "fact.mp3"
    )

    # Generate reaction interjection for between rounds
    # Cached in shared reactions dir so we only generate each phrase once
    reaction_path = _ensure_reaction(round_idx)

    return RoundAudio(
        question_path=q_path,
        reveal_path=r_path,
        fact_path=f_path,
        fact_timestamps=f_timestamps,
        reaction_path=reaction_path,
    )
