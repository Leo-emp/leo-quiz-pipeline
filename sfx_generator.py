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


def _simple_reverb(samples: np.ndarray, decay: float = 0.3,
                   delays_ms: list = None) -> np.ndarray:
    """
    # Simulate reverb by mixing in delayed copies of the signal.
    # Creates spatial depth — sounds less dry and robotic.
    # decay: volume multiplier per echo (0.0-1.0).
    """
    if delays_ms is None:
        delays_ms = [23, 47, 73, 97]  # Prime-number ms delays for natural feel
    result = samples.copy().astype(np.float64)
    for i, delay in enumerate(delays_ms):
        delay_samples = int(delay * SAMPLE_RATE / 1000)
        echo_volume = decay * (0.7 ** i)  # Each echo quieter
        if delay_samples < len(result):
            padded = np.zeros(len(result))
            padded[delay_samples:] = samples[:len(samples) - delay_samples] * echo_volume
            result += padded
    # Normalize to prevent clipping
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result /= peak
    return result


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
    # Rich bell tone for answer reveal (600ms).
    # 880Hz fundamental + 4 harmonics + slight detuning for warmth.
    # Reverb gives it spatial depth. Sounds like a real game show bell.
    """
    duration = 0.6
    # Fundamental + 4 harmonics for metallic richness
    fundamental = _sine_wave(880, duration, 0.5)
    harmonic2 = _sine_wave(1760, duration, 0.22)
    harmonic3 = _sine_wave(2640, duration, 0.10)
    harmonic4 = _sine_wave(3520, duration, 0.05)
    # Slight detune on fundamental for chorus/shimmer
    detuned = _sine_wave(882, duration, 0.15)
    bell = fundamental + harmonic2 + harmonic3 + harmonic4 + detuned
    bell = _exponential_decay(bell, decay_rate=3.5)
    # Reverb for spatial depth
    bell = _simple_reverb(bell, decay=0.25)
    _save_wav(bell, path)


def generate_whoosh(path: Path):
    """
    # Rich swoosh/transition sound (300ms).
    # Frequency-swept noise + sine sweep for tonal character.
    # Reverb tail makes it feel like it's moving through space.
    """
    duration = 0.3
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # Noise layer
    raw_noise = _noise(duration, 0.3)
    # Sine sweep (high to low) for tonal whoosh character
    sweep_freq = 2000 - 1500 * t / duration
    tonal = 0.15 * np.sin(2 * np.pi * np.cumsum(sweep_freq) / SAMPLE_RATE)
    combined = raw_noise + tonal
    # Asymmetric envelope: fast rise, longer tail
    env = np.concatenate([
        np.linspace(0, 1, n // 4),     # Quick rise
        np.linspace(1, 0, n - n // 4), # Longer fall
    ])
    whoosh = combined * env
    whoosh = _simple_reverb(whoosh, decay=0.2, delays_ms=[15, 33, 51])
    _save_wav(whoosh, path)


def generate_applause(path: Path):
    """
    # Realistic-sounding applause (1.5s).
    # Multiple clap layers at different rates + crowd murmur layer.
    # Bandpass effect via mixing filtered noise bands.
    # Reverb simulates a room/hall environment.
    """
    duration = 1.5
    n = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n)
    result = np.zeros(n)

    # Layer 1: Fast individual claps (sharp bursts at ~14/sec)
    clap_rate = 14
    clap_dur = 0.012
    clap_samples = int(clap_dur * SAMPLE_RATE)
    rng = np.random.RandomState(7)
    for i in range(int(clap_rate * duration)):
        # Slight timing randomization for naturalness
        pos = int((i / clap_rate + rng.uniform(-0.01, 0.01)) * SAMPLE_RATE)
        if pos < 0 or pos + clap_samples > n:
            continue
        clap = rng.uniform(-1, 1, clap_samples) * 0.25
        clap *= np.exp(-40.0 * np.linspace(0, 1, clap_samples))
        # Random volume per clap for organic feel
        clap *= rng.uniform(0.5, 1.2)
        result[pos:pos + clap_samples] += clap

    # Layer 2: Slower claps at different phase (~9/sec)
    for i in range(int(9 * duration)):
        pos = int((i / 9.0 + 0.02 + rng.uniform(-0.015, 0.015)) * SAMPLE_RATE)
        if pos < 0 or pos + clap_samples > n:
            continue
        clap = rng.uniform(-1, 1, clap_samples) * 0.18
        clap *= np.exp(-35.0 * np.linspace(0, 1, clap_samples))
        result[pos:pos + clap_samples] += clap

    # Layer 3: Low crowd murmur (filtered noise, adds body)
    murmur = _noise(duration, 0.06)
    # Simple low-pass effect via running average
    kernel_size = 8
    murmur = np.convolve(murmur, np.ones(kernel_size) / kernel_size, mode='same')
    result += murmur

    # Overall ADSR envelope
    result = _envelope(result, attack=0.08, decay=0.1, sustain=0.85, release=0.3)
    # Reverb for room feel
    result = _simple_reverb(result, decay=0.2, delays_ms=[31, 67, 103])
    _save_wav(result, path)


def generate_drumroll(path: Path):
    """
    # Tension-building drumroll (1.2s).
    # Alternating stick hits on a snare-like surface.
    # Accelerating rhythm + crescendo + tonal body.
    # Reverb adds room ambience for studio feel.
    """
    duration = 1.2
    n = int(SAMPLE_RATE * duration)
    result = np.zeros(n)
    rng = np.random.RandomState(42)

    # Accelerating hits: start at 12/sec, end at 30/sec
    total_hits = 28
    for i in range(total_hits):
        progress = i / total_hits
        # Accelerating timing (quadratic)
        hit_time = duration * (progress ** 0.7)
        pos = int(hit_time * SAMPLE_RATE)
        if pos >= n:
            break

        hit_dur = 0.02
        hit_samples = int(hit_dur * SAMPLE_RATE)
        if pos + hit_samples > n:
            hit_samples = n - pos

        # Drum hit = noise burst + tonal body (80Hz fundamental)
        hit_t = np.linspace(0, hit_dur, hit_samples, endpoint=False)
        hit_noise = rng.uniform(-1, 1, hit_samples) * 0.35
        hit_tone = 0.3 * np.sin(2 * np.pi * 80 * hit_t)
        hit = (hit_noise + hit_tone) * np.exp(-35.0 * hit_t / hit_dur)

        # Crescendo + alternating L/R volume for realism
        volume = 0.25 + 0.75 * progress
        # Slight volume variation per hit
        volume *= rng.uniform(0.85, 1.15)
        result[pos:pos + hit_samples] += hit * volume

    # Normalize
    result = np.clip(result, -1.0, 1.0)
    # Room reverb
    result = _simple_reverb(result, decay=0.15, delays_ms=[19, 41, 67])
    _save_wav(result, path)


def generate_correct_chime(path: Path):
    """
    # Happy three-tone ascending chime for correct reveals (400ms).
    # C5→E5→G5 — a major triad arpeggio. Each note has harmonics
    # and slight chorus detune for warmth. Reverb tail adds polish.
    """
    note_dur = 0.12

    def _rich_note(freq, dur, amp):
        """# Single note with harmonics + detune for warmth."""
        note = _sine_wave(freq, dur, amp * 0.7)
        note += _sine_wave(freq * 2, dur, amp * 0.2)
        note += _sine_wave(freq * 1.002, dur, amp * 0.1)  # Chorus detune
        return _exponential_decay(note, 5.0)

    note1 = _rich_note(523.25, note_dur, 0.6)
    note2 = _rich_note(659.25, note_dur, 0.65)
    note3 = _rich_note(783.99, note_dur, 0.7)  # G5 — completes major triad
    gap = np.zeros(int(SAMPLE_RATE * 0.015))
    chime = np.concatenate([note1, gap, note2, gap, note3])
    chime = _simple_reverb(chime, decay=0.25)
    _save_wav(chime, path)


def generate_jingle_intro(path: Path):
    """
    # Ascending 4-note melody for video intro (1.2s).
    # C5→E5→G5→C6: a rising major arpeggio with harmonics.
    # Chorus detune + reverb for polished, broadcast-quality feel.
    """
    freqs = [523.25, 659.25, 783.99, 1046.50]
    note_dur = 0.25
    gap_dur = 0.04

    parts = []
    for i, freq in enumerate(freqs):
        # Rich timbre: fundamental + 3 harmonics + chorus detune
        note = _sine_wave(freq, note_dur, 0.45)
        note += _sine_wave(freq * 2, note_dur, 0.15)
        note += _sine_wave(freq * 3, note_dur, 0.06)
        note += _sine_wave(freq * 1.003, note_dur, 0.12)  # Chorus
        note = _exponential_decay(note, 2.8)
        note *= (0.7 + 0.3 * (i / len(freqs)))
        parts.append(note)
        if i < len(freqs) - 1:
            parts.append(np.zeros(int(SAMPLE_RATE * gap_dur)))

    jingle = np.concatenate(parts)
    jingle = _simple_reverb(jingle, decay=0.3)
    _save_wav(jingle, path)


def generate_jingle_outro(path: Path):
    """
    # Descending melody for video outro (1.5s).
    # C6→G5→E5→C5→C4: falling arpeggio with final resolving chord.
    # Harmonics + chorus + reverb for polished broadcast feel.
    """
    freqs = [1046.50, 783.99, 659.25, 523.25, 261.63]
    note_dur = 0.25
    gap_dur = 0.025

    parts = []
    for i, freq in enumerate(freqs):
        if i == len(freqs) - 1:
            # Final note: full C major chord (C4+E4+G4) for resolution
            dur = 0.5
            note = _sine_wave(freq, dur, 0.45)
            note += _sine_wave(freq * 5 / 4, dur, 0.2)  # E4
            note += _sine_wave(freq * 3 / 2, dur, 0.15)  # G4
            note += _sine_wave(freq * 1.002, dur, 0.1)  # Chorus
            note = _exponential_decay(note, 1.8)
        else:
            note = _sine_wave(freq, note_dur, 0.45)
            note += _sine_wave(freq * 2, note_dur, 0.12)
            note += _sine_wave(freq * 1.003, note_dur, 0.1)
            note = _exponential_decay(note, 3.5)
        parts.append(note)
        if i < len(freqs) - 1:
            parts.append(np.zeros(int(SAMPLE_RATE * gap_dur)))

    jingle = np.concatenate(parts)
    jingle = _simple_reverb(jingle, decay=0.35)
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
# Category-specific BGM — each quiz category gets its own vibe
# ============================================================

# Musical signatures per category: key root, scale, BPM, timbre
CATEGORY_MUSIC = {
    "animals": {
        "bpm": 115,
        # A minor pentatonic — warm, nature-like feel
        "chords": [
            [220.00, 261.63, 329.63],  # Am: A3, C4, E4
            [261.63, 329.63, 392.00],  # C:  C4, E4, G4
            [196.00, 246.94, 293.66],  # G:  G3, B3, D4
            [174.61, 220.00, 261.63],  # F:  F3, A3, C4
        ],
        "bass": [110.00, 130.81, 98.00, 87.31],
        "melody": [523.25, 587.33, 659.25, 783.99, 880.00],
        "hat_rate": 2,      # Relaxed hi-hat pace
        "pad_vol": 0.07,    # Soft nature pad
        "bass_vol": 0.10,
    },
    "dinosaurs": {
        "bpm": 100,
        # D minor — dramatic, prehistoric tension
        "chords": [
            [146.83, 174.61, 220.00],  # Dm: D3, F3, A3
            [130.81, 164.81, 196.00],  # Cm: C3, Eb3, G3
            [155.56, 185.00, 233.08],  # Eb: Eb3, G3, Bb3
            [146.83, 174.61, 220.00],  # Dm resolve
        ],
        "bass": [73.42, 65.41, 77.78, 73.42],
        "melody": [293.66, 349.23, 392.00, 440.00, 523.25],
        "hat_rate": 4,      # Slower, heavier feel
        "pad_vol": 0.09,    # Deeper pads
        "bass_vol": 0.14,   # Heavier bass
    },
    "space": {
        "bpm": 90,
        # Cmaj7/Em — ethereal, floating, cosmic
        "chords": [
            [261.63, 329.63, 493.88],  # Cmaj7: C4, E4, B4
            [329.63, 392.00, 493.88],  # Em:    E4, G4, B4
            [220.00, 261.63, 329.63],  # Am:    A3, C4, E4
            [246.94, 329.63, 392.00],  # Em/B:  B3, E4, G4
        ],
        "bass": [65.41, 82.41, 55.00, 61.74],  # Deep sub bass
        "melody": [523.25, 659.25, 783.99, 987.77, 1046.50],
        "hat_rate": 1,      # Sparse, atmospheric
        "pad_vol": 0.10,    # Lush pads
        "bass_vol": 0.08,   # Subtle sub
    },
    "vehicles": {
        "bpm": 135,
        # E major — energetic, driving, fast
        "chords": [
            [329.63, 415.30, 493.88],  # E:  E4, G#4, B4
            [220.00, 277.18, 329.63],  # A:  A3, C#4, E4
            [246.94, 311.13, 369.99],  # B:  B3, D#4, F#4
            [329.63, 415.30, 493.88],  # E resolve
        ],
        "bass": [82.41, 110.00, 123.47, 82.41],
        "melody": [659.25, 783.99, 880.00, 987.77, 1046.50],
        "hat_rate": 2,      # Fast 8th notes
        "pad_vol": 0.06,    # Lighter pad
        "bass_vol": 0.13,   # Punchy bass
    },
    "fruits": {
        "bpm": 125,
        # G major — bright, happy, tropical
        "chords": [
            [392.00, 493.88, 587.33],  # G:  G4, B4, D5
            [261.63, 329.63, 392.00],  # C:  C4, E4, G4
            [293.66, 369.99, 440.00],  # D:  D4, F#4, A4
            [329.63, 392.00, 493.88],  # Em: E4, G4, B4
        ],
        "bass": [98.00, 130.81, 146.83, 82.41],
        "melody": [783.99, 880.00, 987.77, 1046.50, 1174.66],
        "hat_rate": 2,
        "pad_vol": 0.07,
        "bass_vol": 0.11,
    },
    "flags": {
        "bpm": 110,
        # F major — warm, adventurous, world-music feel
        "chords": [
            [174.61, 220.00, 261.63],  # F:  F3, A3, C4
            [196.00, 246.94, 293.66],  # G:  G3, B3, D4
            [220.00, 261.63, 329.63],  # Am: A3, C4, E4
            [174.61, 220.00, 261.63],  # F resolve
        ],
        "bass": [87.31, 98.00, 110.00, 87.31],
        "melody": [523.25, 587.33, 659.25, 783.99, 880.00],
        "hat_rate": 3,      # Moderate
        "pad_vol": 0.08,
        "bass_vol": 0.11,
    },
}


def generate_category_bgm(category: str, path: Path, duration: float = 30.0):
    """
    # Generate category-specific background music.
    # Each category gets its own key, tempo, and feel.
    # Falls back to default BGM if category not found.
    """
    if category not in CATEGORY_MUSIC:
        return generate_bgm(path, duration)

    spec = CATEGORY_MUSIC[category]
    n = int(SAMPLE_RATE * duration)
    result = np.zeros(n)
    bpm = spec["bpm"]
    beat_dur = 60.0 / bpm
    chord_dur = 4 * beat_dur  # 4 beats per chord

    chords = spec["chords"]
    pad_vol = spec["pad_vol"]
    bass_vol = spec["bass_vol"]

    # --- Chord pad layer ---
    for chord_idx, chord_notes in enumerate(chords):
        for repeat in range(int(duration / (len(chords) * chord_dur)) + 1):
            chord_start = (repeat * len(chords) + chord_idx) * chord_dur
            if chord_start >= duration:
                break
            for note_freq in chord_notes:
                start_s = int(chord_start * SAMPLE_RATE)
                end_s = min(int((chord_start + chord_dur) * SAMPLE_RATE), n)
                if start_s >= n:
                    break
                length = end_s - start_s
                if length <= 0:
                    continue
                note_t = np.linspace(0, chord_dur, length, endpoint=False)
                # Sine pad + slight detune for warmth
                note = pad_vol * np.sin(2 * np.pi * note_freq * note_t)
                note += pad_vol * 0.3 * np.sin(2 * np.pi * note_freq * 1.003 * note_t)
                # Smooth envelope
                fade = min(int(0.08 * SAMPLE_RATE), length // 4)
                env = np.ones(length)
                env[:fade] = np.linspace(0, 1, fade)
                env[-fade:] = np.linspace(1, 0, fade)
                note *= env
                result[start_s:end_s] += note

    # --- Bass line ---
    for chord_idx, bass_freq in enumerate(spec["bass"]):
        for repeat in range(int(duration / (len(spec["bass"]) * chord_dur)) + 1):
            chord_start = (repeat * len(spec["bass"]) + chord_idx) * chord_dur
            if chord_start >= duration:
                break
            for beat in [0, 2]:
                beat_start = chord_start + beat * beat_dur
                if beat_start >= duration:
                    break
                start_s = int(beat_start * SAMPLE_RATE)
                note_len = int(beat_dur * 0.7 * SAMPLE_RATE)
                end_s = min(start_s + note_len, n)
                length = end_s - start_s
                if length <= 0:
                    continue
                note_t = np.linspace(0, beat_dur * 0.7, length, endpoint=False)
                bass = bass_vol * np.sin(2 * np.pi * bass_freq * note_t)
                # Sub-harmonic for weight
                bass += bass_vol * 0.5 * np.sin(2 * np.pi * bass_freq * 0.5 * note_t)
                bass *= np.exp(-3.5 * note_t / (beat_dur * 0.7))
                result[start_s:end_s] += bass

    # --- Melody (pentatonic, deterministic per category) ---
    melody_notes = spec["melody"]
    seed = sum(ord(c) for c in category)
    rng = np.random.RandomState(seed)
    melody_dur = beat_dur * 0.35
    for beat_idx in range(int(duration / beat_dur)):
        if beat_idx % 2 == 1:
            beat_time = beat_idx * beat_dur
            if beat_time >= duration:
                break
            freq = melody_notes[rng.randint(0, len(melody_notes))]
            start_s = int(beat_time * SAMPLE_RATE)
            mel_len = int(melody_dur * SAMPLE_RATE)
            end_s = min(start_s + mel_len, n)
            length = end_s - start_s
            if length <= 0:
                continue
            note_t = np.linspace(0, melody_dur, length, endpoint=False)
            mel = 0.05 * np.sin(2 * np.pi * freq * note_t)
            mel += 0.015 * np.sin(2 * np.pi * freq * 2 * note_t)
            mel += 0.008 * np.sin(2 * np.pi * freq * 3 * note_t)
            mel *= np.exp(-5.0 * note_t / melody_dur)
            result[start_s:end_s] += mel

    # --- Percussion ---
    hat_dur = 0.025
    hat_samples = int(hat_dur * SAMPLE_RATE)
    hat_interval = beat_dur / spec["hat_rate"]
    for beat_idx in range(int(duration / hat_interval)):
        hat_time = beat_idx * hat_interval
        if hat_time >= duration:
            break
        start_s = int(hat_time * SAMPLE_RATE)
        end_s = min(start_s + hat_samples, n)
        length = end_s - start_s
        if length <= 0:
            continue
        hat = 0.025 * np.random.uniform(-1, 1, length)
        hat *= np.exp(-35.0 * np.linspace(0, 1, length))
        accent = 1.4 if beat_idx % (spec["hat_rate"] * 2) == 0 else 1.0
        result[start_s:end_s] += hat * accent

    # --- Kick drum on beats 1 and 3 ---
    kick_dur = 0.06
    kick_samples = int(kick_dur * SAMPLE_RATE)
    for beat_idx in range(int(duration / beat_dur)):
        if beat_idx % 2 == 0:
            kick_time = beat_idx * beat_dur
            if kick_time >= duration:
                break
            start_s = int(kick_time * SAMPLE_RATE)
            end_s = min(start_s + kick_samples, n)
            length = end_s - start_s
            if length <= 0:
                continue
            kick_t = np.linspace(0, kick_dur, length, endpoint=False)
            # Sine sweep from 150Hz to 50Hz = punchy kick
            freq_sweep = 150 - 100 * kick_t / kick_dur
            kick = 0.12 * np.sin(2 * np.pi * freq_sweep * kick_t)
            kick *= np.exp(-25.0 * kick_t / kick_dur)
            result[start_s:end_s] += kick

    # Light reverb for room ambience on all layers
    result = _simple_reverb(result, decay=0.15, delays_ms=[29, 59, 89])

    # Normalize
    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak * 0.85

    # Seamless loop crossfade
    fade_samples = int(0.1 * SAMPLE_RATE)
    result[:fade_samples] *= np.linspace(0, 1, fade_samples)
    result[-fade_samples:] *= np.linspace(1, 0, fade_samples)

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

    # Generate category-specific background music for each quiz category
    for category in config.CATEGORIES:
        bgm_path = config.MUSIC_DIR / f"{category}.wav"
        if not bgm_path.exists():
            print(f"[SFX GEN] Generating {category} background music...")
            generate_category_bgm(category, bgm_path)
            generated.append(f"bgm_{category}")

    # Also generate default BGM as fallback
    bgm_path = config.MUSIC_DIR / "default_bgm.wav"
    if not bgm_path.exists():
        print("[SFX GEN] Generating default background music...")
        generate_bgm(bgm_path)
        generated.append("bgm")

    if generated:
        print(f"[SFX GEN] Generated {len(generated)} audio files: {', '.join(generated)}")
    else:
        print("[SFX GEN] All audio files already exist — skipping generation")

    return generated
