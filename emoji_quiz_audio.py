# emoji_quiz_audio.py
# ============================================================
# Audio mixer for Emoji Quiz format (40 rounds, 5-second timer).
#
# Sound design for "Guess the X by Emoji" videos:
# - Background music throughout with dynamic ducking
# - VOICEOVER NARRATION throughout (Monkey Quiz quality):
#   - Intro narration ("Leo mixed all the animals into emojis!")
#   - Per-round question ("Can you guess this animal?")
#   - Per-round reveal ("Awesome! It's a hamster!")
#   - Section card narration ("Easy level!")
#   - Outro narration ("Amazing job! Subscribe!")
# - Music ducks under voice automatically
# - Tick SFX during timer countdown (builds tension)
# - Ding + correct chime on every answer reveal
# - Section card SFX on difficulty transitions
# - Intro + outro jingles
# ============================================================
import math
from pathlib import Path
from pydub import AudioSegment

import config


def _load_sfx(name: str) -> AudioSegment:
    """
    # Load a sound effect file by name.
    # Returns silent segment if file doesn't exist.
    """
    sfx_path = config.SFX_FILES.get(name)
    if sfx_path and sfx_path.exists():
        try:
            return AudioSegment.from_file(str(sfx_path))
        except Exception:
            pass
    return AudioSegment.silent(duration=100)


def _load_voice_clip(path: Path) -> AudioSegment:
    """
    # Load a voice narration clip from a file.
    # Returns silent segment if file doesn't exist or is too small.
    """
    if path and path.exists() and path.stat().st_size > 1000:
        try:
            return AudioSegment.from_file(str(path))
        except Exception:
            pass
    return AudioSegment.silent(duration=100)


def _duck_music_under_voice(music: AudioSegment, voice_layer: AudioSegment,
                             duck_db: float = -10.0) -> AudioSegment:
    """
    # Duck the music volume wherever voice is present.
    # Scans the voice layer in 50ms chunks — where voice is louder
    # than -35dBFS, the music is reduced by duck_db.
    """
    chunk_ms = 50
    ducked = AudioSegment.empty()

    for i in range(0, len(music), chunk_ms):
        music_chunk = music[i:i + chunk_ms]
        voice_chunk = voice_layer[i:i + chunk_ms]

        # Check if voice is present in this chunk
        if len(voice_chunk) > 0:
            try:
                if voice_chunk.dBFS > -35:
                    # Voice present — duck the music
                    music_chunk = music_chunk.apply_gain(duck_db)
            except Exception:
                pass

        ducked += music_chunk

    return ducked


def build_emoji_audio(music_path: Path, total_duration: float,
                       output_path: Path, num_rounds: int = 40,
                       narration_pack=None,
                       emoji_counts: list[int] = None) -> Path:
    """
    # Build complete audio track for an emoji quiz video.
    #
    # Audio layers:
    # 1. Background music (looped, ducked under voice)
    # 2. Voice narration (intro, per-round question/reveal, sections, outro)
    # 3. SFX (ticks, dings, whoosh, drumroll, applause, jingles)
    #
    # When narration_pack is provided, voice clips are mixed in and
    # the music automatically ducks under them.
    """
    total_ms = int(total_duration * 1000)

    # --- Load all SFX ---
    tick_sfx = _load_sfx("tick")
    ding_sfx = _load_sfx("ding")
    correct_sfx = _load_sfx("correct")
    whoosh_sfx = _load_sfx("whoosh")
    drumroll_sfx = _load_sfx("drumroll")
    applause_sfx = _load_sfx("applause")
    intro_jingle = _load_sfx("jingle_intro")
    outro_jingle = _load_sfx("jingle_outro")
    countdown_beep = _load_sfx("countdown_beep")
    times_up_sfx = _load_sfx("times_up")
    emoji_pop_sfx = _load_sfx("emoji_pop")

    # --- Layer 1: Background music ---
    if music_path and music_path.exists():
        music = AudioSegment.from_file(str(music_path))
        loops = (total_ms // len(music)) + 1
        music = (music * loops)[:total_ms]
        music = music.apply_gain(-12)  # background level
    else:
        music = AudioSegment.silent(duration=total_ms)

    # --- Layer 2: Voice narration ---
    voice_layer = AudioSegment.silent(duration=total_ms)
    has_voice = False

    # --- Layer 3: SFX ---
    sfx_layer = AudioSegment.silent(duration=total_ms)

    # ================================================================
    # BUILD TIMELINE — place SFX and voice at correct positions
    # ================================================================
    t = 0.0

    # --- Intro ---
    intro_pos = int(t * 1000)
    if len(intro_jingle) > 100:
        sfx_layer = sfx_layer.overlay(intro_jingle.apply_gain(-3), position=intro_pos)

    # --- Intro voice narration ---
    # Place intro voice at 0.3s (matching subtitle clip_start in assembler)
    intro_voice_end_ms = intro_pos + 300
    if narration_pack and narration_pack.intro_path:
        intro_voice = _load_voice_clip(narration_pack.intro_path)
        if len(intro_voice) > 100:
            voice_layer = voice_layer.overlay(
                intro_voice.apply_gain(2), position=intro_pos + 300)
            has_voice = True
            intro_voice_end_ms = intro_pos + 300 + len(intro_voice)

    # --- Subscribe voice plays right after intro finishes (no overlap) ---
    if narration_pack and narration_pack.subscribe_path:
        sub_voice = _load_voice_clip(narration_pack.subscribe_path)
        if len(sub_voice) > 100:
            sub_pos = intro_voice_end_ms + 300  # 300ms gap after intro
            voice_layer = voice_layer.overlay(
                sub_voice.apply_gain(1), position=sub_pos)

    # --- Dynamic intro duration: voice must finish before rounds start ---
    intro_voice_total = 0.0
    if narration_pack:
        intro_voice_total = (narration_pack.intro_duration +
                              narration_pack.subscribe_duration)
    actual_intro = max(config.EMOJI_INTRO_DURATION,
                       intro_voice_total + 1.5)
    t += actual_intro

    # --- For each difficulty tier ---
    # Proportional scaling when total rounds < config sum (e.g. --rounds 4)
    rpd = config.EMOJI_ROUNDS_PER_DIFFICULTY
    round_idx = 0
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

    for tier_idx, difficulty in enumerate(config.EMOJI_DIFFICULTIES):
        rounds_per_tier = tier_round_counts.get(difficulty, 0)
        if rounds_per_tier <= 0:
            continue
        # --- Section card SFX ---
        section_pos = int(t * 1000)
        if len(whoosh_sfx) > 100:
            sfx_layer = sfx_layer.overlay(whoosh_sfx.apply_gain(-4), position=section_pos)
        if len(drumroll_sfx) > 100:
            sfx_layer = sfx_layer.overlay(
                drumroll_sfx[:2000].apply_gain(-6),
                position=section_pos + 300)

        # --- Section card voice narration ---
        # Section card is 3s — voice must finish before first round starts
        sec_voice_start_ms = section_pos + 200
        sec_max_len_ms = int(config.EMOJI_SECTION_CARD_DURATION * 1000) - 400
        if narration_pack and difficulty in narration_pack.section_paths:
            sec_voice = _load_voice_clip(narration_pack.section_paths[difficulty])
            if len(sec_voice) > 100:
                if len(sec_voice) > sec_max_len_ms:
                    sec_voice = sec_voice[:sec_max_len_ms]
                voice_layer = voice_layer.overlay(
                    sec_voice.apply_gain(2), position=sec_voice_start_ms)
                has_voice = True

        t += config.EMOJI_SECTION_CARD_DURATION

        # --- Per-round SFX + voice ---
        for i in range(rounds_per_tier):
            round_start_ms = int(t * 1000)
            round_end_ms = int((t + config.EMOJI_ROUND_DURATION) * 1000)
            reveal_pos = int((t + config.EMOJI_REVEAL_START) * 1000)

            # --- Emoji pop SFX (one per emoji appearing, staggered 0.7s) ---
            # Uses actual emoji count per round so pops match visuals exactly
            num_emoji = emoji_counts[round_idx] if emoji_counts and round_idx < len(emoji_counts) else 2
            for emoji_i in range(num_emoji):
                pop_pos = round_start_ms + int(emoji_i * 700)
                if pop_pos < total_ms and len(emoji_pop_sfx) > 100:
                    sfx_layer = sfx_layer.overlay(
                        emoji_pop_sfx.apply_gain(0), position=pop_pos)

            # --- Question voice ("Can you guess this animal?") ---
            # Plays at round start. MUST end before reveal starts (no overlap).
            q_voice_start_ms = round_start_ms + 100
            q_max_len_ms = reveal_pos - q_voice_start_ms - 200
            if (narration_pack and
                round_idx < len(narration_pack.question_paths) and
                narration_pack.question_paths[round_idx]):
                q_voice = _load_voice_clip(narration_pack.question_paths[round_idx])
                if len(q_voice) > 100:
                    if len(q_voice) > q_max_len_ms:
                        q_voice = q_voice[:q_max_len_ms]
                    voice_layer = voice_layer.overlay(
                        q_voice.apply_gain(2), position=q_voice_start_ms)
                    has_voice = True

            # --- Timer ticks during countdown (LOUD) ---
            timer_start = t + config.EMOJI_EMOJI_SETTLE
            for tick_i in range(config.EMOJI_TIMER_SECONDS):
                tick_pos = int((timer_start + tick_i) * 1000)
                if tick_pos < total_ms and len(tick_sfx) > 100:
                    tick_gain = 0 if tick_i < 3 else 3
                    sfx_layer = sfx_layer.overlay(
                        tick_sfx.apply_gain(tick_gain), position=tick_pos)

            # --- Final countdown beep (last second) ---
            beep_pos = int((timer_start + config.EMOJI_TIMER_SECONDS - 1) * 1000)
            if beep_pos < total_ms and len(countdown_beep) > 100:
                sfx_layer = sfx_layer.overlay(
                    countdown_beep.apply_gain(3), position=beep_pos)

            # --- TIME'S UP buzzer right when timer expires ---
            times_up_pos = int((timer_start + config.EMOJI_TIMER_SECONDS) * 1000)
            if times_up_pos < total_ms and len(times_up_sfx) > 100:
                sfx_layer = sfx_layer.overlay(
                    times_up_sfx.apply_gain(2), position=times_up_pos)

            # --- Answer reveal ding (after buzzer) ---
            if reveal_pos < total_ms and len(ding_sfx) > 100:
                sfx_layer = sfx_layer.overlay(
                    ding_sfx.apply_gain(-2), position=reveal_pos)
            if reveal_pos + 200 < total_ms and len(correct_sfx) > 100:
                sfx_layer = sfx_layer.overlay(
                    correct_sfx.apply_gain(-4), position=reveal_pos + 200)

            # --- Reveal voice ("It's a hamster!") ---
            # Plays after ding. MUST end before next round starts (no overlap).
            r_voice_start_ms = reveal_pos + 300
            r_max_len_ms = round_end_ms - r_voice_start_ms - 200  # 200ms gap before next round
            if (narration_pack and
                round_idx < len(narration_pack.reveal_paths) and
                narration_pack.reveal_paths[round_idx]):
                r_voice = _load_voice_clip(narration_pack.reveal_paths[round_idx])
                if len(r_voice) > 100:
                    # Truncate if too long to prevent overlap with next round
                    if len(r_voice) > r_max_len_ms:
                        r_voice = r_voice[:r_max_len_ms]
                    voice_layer = voice_layer.overlay(
                        r_voice.apply_gain(2), position=r_voice_start_ms)
                    has_voice = True

            # --- Transition whoosh SFX (between rounds) ---
            trans_pos = int((t + config.EMOJI_TRANSITION_START) * 1000)
            if trans_pos < total_ms and len(whoosh_sfx) > 100:
                sfx_layer = sfx_layer.overlay(
                    whoosh_sfx.apply_gain(-2), position=trans_pos)

            t += config.EMOJI_ROUND_DURATION
            round_idx += 1

    # --- Outro ---
    outro_pos = int(t * 1000)
    if len(outro_jingle) > 100:
        sfx_layer = sfx_layer.overlay(
            outro_jingle.apply_gain(-3), position=outro_pos)
    if len(applause_sfx) > 100:
        sfx_layer = sfx_layer.overlay(
            applause_sfx.apply_gain(-4), position=outro_pos + 500)

    # --- Outro voice narration ---
    if narration_pack and narration_pack.outro_path:
        outro_voice = _load_voice_clip(narration_pack.outro_path)
        if len(outro_voice) > 100:
            voice_layer = voice_layer.overlay(
                outro_voice.apply_gain(2), position=outro_pos + 300)
            has_voice = True

    # ================================================================
    # MIX ALL LAYERS
    # ================================================================

    # If we have voice, duck the music under it
    if has_voice:
        print("[EMOJI AUDIO] Ducking music under voice narration...")
        music = _duck_music_under_voice(music, voice_layer, duck_db=-10.0)

    # Mix: music (ducked) + voice + SFX
    final = music.overlay(voice_layer).overlay(sfx_layer)

    # --- Normalize to prevent clipping ---
    if final.max_dBFS > -1.0:
        final = final.apply_gain(-1.0 - final.max_dBFS)

    # --- Export ---
    final.export(str(output_path), format="wav")
    voice_status = "with narration" if has_voice else "SFX only"
    print(f"[EMOJI AUDIO] Mixed {total_duration:.0f}s audio ({voice_status}) -> {output_path.name}")
    return output_path
