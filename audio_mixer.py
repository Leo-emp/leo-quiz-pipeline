# audio_mixer.py
# ============================================================
# Audio assembly for Leo Quiz videos.
# Mixes voice narration, sound effects, and background music
# into a single audio track with proper volume levels.
# Uses pydub for audio manipulation and layering.
# ============================================================
import math
from pathlib import Path
from pydub import AudioSegment

import config


def normalize_audio(audio_path: Path, target_db: float = None) -> Path:
    """
    # Normalize an audio file to the target peak dB.
    # Adjusts volume so peak loudness matches target.
    # Overwrites the file in place. Returns the path.
    """
    if target_db is None:
        target_db = config.AUDIO_PEAK_DB

    audio = AudioSegment.from_file(str(audio_path))
    # Calculate gain needed to reach target peak
    change_in_db = target_db - audio.max_dBFS
    normalized = audio.apply_gain(change_in_db)
    normalized.export(str(audio_path), format=audio_path.suffix.lstrip("."))
    return audio_path


def mix_layers(layers: list[tuple[Path, int, float]],
               total_duration_ms: int,
               output_path: Path) -> Path:
    """
    # Mix multiple audio layers into one output file.
    # layers: list of (audio_path, start_offset_ms, volume_multiplier)
    # volume_multiplier: 1.0 = full volume, 0.2 = 20%, etc.
    # Creates a silent base track and overlays each layer at its offset.
    """
    # Create silent base track of total duration
    mixed = AudioSegment.silent(duration=total_duration_ms)

    for audio_path, offset_ms, volume in layers:
        # Skip missing files gracefully
        if not Path(audio_path).exists():
            continue
        clip = AudioSegment.from_file(str(audio_path))

        # Apply volume adjustment (convert multiplier to dB)
        if volume < 1.0:
            db_change = 20 * math.log10(max(volume, 0.01))
            clip = clip.apply_gain(db_change)

        # Overlay at the specified time offset
        mixed = mixed.overlay(clip, position=offset_ms)

    # Normalize final mix to target peak
    if mixed.max_dBFS > -100:  # Only normalize if not pure silence
        change_in_db = config.AUDIO_PEAK_DB - mixed.max_dBFS
        mixed = mixed.apply_gain(change_in_db)

    # Export mixed audio
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mixed.export(str(output_path), format="wav")
    return output_path


def build_short_audio(round_audios: list, music_path: Path,
                       total_duration: float,
                       output_path: Path) -> Path:
    """
    # Build complete audio track for a short-form video.
    # Layers: background music (continuous, ducked to 18%) +
    # voice clips + SFX placed at correct timestamps per round timing.
    """
    total_ms = int(total_duration * 1000)
    layers = []

    # Background music (looping, 18% volume — ducked under voice)
    if music_path and music_path.exists():
        music = AudioSegment.from_file(str(music_path))
        # Loop music to fill total duration
        loops_needed = (total_ms // len(music)) + 1
        looped_music = music * loops_needed
        looped_path = output_path.parent / "looped_music.wav"
        looped_music[:total_ms].export(str(looped_path), format="wav")
        layers.append((looped_path, 0, 0.18))

    # Intro jingle SFX
    if config.SFX_FILES["jingle_intro"].exists():
        layers.append((config.SFX_FILES["jingle_intro"], 0, 0.7))

    # Per-round audio placement based on timing spec
    for i, ra in enumerate(round_audios):
        # Calculate round start time in milliseconds
        round_start_ms = int((config.INTRO_DURATION + i * config.ROUND_DURATION) * 1000)

        # Question voice at round start
        layers.append((ra.question_path, round_start_ms, 1.0))

        # Tick SFX at each countdown second (3, 2, 1)
        for sec in range(config.COUNTDOWN_SECONDS):
            tick_ms = round_start_ms + int((config.COUNTDOWN_START + sec) * 1000)
            if config.SFX_FILES["tick"].exists():
                layers.append((config.SFX_FILES["tick"], tick_ms, 0.6))

        # Ding SFX + reveal voice at reveal time
        reveal_ms = round_start_ms + int(config.REVEAL_START * 1000)
        if config.SFX_FILES["ding"].exists():
            layers.append((config.SFX_FILES["ding"], reveal_ms, 0.8))
        layers.append((ra.reveal_path, reveal_ms, 1.0))

        # Fun fact voice at fact time
        fact_ms = round_start_ms + int(config.FUN_FACT_START * 1000)
        layers.append((ra.fact_path, fact_ms, 1.0))

        # Whoosh transition SFX near end of round
        transition_ms = round_start_ms + int(config.TRANSITION_START * 1000)
        if config.SFX_FILES["whoosh"].exists():
            layers.append((config.SFX_FILES["whoosh"], transition_ms, 0.5))

    # Outro jingle SFX
    outro_ms = total_ms - int(config.OUTRO_DURATION * 1000)
    if config.SFX_FILES["jingle_outro"].exists():
        layers.append((config.SFX_FILES["jingle_outro"], outro_ms, 0.7))

    # Mix all layers into final output
    return mix_layers(layers, total_ms, output_path)
