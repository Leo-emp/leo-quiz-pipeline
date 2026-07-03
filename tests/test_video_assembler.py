# tests/test_video_assembler.py
import pytest
import numpy as np
from PIL import Image
from pathlib import Path

def test_build_round_timeline():
    """# build_round_timeline should return correct timing entries for one round."""
    from video_assembler import build_round_timeline
    timeline = build_round_timeline(round_index=0, round_start=2.0)
    # Should have entries for silhouette, countdown 3/2/1, reveal, fact
    assert len(timeline) >= 6
    # First entry should be silhouette phase starting at round_start
    assert timeline[0]["phase"] == "silhouette"
    assert timeline[0]["start"] == pytest.approx(2.0, abs=0.01)

def test_render_frame_returns_array():
    """# render_frame should return a numpy array of the correct size."""
    from video_assembler import render_frame, VideoContext
    # Create minimal context for testing
    ctx = VideoContext(
        width=1080, height=1920,
        category="animals",
        rounds=[],
        image_paths=[],
        silhouette_paths=[],
        mascot_images={},
        particle_system=None,
    )
    frame = render_frame(0.0, ctx)
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (1920, 1080, 3)
