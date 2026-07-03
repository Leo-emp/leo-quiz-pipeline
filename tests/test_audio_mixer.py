# tests/test_audio_mixer.py
import pytest
from pathlib import Path
import wave

def _create_silent_wav(path: Path, duration_ms: int = 1000, sample_rate: int = 44100):
    """# Helper: create a silent WAV file for testing."""
    num_samples = int(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * num_samples)
    return path

def test_round_audio_dataclass():
    """# RoundAudio should hold paths to all audio clips for one round."""
    from narration import RoundAudio
    ra = RoundAudio(
        question_path=Path("q.wav"),
        reveal_path=Path("r.wav"),
        fact_path=Path("f.wav"),
        fact_timestamps=[{"word": "Lions", "start": 0.0, "end": 0.2}],
    )
    assert ra.question_path == Path("q.wav")
    assert len(ra.fact_timestamps) == 1

def test_normalize_audio(tmp_path):
    """# normalize_audio should adjust peak to target dB."""
    from audio_mixer import normalize_audio
    wav_path = _create_silent_wav(tmp_path / "test.wav", duration_ms=500)
    result = normalize_audio(wav_path, target_db=-3.0)
    assert result.exists()

def test_mix_layers_creates_output(tmp_path):
    """# mix_layers should combine multiple audio files into one output."""
    from audio_mixer import mix_layers
    track1 = _create_silent_wav(tmp_path / "track1.wav")
    track2 = _create_silent_wav(tmp_path / "track2.wav")
    output = tmp_path / "mixed.wav"
    result = mix_layers(
        layers=[(track1, 0, 1.0), (track2, 500, 0.5)],
        total_duration_ms=2000,
        output_path=output
    )
    assert result.exists()
