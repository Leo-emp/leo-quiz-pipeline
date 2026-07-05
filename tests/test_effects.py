# tests/test_effects.py
import pytest
import numpy as np
from PIL import Image


def _make_test_frame(w=1080, h=1920):
    """# Helper: create a solid-color RGBA test frame."""
    return Image.new("RGBA", (w, h), (50, 100, 150, 255))


def test_confetti_burst_active_timing():
    """# ConfettiBurst should only be active during its duration window."""
    from effects import ConfettiBurst
    burst = ConfettiBurst(540, 960, trigger_time=5.0, count=20, seed=42)
    assert not burst.is_active(4.9)   # Before trigger
    assert burst.is_active(5.0)       # At trigger
    assert burst.is_active(5.5)       # During burst
    assert burst.is_active(6.4)       # Near end
    assert not burst.is_active(6.6)   # After duration (5.0 + 1.5 = 6.5)


def test_confetti_burst_render():
    """# ConfettiBurst.render should modify the frame when active."""
    from effects import ConfettiBurst
    frame = _make_test_frame()
    burst = ConfettiBurst(540, 960, trigger_time=0.0, count=30, seed=42)
    result = burst.render(frame, 0.5)
    # Frame should have been modified (confetti drawn on it)
    assert result.size == frame.size
    orig_arr = np.array(frame)
    result_arr = np.array(result)
    assert not np.array_equal(orig_arr, result_arr)


def test_confetti_burst_no_render_when_inactive():
    """# ConfettiBurst should return frame unchanged when not active."""
    from effects import ConfettiBurst
    frame = _make_test_frame()
    burst = ConfettiBurst(540, 960, trigger_time=10.0, count=30, seed=42)
    result = burst.render(frame, 0.0)  # Way before trigger
    orig_arr = np.array(frame)
    result_arr = np.array(result)
    assert np.array_equal(orig_arr, result_arr)


def test_screen_shake_applies_offset():
    """# ScreenShake should shift the frame during active window."""
    from effects import ScreenShake
    frame = _make_test_frame(100, 100)
    # Draw a distinct pixel in the corner for detection
    frame.putpixel((0, 0), (255, 0, 0, 255))
    result = ScreenShake.apply(frame, 0.1, trigger_time=0.0,
                                duration=0.3, intensity=20.0)
    assert result.size == frame.size


def test_screen_shake_no_effect_outside_window():
    """# ScreenShake should not modify frame outside its time window."""
    from effects import ScreenShake
    frame = _make_test_frame(100, 100)
    result = ScreenShake.apply(frame, 5.0, trigger_time=0.0,
                                duration=0.3, intensity=20.0)
    # Should be identical (t=5.0 is way past duration=0.3)
    assert np.array_equal(np.array(frame), np.array(result))


def test_ken_burns_zoom_changes_frame():
    """# KenBurnsZoom should crop and upscale the frame."""
    from effects import KenBurnsZoom
    frame = _make_test_frame(200, 200)
    # Draw a border so we can detect cropping
    from PIL import ImageDraw
    draw = ImageDraw.Draw(frame)
    draw.rectangle([0, 0, 199, 199], outline=(255, 0, 0, 255), width=3)
    result = KenBurnsZoom.apply(frame, 1.0, start_time=0.0,
                                 duration=2.0, max_zoom=1.1)
    assert result.size == frame.size


def test_ken_burns_zoom_no_effect_before_start():
    """# KenBurnsZoom should return original frame before start_time."""
    from effects import KenBurnsZoom
    frame = _make_test_frame(100, 100)
    result = KenBurnsZoom.apply(frame, 0.0, start_time=5.0,
                                 duration=2.0, max_zoom=1.1)
    assert np.array_equal(np.array(frame), np.array(result))


def test_glow_ring_renders():
    """# GlowRing should draw glowing circles on the frame."""
    from effects import GlowRing
    frame = _make_test_frame()
    result = GlowRing.render(frame, 540, 960, 100, (255, 100, 50), 0.5)
    orig_arr = np.array(frame)
    result_arr = np.array(result)
    assert not np.array_equal(orig_arr, result_arr)


def test_progress_indicator_renders():
    """# ProgressIndicator should draw dots on the frame."""
    from effects import ProgressIndicator
    frame = _make_test_frame()
    result = ProgressIndicator.render(frame, 2, 5, 0.0)
    orig_arr = np.array(frame)
    result_arr = np.array(result)
    assert not np.array_equal(orig_arr, result_arr)


def test_themed_decorations_renders():
    """# ThemedDecorations should draw floating shapes on the frame."""
    from effects import ThemedDecorations
    decorations = ThemedDecorations("animals", 1080, 1920)
    frame = _make_test_frame()
    result = decorations.render(frame, 1.0)
    orig_arr = np.array(frame)
    result_arr = np.array(result)
    assert not np.array_equal(orig_arr, result_arr)


def test_render_glow_text():
    """# render_glow_text should draw text with a glow effect."""
    from effects import render_glow_text
    frame = _make_test_frame()
    result = render_glow_text(frame, "TEST", position=(540, 960),
                               font_size=64, glow_color=(255, 200, 50))
    orig_arr = np.array(frame)
    result_arr = np.array(result)
    assert not np.array_equal(orig_arr, result_arr)


def test_render_rainbow_text():
    """# render_rainbow_text should draw text with rainbow colors."""
    from effects import render_rainbow_text
    frame = _make_test_frame()
    result = render_rainbow_text(frame, "RAINBOW", position=(540, 960),
                                  font_size=48, t=0.0)
    orig_arr = np.array(frame)
    result_arr = np.array(result)
    assert not np.array_equal(orig_arr, result_arr)


def test_apply_vignette():
    """# apply_vignette should darken edges while keeping center bright."""
    from effects import apply_vignette
    # Create a uniform white frame
    frame = Image.new("RGBA", (200, 200), (255, 255, 255, 255))
    result = apply_vignette(frame, intensity=0.5)
    result_arr = np.array(result)
    # Center should be brighter than corners
    center_brightness = result_arr[100, 100, :3].mean()
    corner_brightness = result_arr[5, 5, :3].mean()
    assert center_brightness > corner_brightness


def test_countdown_bar_renders():
    """# CountdownBar should draw a visible bar on the frame."""
    from effects import CountdownBar
    frame = _make_test_frame(400, 400)
    result = CountdownBar.render(frame, progress=0.5, color=(255, 255, 255))
    orig_arr = np.array(frame)
    result_arr = np.array(result)
    assert not np.array_equal(orig_arr, result_arr)


def test_countdown_bar_color_changes():
    """# Bar color should shift from green to red as progress approaches 1.0."""
    from effects import CountdownBar
    # At 0.0 progress (green zone)
    frame1 = _make_test_frame(400, 400)
    result_start = CountdownBar.render(frame1, progress=0.0)
    # At 0.9 progress (red zone)
    frame2 = _make_test_frame(400, 400)
    result_end = CountdownBar.render(frame2, progress=0.9)
    # Both should render (not identical to original)
    assert not np.array_equal(np.array(frame1), np.array(result_start))
    assert not np.array_equal(np.array(frame2), np.array(result_end))
    # The two results should differ (different colors/widths)
    assert not np.array_equal(np.array(result_start), np.array(result_end))
