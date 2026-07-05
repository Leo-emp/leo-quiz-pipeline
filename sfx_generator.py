# sfx_generator.py
# ============================================================
# Programmatic sound effect generator for Leo Quiz.
# Generates ALL SFX + background music from pure math (numpy)
# so the pipeline works without any bundled audio files.
# Run once — caches generated WAV files in assets/sfx/ and
# assets/music/ for all future pipeline runs.
# ============================================================
import math
import struct
import wave
from pathlib import Path

import numpy as np

import config

# --- Audio constants ---
SAMPLE_RATE = 44100      # CD-quality sample rate
BIT_DEPTH = 16           # 16-bit PCM
MAX_AMP = 32767          # Max amplitude for 16-bit signed int


def _save_wav(samples: np.ndarray, path: Path, sample_rate: int = SAMPLE_RATE):
    """
    # Save a numpy float array (-1.0 to 1.0) as a 16-bit WAV file.
    # Creates parent directories if they don't exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Clip to valid range and convert to 16-bit integers
    clipped = np.clip(samples, -1.0, 1.0)
    int_samples = (clipped * MAX_AMP).astype(np.int16)

    # Write WAV file using stdlib wave module (no pydub dependency here)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)            # Mono audio
        wf.setsampwidth(2)            # 16-bit = 2 bytes per sample
        wf.setframerate(sample_rate)
        wf.writeframes(int_samples.tobytes())


def _sine_wave(freq: float, duration: float, amplitude: float = 1.0,
               sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """
    # Generate a pure sine wave at the given frequency.
    # freq: Hz, duration: seconds, amplitude: 0.0-1.0
    """
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    return amplitude * np.sin(2 * np.pi * freq * t)


def _noise(duration: float, amplitude: float = 1.0,
           sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """
    # Generate white noise — random samples for whoosh/applause effects.
    """
    n_samples = int(sample_rate * duration)
    return amplitude * np.random.uniform(-1, 1, n_samples)


def _envelope(samples: np.ndarray, attack: float = 0.01,
              decay: float = 0.1, sustain: float = 0.7,
              release: float = 0.1) -> np.ndarray:
    """
    # Apply ADSR envelope to shape the volume over time.
    # attack/decay/release in seconds, sustain as 0-1 level.
    # Makes raw sine waves sound like real instruments.
    """
    n = len(samples)
    sr = SAMPLE_RATE
    env = np.ones(n)

    # Attack phase: ramp up from 0 to 1
    a_samples = min(int(attack * sr), n)
    env[:a_samples] = np.linspace(0, 1, a_samples)

    # Decay phase: drop from 1 to sustain level
    d_start = a_samples
    d_samples = min(int(decay * sr), n - d_start)
    env[d_start:d_start + d_samples] = np.linspace(1, sustain, d_samples)

    # Sustain phase: hold at sustain level (already 1.0, just set it)
    s_end = n - int(release * sr)
    env[d_start + d_samples:s_end] = sustain

    # Release phase: fade from sustain to 0
    r_start = max(s_end, 0)
    env[r_start:] = np.linspace(sustain, 0, n - r_start)

    return samples * env


def _exponential_decay(samples: np.ndarray, decay_rate: float = 5.0) -> np.ndarray:
    """
    # Apply exponential decay — used for bell/ding sounds.
    # Higher decay_rate = faster fade out.
    """
    n = len(samples)
    t = np.linspace(0, 1, n)
    decay = np.exp(-decay_rate * t)
    return samples * decay


# ============================================================
# Individual SFX generators
# ============================================================

def generate_tick(path: Path):
    """
    # Short percussive click for countdown beats (50ms).
    # Two sine bursts at 1000Hz and 2500Hz with fast decay.
    # Sounds like a clock tick or metronome click.
    """
    duration = 0.05  # 50 milliseconds
    # Mix two frequencies for richer click sound
    tone1 = _sine_wave(1000, duration, 0.8)
    tone2 = _sine_wave(2500, duration, 0.3)
    click = tone1 + tone2
    # Very fast exponential decay — sharp attack, instant falloff
    click = _exponential_decay(click, decay_rate=40.0)
    _save_wav(click, path)


def generate_ding(path: Path):
    """
    # Bell tone for answer reveal (500ms).
    # 880Hz fundamental + harmonics (1760Hz, 2640Hz) with decay.
    # Sounds like a game show "correct" bell.
    """
    duration = 0.5
    # Fundamental + two harmonics create a rich bell timbre
    fundamental = _sine_wave(880, duration, 0.6)
    harmonic2 = _sine_wave(1760, duration, 0.25)
    harmonic3 = _sine_wave(2640, duration, 0.1)
    bell = fundamental + harmonic2 + harmonic3
    # Bell sounds decay exponentially
    bell = _exponential_decay(bell, decay_rate=4.0)
    _save_wav(bell, path)


def generate_whoosh(path: Path):
    """
    # Swoosh/transition sound (250ms).
    # Band-shaped noise with volume envelope — rises then falls.
    # Used for round transitions and slide-in animations.
    """
    duration = 0.25
    n = int(SAMPLE_RATE * duration)
    # White noise base
    raw_noise = _noise(duration, 0.4)
    # Volume envelope: quick rise then fall (triangle shape)
    env = np.concatenate([
        np.linspace(0, 1, n // 3),     # Rise
        np.linspace(1, 0, n - n // 3), # Fall
    ])
    whoosh = raw_noise * env
    _save_wav(whoosh, path)


def generate_applause(path: Path):
    """
    # Celebratory applause sound (1.5s).
    # Layered noise bursts with modulation to simulate clapping.
    # Used after correct answer or high scores.
    """
    duration = 1.5
    n = int(SAMPLE_RATE * duration)
    # Base noise for applause texture
    base = _noise(duration, 0.3)
    # Modulate with low-frequency wave to create "clap" rhythm (~12 claps/sec)
    t = np.linspace(0, duration, n)
    modulation = 0.5 + 0.5 * np.sin(2 * np.pi * 12 * t)
    applause = base * modulation
    # Fade in quickly, sustain, fade out
    applause = _envelope(applause, attack=0.05, decay=0.1,
                         sustain=0.8, release=0.4)
    _save_wav(applause, path)


def generate_drumroll(path: Path):
    """
    # Tension-building drumroll (1.0s).
    # Rapid repeating bursts that increase in volume (crescendo).
    # Played during the 3-2-1 countdown for dramatic effect.
    """
    duration = 1.0
    n = int(SAMPLE_RATE * duration)
    result = np.zeros(n)
    # Create rapid drum hits (~20 per second, getting faster)
    hits_per_sec = 20
    hit_duration = 0.015  # 15ms per hit
    hit_samples = int(SAMPLE_RATE * hit_duration)

    for i in range(int(hits_per_sec * duration)):
        # Position each hit — they get slightly closer together over time
        pos = int(i * SAMPLE_RATE / hits_per_sec)
        if pos + hit_samples > n:
            break
        # Each hit is a noise burst with exponential decay
        hit = _noise(hit_duration, 0.5)
        hit = _exponential_decay(hit, decay_rate=30.0)
        # Crescendo: volume increases linearly over time
        volume = 0.3 + 0.7 * (i / (hits_per_sec * duration))
        result[pos:pos + len(hit)] += hit * volume

    # Clip to prevent clipping artifacts
    result = np.clip(result, -1.0, 1.0)
    _save_wav(result, path)


def generate_correct_chime(path: Path):
    """
    # Happy two-tone chime for correct reveals (300ms).
    # C5 (523Hz) then E5 (659Hz) — a major third interval.
    # Universal "you got it right!" sound.
    """
    note_dur = 0.15  # 150ms per note
    # First note: C5
    note1 = _sine_wave(523.25, note_dur, 0.7)
    note1 = _exponential_decay(note1, 6.0)
    # Second note: E5 (higher, happy feel)
    note2 = _sine_wave(659.25, note_dur, 0.7)
    note2 = _exponential_decay(note2, 6.0)
    # Concatenate with tiny gap
    gap = np.zeros(int(SAMPLE_RATE * 0.02))
    chime = np.concatenate([note1, gap, note2])
    _save_wav(chime, path)


def generate_jingle_intro(path: Path):
    """
    # Ascending 4-note melody for video intro (1.2s).
    # C5→E5→G5→C6: a rising major arpeggio.
    # Signals "the quiz is starting!" excitement.
    """
    # Notes: C5, E5, G5, C6 (ascending major arpeggio)
    freqs = [523.25, 659.25, 783.99, 1046.50]
    note_dur = 0.25   # 250ms per note
    gap_dur = 0.05    # 50ms gap between notes

    parts = []
    for i, freq in enumerate(freqs):
        # Each note has fundamental + octave harmonic for richness
        note = _sine_wave(freq, note_dur, 0.5)
        note += _sine_wave(freq * 2, note_dur, 0.15)  # Octave harmonic
        note = _exponential_decay(note, 3.0)
        # Volume increases as pitch rises — builds energy
        note *= (0.7 + 0.3 * (i / len(freqs)))
        parts.append(note)
        if i < len(freqs) - 1:
            parts.append(np.zeros(int(SAMPLE_RATE * gap_dur)))

    jingle = np.concatenate(parts)
    _save_wav(jingle, path)


def generate_jingle_outro(path: Path):
    """
    # Descending melody for video outro (1.5s).
    # C6→G5→E5→C5→C4: falling arpeggio with final low note.
    # "That's all folks!" feel — wraps up the quiz.
    """
    # Descending: C6, G5, E5, C5, then resolving low C4
    freqs = [1046.50, 783.99, 659.25, 523.25, 261.63]
    note_dur = 0.25
    gap_dur = 0.03

    parts = []
    for i, freq in enumerate(freqs):
        note = _sine_wave(freq, note_dur, 0.5)
        note += _sine_wave(freq * 2, note_dur, 0.12)
        # Last note sustains longer for finality
        if i == len(freqs) - 1:
            note = _sine_wave(freq, 0.4, 0.6)
            note += _sine_wave(freq * 2, 0.4, 0.15)
            note = _exponential_decay(note, 2.0)
        else:
            note = _exponential_decay(note, 4.0)
        parts.append(note)
        if i < len(freqs) - 1:
            parts.append(np.zeros(int(SAMPLE_RATE * gap_dur)))

    jingle = np.concatenate(parts)
    _save_wav(jingle, path)


def generate_countdown_beep(path: Path):
    """
    # Short countdown beep for each number (100ms).
    # 440Hz (A4) with sharp attack — used alongside the tick.
    # Layered on top of tick for more dramatic countdown feel.
    """
    duration = 0.1
    tone = _sine_wave(440, duration, 0.5)
    tone += _sine_wave(880, duration, 0.2)
    tone = _envelope(tone, attack=0.005, decay=0.02,
                     sustain=0.4, release=0.03)
    _save_wav(tone, path)


# ============================================================
# Background music generator
# ============================================================

def generate_bgm(path: Path, duration: float = 30.0):
    """
    # Generate a cheerful background music loop (30 seconds).
    # Uses a simple major-key chord progression: C-F-G-C
    # with a bouncy rhythm and light melody on top.
    # Not studio quality — but WAY better than silence.
    # Loops seamlessly for any video length.
    """
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    result = np.zeros(n)
    bpm = 120
    beat_dur = 60.0 / bpm  # 0.5 seconds per beat

    # --- Chord progression (4 chords, 2 bars each = 16 beats total loop) ---
    # C major (C-E-G), F major (F-A-C), G major (G-B-D), C major
    chords = [
        [261.63, 329.63, 392.00],  # C major: C4, E4, G4
        [349.23, 440.00, 523.25],  # F major: F4, A4, C5
        [392.00, 493.88, 587.33],  # G major: G4, B4, D5
        [261.63, 329.63, 392.00],  # C major (resolve)
    ]
    # Each chord plays for 4 beats = 2 seconds
    chord_dur = 4 * beat_dur

    # Render chord pad (sustained tones at low volume)
    for chord_idx, chord_notes in enumerate(chords):
        # Repeat the 4-chord progression to fill duration
        for repeat in range(int(duration / (len(chords) * chord_dur)) + 1):
            chord_start = (repeat * len(chords) + chord_idx) * chord_dur
            if chord_start >= duration:
                break
            # Each note in the chord
            for note_freq in chord_notes:
                start_sample = int(chord_start * SAMPLE_RATE)
                end_sample = min(int((chord_start + chord_dur) * SAMPLE_RATE), n)
                if start_sample >= n:
                    break
                length = end_sample - start_sample
                # Soft sine pad with gentle attack/release
                note_t = np.linspace(0, chord_dur, length, endpoint=False)
                note = 0.08 * np.sin(2 * np.pi * note_freq * note_t)
                # Soft envelope to avoid clicks between chords
                env = np.ones(length)
                fade = min(int(0.05 * SAMPLE_RATE), length // 4)
                env[:fade] = np.linspace(0, 1, fade)
                env[-fade:] = np.linspace(1, 0, fade)
                note *= env
                result[start_sample:end_sample] += note

    # --- Bouncy bass line (root note, octave below chords) ---
    bass_notes = [130.81, 174.61, 196.00, 130.81]  # C3, F3, G3, C3
    for chord_idx, bass_freq in enumerate(bass_notes):
        for repeat in range(int(duration / (len(bass_notes) * chord_dur)) + 1):
            chord_start = (repeat * len(bass_notes) + chord_idx) * chord_dur
            if chord_start >= duration:
                break
            # Play bass on beats 1 and 3 of each 4-beat bar
            for beat in [0, 2]:
                beat_start = chord_start + beat * beat_dur
                if beat_start >= duration:
                    break
                start_s = int(beat_start * SAMPLE_RATE)
                note_len = int(beat_dur * 0.8 * SAMPLE_RATE)
                end_s = min(start_s + note_len, n)
                length = end_s - start_s
                if length <= 0:
                    continue
                note_t = np.linspace(0, beat_dur * 0.8, length, endpoint=False)
                bass = 0.12 * np.sin(2 * np.pi * bass_freq * note_t)
                bass = bass * np.exp(-3.0 * note_t / (beat_dur * 0.8))
                result[start_s:end_s] += bass

    # --- Simple melody (pentatonic, plays on upbeats) ---
    # C pentatonic: C5, D5, E5, G5, A5
    melody_notes = [523.25, 587.33, 659.25, 783.99, 880.00]
    rng = np.random.RandomState(42)  # Deterministic melody
    melody_dur = beat_dur * 0.4  # Short staccato notes
    for beat_idx in range(int(duration / beat_dur)):
        # Play melody on every other beat for a bouncy feel
        if beat_idx % 2 == 1:
            beat_time = beat_idx * beat_dur
            if beat_time >= duration:
                break
            # Pick a random pentatonic note
            freq = melody_notes[rng.randint(0, len(melody_notes))]
            start_s = int(beat_time * SAMPLE_RATE)
            mel_len = int(melody_dur * SAMPLE_RATE)
            end_s = min(start_s + mel_len, n)
            length = end_s - start_s
            if length <= 0:
                continue
            note_t = np.linspace(0, melody_dur, length, endpoint=False)
            # Bright sine + light harmonic for xylophone-like timbre
            mel = 0.06 * np.sin(2 * np.pi * freq * note_t)
            mel += 0.02 * np.sin(2 * np.pi * freq * 2 * note_t)
            mel = mel * np.exp(-5.0 * note_t / melody_dur)
            result[start_s:end_s] += mel

    # --- Light percussion (hi-hat pattern using filtered noise) ---
    hat_dur = 0.03  # 30ms noise burst
    hat_samples = int(hat_dur * SAMPLE_RATE)
    for beat_idx in range(int(duration / (beat_dur / 2))):
        # Hi-hat on every eighth note
        hat_time = beat_idx * beat_dur / 2
        if hat_time >= duration:
            break
        start_s = int(hat_time * SAMPLE_RATE)
        end_s = min(start_s + hat_samples, n)
        length = end_s - start_s
        if length <= 0:
            continue
        # Noise burst with fast decay = hi-hat
        hat = 0.03 * np.random.uniform(-1, 1, length)
        hat_env = np.exp(-30.0 * np.linspace(0, 1, length))
        # Accent on downbeats (beats 0 and 2)
        accent = 1.5 if beat_idx % 4 == 0 else 1.0
        result[start_s:end_s] += hat * hat_env * accent

    # Normalize to prevent clipping
    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak * 0.85

    # Crossfade start/end for seamless looping (100ms fade)
    fade_samples = int(0.1 * SAMPLE_RATE)
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    result[:fade_samples] *= fade_in
    result[-fade_samples:] *= fade_out

    _save_wav(result, path)


# ============================================================
# Main generator — creates all missing SFX + music files
# ============================================================

def ensure_all_sfx():
    """
    # Generate any missing SFX and music files.
    # Called automatically at pipeline startup.
    # Skips files that already exist (user can replace with real audio).
    # This means the pipeline works out-of-the-box with zero assets.
    """
    # Map each SFX name to its generator function
    sfx_generators = {
        "tick": generate_tick,
        "ding": generate_ding,
        "whoosh": generate_whoosh,
        "applause": generate_applause,
        "drumroll": generate_drumroll,
        "jingle_intro": generate_jingle_intro,
        "jingle_outro": generate_jingle_outro,
    }

    # Also generate extra SFX not in the original config
    extra_sfx = {
        "correct": generate_correct_chime,
        "countdown_beep": generate_countdown_beep,
    }

    generated = []

    # Generate standard SFX from config paths
    for name, generator in sfx_generators.items():
        path = config.SFX_FILES[name]
        if not path.exists():
            print(f"[SFX GEN] Generating {name}.wav...")
            generator(path)
            generated.append(name)

    # Generate extra SFX
    for name, generator in extra_sfx.items():
        path = config.SFX_DIR / f"{name}.wav"
        if not path.exists():
            print(f"[SFX GEN] Generating {name}.wav...")
            generator(path)
            generated.append(name)

    # Generate default background music if none exists
    bgm_path = config.MUSIC_DIR / "default_bgm.wav"
    if not bgm_path.exists() and not any(config.MUSIC_DIR.glob("*.mp3")):
        print("[SFX GEN] Generating default background music...")
        generate_bgm(bgm_path)
        generated.append("bgm")

    if generated:
        print(f"[SFX GEN] Generated {len(generated)} audio files: {', '.join(generated)}")
    else:
        print("[SFX GEN] All audio files already exist — skipping generation")

    return generated
