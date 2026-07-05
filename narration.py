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


def generate_narration(text: str, output_path: Path) -> tuple[Path, list[dict]]:
    """
    # Generate speech audio from text using ElevenLabs.
    # Returns (audio_path, word_timestamps).
    # word_timestamps is a list of {"word", "start", "end"} dicts
    # used for synced text animation in the video.
    """
    from elevenlabs import ElevenLabs

    # Initialize ElevenLabs client
    client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

    # Generate with word-level timestamps for text sync
    response = client.text_to_speech.convert_with_timestamps(
        text=text,
        voice_id=config.ELEVENLABS_VOICE_ID,
        model_id="eleven_multilingual_v2",
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

    return RoundAudio(
        question_path=q_path,
        reveal_path=r_path,
        fact_path=f_path,
        fact_timestamps=f_timestamps,
    )
