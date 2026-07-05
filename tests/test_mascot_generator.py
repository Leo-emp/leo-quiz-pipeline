# tests/test_mascot_generator.py
# ============================================================
# Tests for the mascot generator module.
# Verifies PIL fallback rendering for all 4 poses,
# image dimensions, transparency, and mascot prompts.
# ============================================================
import pytest
from PIL import Image

from mascot_generator import _draw_simple_lion, MASCOT_PROMPTS


def test_all_poses_exist():
    """# MASCOT_PROMPTS should define all 4 required poses."""
    expected_poses = {"thinking", "excited", "waving", "surprised"}
    assert set(MASCOT_PROMPTS.keys()) == expected_poses


def test_draw_simple_lion_returns_rgba():
    """# PIL fallback mascot should be RGBA (transparent background)."""
    img = _draw_simple_lion("waving", size=256)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"


def test_draw_simple_lion_correct_size():
    """# Output image should match requested size."""
    for size in [256, 512]:
        img = _draw_simple_lion("thinking", size=size)
        assert img.size == (size, size)


def test_draw_simple_lion_all_poses():
    """# All 4 poses should render without error."""
    for pose in ["thinking", "excited", "waving", "surprised"]:
        img = _draw_simple_lion(pose, size=256)
        assert img.size == (256, 256)
        assert img.mode == "RGBA"


def test_draw_simple_lion_has_content():
    """# The mascot should have visible pixels (not fully transparent)."""
    img = _draw_simple_lion("excited", size=256)
    # Check alpha channel — should have both transparent and opaque pixels
    alpha = img.split()[3]
    pixels = list(alpha.getdata())
    opaque_count = sum(1 for p in pixels if p > 0)
    transparent_count = sum(1 for p in pixels if p == 0)
    # Should have both opaque content and transparent background
    assert opaque_count > 100, "Mascot has too few visible pixels"
    assert transparent_count > 100, "Mascot has too few transparent pixels"


def test_draw_simple_lion_poses_differ():
    """# Different poses should produce visually different images."""
    img_waving = _draw_simple_lion("waving", size=256)
    img_thinking = _draw_simple_lion("thinking", size=256)
    # Convert to raw bytes for comparison
    data_waving = list(img_waving.getdata())
    data_thinking = list(img_thinking.getdata())
    # They should not be identical (different arm/eye positions)
    assert data_waving != data_thinking
