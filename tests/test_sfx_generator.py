# tests/test_sfx_generator.py
import pytest
import wave
import numpy as np
from pathlib import Path


def test_save_wav_creates_file(tmp_path):
    """# _save_wav should create a valid WAV file from numpy array."""
    from sfx_generator import _save_wav
    samples = np.sin(np.linspace(0, 2 * np.pi * 440, 44100)).astype(np.float64)
    path = tmp_path / "test.wav"
    _save_wav(samples, path)
    assert path.exists()
    # Verify it's a valid WAV file
    with wave.open(str(path), "r") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100


def test_sine_wave_correct_length():
    """# _sine_wave should produce the correct number of samples."""
    from sfx_generator import _sine_wave
    samples = _sine_wave(440, 1.0)
    assert len(samples) == 44100  # 1 second at 44100 Hz


def test_noise_correct_length():
    """# _noise should produce the correct number of samples."""
    from sfx_generator import _noise
    samples = _noise(0.5)
    assert len(samples) == 22050  # 0.5 seconds at 44100 Hz


def test_generate_tick(tmp_path):
    """# generate_tick should create a short click WAV file."""
    from sfx_generator import generate_tick
    path = tmp_path / "tick.wav"
    generate_tick(path)
    assert path.exists()
    with wave.open(str(path), "r") as wf:
        duration = wf.getnframes() / wf.getframerate()
        assert duration == pytest.approx(0.05, abs=0.01)


def test_generate_ding(tmp_path):
    """# generate_ding should create a bell tone WAV file."""
    from sfx_generator import generate_ding
    path = tmp_path / "ding.wav"
    generate_ding(path)
    assert path.exists()
    with wave.open(str(path), "r") as wf:
        duration = wf.getnframes() / wf.getframerate()
        assert duration == pytest.approx(0.6, abs=0.05)


def test_generate_bgm(tmp_path):
    """# generate_bgm should create a 30-second music loop."""
    from sfx_generator import generate_bgm
    path = tmp_path / "bgm.wav"
    generate_bgm(path, duration=5.0)  # Short version for speed
    assert path.exists()
    with wave.open(str(path), "r") as wf:
        duration = wf.getnframes() / wf.getframerate()
        assert duration == pytest.approx(5.0, abs=0.1)


def test_ensure_all_sfx_generates_missing(tmp_path, monkeypatch):
    """# ensure_all_sfx should generate all missing SFX files."""
    import config
    # Point asset dirs to tmp_path so we don't pollute real assets
    monkeypatch.setattr(config, "SFX_DIR", tmp_path / "sfx")
    monkeypatch.setattr(config, "MUSIC_DIR", tmp_path / "music")
    # Update SFX_FILES to point to tmp_path
    for key in config.SFX_FILES:
        monkeypatch.setitem(config.SFX_FILES, key, tmp_path / "sfx" / f"{key}.wav")

    from sfx_generator import ensure_all_sfx
    generated = ensure_all_sfx()
    # Should have generated all standard SFX + extras + bgm
    assert len(generated) >= 8  # 7 standard + correct + countdown_beep + bgm


def test_exponential_decay():
    """# _exponential_decay should reduce amplitude over time."""
    from sfx_generator import _exponential_decay
    samples = np.ones(1000)
    decayed = _exponential_decay(samples, decay_rate=5.0)
    # First sample should be close to 1.0
    assert decayed[0] == pytest.approx(1.0, abs=0.01)
    # Last sample should be much smaller
    assert decayed[-1] < 0.01


def test_envelope_shapes_audio():
    """# _envelope should apply ADSR shape to audio."""
    from sfx_generator import _envelope
    samples = np.ones(44100)  # 1 second of constant 1.0
    shaped = _envelope(samples, attack=0.1, decay=0.1, sustain=0.5, release=0.2)
    # Attack: starts at 0
    assert shaped[0] == pytest.approx(0.0, abs=0.01)
    # Sustain: should be at sustain level
    assert shaped[22050] == pytest.approx(0.5, abs=0.1)
    # Release: ends at 0
    assert shaped[-1] == pytest.approx(0.0, abs=0.01)


def test_simple_reverb_adds_tail():
    """# _simple_reverb should add delayed echoes making the signal longer-sounding."""
    from sfx_generator import _simple_reverb
    # Create a short impulse (1 at start, 0 everywhere else)
    impulse = np.zeros(4410)  # 0.1 seconds
    impulse[0] = 1.0
    reverbed = _simple_reverb(impulse, decay=0.5)
    # Reverbed signal should have energy after the initial impulse
    # (the echoes at prime-number delays)
    assert np.sum(np.abs(reverbed[100:])) > 0.1


def test_simple_reverb_does_not_clip():
    """# _simple_reverb should normalize to prevent clipping."""
    from sfx_generator import _simple_reverb
    loud = np.ones(4410) * 0.9
    reverbed = _simple_reverb(loud, decay=0.5)
    assert np.max(np.abs(reverbed)) <= 1.0
