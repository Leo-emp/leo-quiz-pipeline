# audio_mixer.py
# ============================================================
# Audio assembly for Leo Quiz videos.
# UPGRADED: auto-generates SFX if missing, adds drumroll before
# reveal, correct chime on answer, countdown beeps alongside
# ticks, and applause on final round reveal.
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
    # Creates a silent base and overlays each layer at its offset.
    """
    mixed = AudioSegment.silent(duration=total_duration_ms)

    for audio_path, offset_ms, volume in layers:
        if not Path(audio_path).exists():
            continue
        clip = AudioSegment.from_file(str(audio_path))

        # Apply volume adjustment (multiplier → dB conversion)
        if volume < 1.0:
            db_change = 20 * math.log10(max(volume, 0.01))
            clip = clip.apply_gain(db_change)
        elif volume > 1.0:
            db_change = 20 * math.log10(volume)
            clip = clip.apply_gain(db_change)

        # Overlay at the specified time offset
        mixed = mixed.overlay(clip, position=offset_ms)

    # Normalize final mix to target peak
    if mixed.max_dBFS > -100:
        change_in_db = config.AUDIO_PEAK_DB - mixed.max_dBFS
        mixed = mixed.apply_gain(change_in_db)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mixed.export(str(output_path), format="wav")
    return output_path


def _duck_music_during_voice(music_path: Path, voice_regions: list[tuple[int, int]],
                             total_ms: int, output_path: Path,
                             normal_vol: float = 0.18,
                             ducked_vol: float = 0.08) -> Path:
    """
    # Dynamic music ducking: lower music volume during voice segments.
    # voice_regions: list of (start_ms, end_ms) when voice is playing.
    # This creates the professional "sidechain" effect heard in studio content.
    """
    music = AudioSegment.from_file(str(music_path))
    loops_needed = (total_ms // len(music)) + 1
    looped = music * loops_needed
    looped = looped[:total_ms]

    # Apply volume in chunks (50ms resolution for smooth ducking)
    chunk_ms = 50
    result = AudioSegment.silent(duration=0)

    for pos in range(0, total_ms, chunk_ms):
        chunk_end = min(pos + chunk_ms, total_ms)
        chunk = looped[pos:chunk_end]

        # Check if any voice region overlaps this chunk
        is_voice = any(start <= pos < end or start < chunk_end <= end
                       for start, end in voice_regions)

        vol = ducked_vol if is_voice else normal_vol
        if vol < 1.0:
            db_change = 20 * math.log10(max(vol, 0.01))
            chunk = chunk.apply_gain(db_change)
        result += chunk

    result.export(str(output_path), format="wav")
    return output_path


def build_short_audio(round_audios: list, music_path: Path,
                       total_duration: float,
                       output_path: Path) -> Path:
    """
    # Build complete audio track for a short-form video.
    # STUDIO-GRADE sound design with dynamic music ducking:
    #
    # Layer 1: Background music (dynamic ducking — louder between rounds,
    #          quieter during voice) for professional sidechain feel
    # Layer 2: Intro jingle
    # Layer 3: Per-round sounds:
    #   - Question voice narration (with varied phrases)
    #   - Tick + countdown beep on each countdown number
    #   - Drumroll building tension before reveal
    #   - Ding + correct chime on answer reveal (with reverb)
    #   - Reveal voice narration
    #   - Fun fact voice narration
    #   - Applause on final round reveal
    #   - Whoosh transition to next round
    # Layer 4: Outro jingle
    """
    total_ms = int(total_duration * 1000)
    layers = []
    num_rounds = len(round_audios)

    # Collect voice regions for dynamic ducking
    voice_regions = []
    for i, ra in enumerate(round_audios):
        round_start_ms = int((config.INTRO_DURATION + i * config.ROUND_DURATION) * 1000)
        # Question voice (~1.5s estimate)
        voice_regions.append((round_start_ms, round_start_ms + 2000))
        # Reveal voice
        reveal_ms = round_start_ms + int(config.REVEAL_START * 1000)
        voice_regions.append((reveal_ms, reveal_ms + 1500))
        # Fun fact voice
        fact_ms = round_start_ms + int(config.FUN_FACT_START * 1000)
        voice_regions.append((fact_ms, fact_ms + 2500))

    # --- Layer 1: Background music with dynamic ducking ---
    if music_path and music_path.exists():
        ducked_path = output_path.parent / "ducked_music.wav"
        _duck_music_during_voice(music_path, voice_regions, total_ms, ducked_path)
        layers.append((ducked_path, 0, 1.0))  # Already volume-adjusted

    # --- Layer 2: Intro jingle ---
    if config.SFX_FILES["jingle_intro"].exists():
        layers.append((config.SFX_FILES["jingle_intro"], 0, 0.75))

    # --- Layer 3: Per-round audio ---
    for i, ra in enumerate(round_audios):
        round_start_ms = int((config.INTRO_DURATION + i * config.ROUND_DURATION) * 1000)

        # Question voice at round start
        layers.append((ra.question_path, round_start_ms, 1.0))

        # Tick + countdown beep on each countdown second (3, 2, 1)
        for sec in range(config.COUNTDOWN_SECONDS):
            tick_ms = round_start_ms + int((config.COUNTDOWN_START + sec) * 1000)
            # Tick sound
            if config.SFX_FILES["tick"].exists():
                # Ticks get louder as countdown progresses (tension builds)
                tick_vol = 0.4 + 0.2 * (sec / config.COUNTDOWN_SECONDS)
                layers.append((config.SFX_FILES["tick"], tick_ms, tick_vol))
            # Countdown beep layered with tick for dramatic feel
            beep_path = config.SFX_FILES.get("countdown_beep")
            if beep_path and beep_path.exists():
                layers.append((beep_path, tick_ms, 0.3))

        # Drumroll building tension in the 2 seconds before reveal
        if config.SFX_FILES["drumroll"].exists():
            drumroll_start = round_start_ms + int((config.REVEAL_START - 1.5) * 1000)
            layers.append((config.SFX_FILES["drumroll"], drumroll_start, 0.35))

        # Ding + correct chime at reveal moment
        reveal_ms = round_start_ms + int(config.REVEAL_START * 1000)
        if config.SFX_FILES["ding"].exists():
            layers.append((config.SFX_FILES["ding"], reveal_ms, 0.85))
        # Correct chime layered with ding for "you got it!" feel
        correct_path = config.SFX_FILES.get("correct")
        if correct_path and correct_path.exists():
            layers.append((correct_path, reveal_ms + 100, 0.5))

        # Reveal voice narration
        layers.append((ra.reveal_path, reveal_ms, 1.0))

        # Fun fact voice
        fact_ms = round_start_ms + int(config.FUN_FACT_START * 1000)
        layers.append((ra.fact_path, fact_ms, 1.0))

        # Applause on the LAST round reveal for celebration
        if i == num_rounds - 1 and config.SFX_FILES["applause"].exists():
            layers.append((config.SFX_FILES["applause"], reveal_ms + 200, 0.4))

        # Reaction interjection after fun fact (host energy between rounds)
        if hasattr(ra, 'reaction_path') and ra.reaction_path and Path(ra.reaction_path).exists():
            reaction_ms = round_start_ms + int(config.SCORE_UPDATE_TIME * 1000)
            layers.append((ra.reaction_path, reaction_ms, 0.85))

        # Whoosh transition near end of round
        transition_ms = round_start_ms + int(config.TRANSITION_START * 1000)
        if config.SFX_FILES["whoosh"].exists():
            layers.append((config.SFX_FILES["whoosh"], transition_ms, 0.5))

    # --- Layer 4: Outro jingle + applause ---
    outro_ms = total_ms - int(config.OUTRO_DURATION * 1000)
    if config.SFX_FILES["jingle_outro"].exists():
        layers.append((config.SFX_FILES["jingle_outro"], outro_ms, 0.75))
    # Applause during outro for celebration feel
    if config.SFX_FILES["applause"].exists():
        layers.append((config.SFX_FILES["applause"], outro_ms + 300, 0.35))

    # Mix all layers into final output
    return mix_layers(layers, total_ms, output_path)
