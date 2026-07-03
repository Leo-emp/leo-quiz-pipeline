# tests/test_animations.py
import pytest
import numpy as np

def test_ease_value_linear():
    """# ease_value should interpolate linearly when using linear easing."""
    from animations import ease_value
    # At t=0, should return start value
    assert ease_value("linear", 0.0, 1.0, 0.0, 100.0) == pytest.approx(0.0, abs=0.1)
    # At t=1.0 (end), should return end value
    assert ease_value("linear", 1.0, 1.0, 0.0, 100.0) == pytest.approx(100.0, abs=0.1)
    # At t=0.5 (middle), should return midpoint
    assert ease_value("linear", 0.5, 1.0, 0.0, 100.0) == pytest.approx(50.0, abs=1.0)

def test_ease_value_clamps():
    """# ease_value should clamp to start/end if t is outside duration."""
    from animations import ease_value
    # Before animation starts: return start
    assert ease_value("cubic_out", -0.5, 1.0, 0.0, 100.0) == pytest.approx(0.0, abs=0.1)
    # After animation ends: return end
    assert ease_value("cubic_out", 2.0, 1.0, 0.0, 100.0) == pytest.approx(100.0, abs=0.1)

def test_ease_value_back_out_overshoots():
    """# BackEaseOut should overshoot past end before settling."""
    from animations import ease_value
    # At end, should be at target
    end_val = ease_value("back_out", 1.0, 1.0, 0.0, 100.0)
    assert end_val == pytest.approx(100.0, abs=0.5)

def test_compute_scale():
    """# compute_scale should return 0.0 at start and 1.0 at end."""
    from animations import compute_scale
    assert compute_scale(0.0, 0.0, 0.5, "cubic_out") == pytest.approx(0.0, abs=0.05)
    assert compute_scale(0.5, 0.0, 0.5, "cubic_out") == pytest.approx(1.0, abs=0.05)

def test_compute_opacity():
    """# compute_opacity should return 0.0 at start and 1.0 at end."""
    from animations import compute_opacity
    assert compute_opacity(0.0, 0.0, 0.3, "quad_out") == pytest.approx(0.0, abs=0.05)
    assert compute_opacity(0.3, 0.0, 0.3, "quad_out") == pytest.approx(1.0, abs=0.05)

def test_compute_slide_x():
    """# compute_slide_x should move from off-screen to target position."""
    from animations import compute_slide_x
    frame_width = 1080
    # At start, should be off-screen (negative)
    x_start = compute_slide_x(0.0, 0.0, 0.4, frame_width, "left")
    assert x_start < 0
    # At end of animation, should be at center
    x_end = compute_slide_x(0.4, 0.0, 0.4, frame_width, "left")
    assert x_end == pytest.approx(frame_width // 2, abs=10)

def test_particle_system_render():
    """# ParticleSystem should composite sparkles onto a frame without crashing."""
    from animations import ParticleSystem
    ps = ParticleSystem(width=1080, height=1920, count=10)
    frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
    result = ps.render(frame, t=0.5)
    assert result.shape == (1920, 1080, 3)
    # At least some pixels should be non-zero (particles drawn)
    assert np.any(result > 0)
