# speed_quiz_audio.py
# ============================================================
# Audio mixer for speed quiz format (120 rounds, 3-second timer).
#
# Sound design optimized for the speed quiz format:
# - Background music throughout with dynamic ducking
# - Tick SFX during timer countdown (builds tension)
# - Ding + correct chime on every answer reveal
# - Cheering reactions every ~10 rounds (not every round — too slow)
# - Section card narration: "Easy level!", "Medium level!" etc.
# - Intro + outro narration and jingles
# - Confetti/applause sounds on difficulty transitions
#
# Key difference from shorts audio: 120 rounds means we CAN'T
# narrate every question (too many ElevenLabs API calls + too slow).
# Instead: SFX-driven pacing with periodic voice reactions.
# ============================================================
import math
from pathlib import Path
from pydub import AudioSegment

import config


def _get_audio_duration_ms(audio_path: Path, fallback: int) -> int:
    """# Get audio file duration in ms, falling back to estimate."""
    try:
        if audio_path and audio_path.exists():
            return len(AudioSegment.from_file(str(audio_path)))
    except Exception:
        pass
    return fallback


def _duck_music(music_path: Path, voice_regions: list[tuple[int, int]],
                total_ms: int, output_path: Path,
                normal_vol: float = 0.20,
                ducked_vol: float = 0.08) -> Path:
    """
    # Dynamic music ducking — lower music during voice segments.
    # Creates the professional "sidechain" feel heard in studio content.
    # Loops music track to fill entire video duration.
    """
    music = AudioSegment.from_file(str(music_path))
    # Loop music to cover full video length
    loops = (total_ms // len(music)) + 1
    looped = (music * loops)[:total_ms]

    # Duck in 50ms chunks for smooth transitions
    chunk_ms = 50
    result = AudioSegment.silent(duration=0)
    for pos in range(0, total_ms, chunk_ms):
        chunk = looped[pos:min(pos + chunk_ms, total_ms)]
        is_voice = any(s <= pos < e or s < min(pos + chunk_ms, total_ms) <= e
                       for s, e in voice_regions)
        vol = ducked_vol if is_voice else normal_vol
        if vol < 1.0:
            chunk = chunk.apply_gain(20 * math.log10(max(vol, 0.01)))
        result += chunk

    result.export(str(output_path), format="wav")
    return output_path


def build_speed_audio(round_audios: list, music_path: Path,
                      total_duration: float, output_path: Path,
                      num_rounds: int = 120,
                      narration_pack=None) -> Path:
    """
    # Build complete audio track for a speed quiz video.
    #
    # Audio layers:
    # 1. Background music (ducked during voice)
    # 2. Intro jingle + voiceover
    # 3. Subscribe voiceover
    # 4. Section card voiceover ("Easy level! Let's go!")
    # 5. Per-round SFX: ticks (timer) + ding (reveal)
    # 6. Cheering reactions from narration_pack (~every 10 rounds)
    # 7. Applause on difficulty transitions
    # 8. Outro jingle + voiceover + applause
    #
    # narration_pack: SpeedNarrationPack with unique voiceover clips
    # (generated fresh per video so no two videos sound the same)
    """
    total_ms = int(total_duration * 1000)
    layers = []
    voice_regions = []

    # --- Calculate timing ---
    intro_ms = int(config.SPEED_INTRO_DURATION * 1000)
    subscribe_ms = int(config.SPEED_SUBSCRIBE_DURATION * 1000)
    section_ms = int(config.SPEED_SECTION_CARD_DURATION * 1000)
    round_ms = int(config.SPEED_ROUND_DURATION * 1000)

    current_ms = 0

    # --- Intro: jingle + voiceover ---
    if config.SFX_FILES["jingle_intro"].exists():
        layers.append((config.SFX_FILES["jingle_intro"], 0, 0.65))

    if narration_pack and narration_pack.intro_path and narration_pack.intro_path.exists():
        layers.append((narration_pack.intro_path, 800, 1.0))
        dur = _get_audio_duration_ms(narration_pack.intro_path, 3000)
        voice_regions.append((800, 800 + dur))

    current_ms = intro_ms

    # --- Subscribe prompt voiceover ---
    if narration_pack and narration_pack.subscribe_path and narration_pack.subscribe_path.exists():
        layers.append((narration_pack.subscribe_path, current_ms + 500, 1.0))
        dur = _get_audio_duration_ms(narration_pack.subscribe_path, 2000)
        voice_regions.append((current_ms + 500, current_ms + 500 + dur))

    current_ms += subscribe_ms

    # Track which reaction clip to use next (cycles through available clips)
    reaction_idx = 0
    reaction_paths = narration_pack.reaction_paths if narration_pack else []

    # --- Per-section and per-round audio ---
    for section_idx in range(len(config.SPEED_DIFFICULTIES)):
        difficulty = config.SPEED_DIFFICULTIES[section_idx]
        section_start_ms = current_ms

        # Section card voiceover (unique per difficulty, fresh every video)
        if narration_pack and difficulty in narration_pack.section_paths:
            section_voice = narration_pack.section_paths[difficulty]
            if section_voice and section_voice.exists():
                layers.append((section_voice, section_start_ms + 400, 1.0))
                dur = _get_audio_duration_ms(section_voice, 2000)
                voice_regions.append((section_start_ms + 400, section_start_ms + 400 + dur))

        current_ms += section_ms

        # 30 rounds in this section
        start_round = section_idx * config.SPEED_ROUNDS_PER_DIFFICULTY
        end_round = min(start_round + config.SPEED_ROUNDS_PER_DIFFICULTY, num_rounds)

        for round_idx in range(start_round, end_round):
            round_start_ms = current_ms

            # Timer tick sounds (3 ticks, one per second, getting louder)
            timer_start_ms = round_start_ms + int(config.SPEED_TIMER_START * 1000)
            for tick_i in range(config.SPEED_TIMER_SECONDS):
                tick_ms = timer_start_ms + tick_i * 1000
                if config.SFX_FILES["tick"].exists():
                    tick_vol = 0.35 + 0.25 * (tick_i / config.SPEED_TIMER_SECONDS)
                    layers.append((config.SFX_FILES["tick"], tick_ms, tick_vol))
                if tick_i == config.SPEED_TIMER_SECONDS - 1:
                    beep = config.SFX_FILES.get("countdown_beep")
                    if beep and beep.exists():
                        layers.append((beep, tick_ms, 0.4))

            # Ding + correct chime on reveal
            reveal_ms = round_start_ms + int(config.SPEED_REVEAL_START * 1000)
            if config.SFX_FILES["ding"].exists():
                layers.append((config.SFX_FILES["ding"], reveal_ms, 0.75))
            correct = config.SFX_FILES.get("correct")
            if correct and correct.exists():
                layers.append((correct, reveal_ms + 80, 0.45))

            # Per-round answer reveal voice ("It's a Lion!", "Eagle! Wow!")
            # Every round gets its own clip — varied templates so no two sound alike
            reveal_paths = narration_pack.round_reveal_paths if narration_pack else []
            if round_idx < len(reveal_paths) and reveal_paths[round_idx]:
                r_path = reveal_paths[round_idx]
                if r_path.exists():
                    # Voice starts 200ms after ding for natural feel
                    layers.append((r_path, reveal_ms + 200, 1.0))
                    dur = _get_audio_duration_ms(r_path, 1200)
                    voice_regions.append((reveal_ms + 200, reveal_ms + 200 + dur))

            # Cheering reaction every ~10 rounds (from narration pack)
            # These are unique per video — Gemini wrote them fresh
            rounds_in_section = round_idx - start_round
            if rounds_in_section > 0 and rounds_in_section % 10 == 0 and reaction_paths:
                r_path = reaction_paths[reaction_idx % len(reaction_paths)]
                if r_path and r_path.exists():
                    cheer_ms = round_start_ms + int(config.SPEED_FACT_START * 1000)
                    layers.append((r_path, cheer_ms, 0.9))
                    dur = _get_audio_duration_ms(r_path, 1200)
                    voice_regions.append((cheer_ms, cheer_ms + dur))
                reaction_idx += 1

            # Whoosh transition
            transition_ms = round_start_ms + int(config.SPEED_TRANSITION_START * 1000)
            if config.SFX_FILES["whoosh"].exists():
                layers.append((config.SFX_FILES["whoosh"], transition_ms, 0.4))

            # Applause at end of each difficulty section
            if round_idx == end_round - 1 and config.SFX_FILES["applause"].exists():
                layers.append((config.SFX_FILES["applause"], reveal_ms + 200, 0.35))

            current_ms += round_ms

    # --- Outro: jingle + voiceover + applause ---
    outro_start_ms = total_ms - int(config.SPEED_OUTRO_DURATION * 1000)
    if config.SFX_FILES["jingle_outro"].exists():
        layers.append((config.SFX_FILES["jingle_outro"], outro_start_ms, 0.65))
    if config.SFX_FILES["applause"].exists():
        layers.append((config.SFX_FILES["applause"], outro_start_ms + 500, 0.45))

    if narration_pack and narration_pack.outro_path and narration_pack.outro_path.exists():
        layers.append((narration_pack.outro_path, outro_start_ms + 1000, 1.0))
        dur = _get_audio_duration_ms(narration_pack.outro_path, 3000)
        voice_regions.append((outro_start_ms + 1000, outro_start_ms + 1000 + dur))

    # --- Background music with dynamic ducking ---
    if music_path and music_path.exists():
        ducked_path = output_path.parent / "speed_ducked_music.wav"
        _duck_music(music_path, voice_regions, total_ms, ducked_path)
        layers.append((ducked_path, 0, 1.0))

    # --- Mix all layers ---
    mixed = AudioSegment.silent(duration=total_ms)
    for audio_path_item, offset_ms, volume in layers:
        if not Path(audio_path_item).exists():
            continue
        try:
            clip = AudioSegment.from_file(str(audio_path_item))
            if volume < 1.0:
                clip = clip.apply_gain(20 * math.log10(max(volume, 0.01)))
            elif volume > 1.0:
                clip = clip.apply_gain(20 * math.log10(volume))
            mixed = mixed.overlay(clip, position=offset_ms)
        except Exception as e:
            print(f"[SPEED AUDIO] Could not mix {audio_path_item}: {e}")

    # Normalize final mix
    if mixed.max_dBFS > -100:
        mixed = mixed.apply_gain(config.AUDIO_PEAK_DB - mixed.max_dBFS)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mixed.export(str(output_path), format="wav")
    print(f"[SPEED AUDIO] Mixed audio saved: {output_path}")
    return output_path
