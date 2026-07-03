# tests/test_frame_composer.py
import pytest
from pathlib import Path
from PIL import Image
import numpy as np

def test_render_gradient_background():
    """# Should produce a gradient image with the right dimensions."""
    from frame_composer import render_gradient_background
    img = render_gradient_background(1080, 1920, "animals", t=0.0)
    assert img.size == (1080, 1920)
    assert img.mode == "RGB"
    # Top and bottom should be different colors (it's a gradient)
    arr = np.array(img)
    top_pixel = arr[10, 540]
    bottom_pixel = arr[1910, 540]
    assert not np.array_equal(top_pixel, bottom_pixel)

def test_render_text():
    """# Should draw text onto an image without crashing."""
    from frame_composer import render_text
    img = Image.new("RGBA", (1080, 1920), (50, 50, 50, 255))
    result = render_text(img, "Hello World!", position=(540, 960),
                         font_size=48, color=(255, 255, 255))
    assert result.size == (1080, 1920)
    # Some pixels should have changed (text was drawn)
    orig_arr = np.array(img)
    result_arr = np.array(result)
    assert not np.array_equal(orig_arr, result_arr)

def test_hex_to_rgb():
    """# Should convert hex color strings to RGB tuples."""
    from frame_composer import hex_to_rgb
    assert hex_to_rgb("#2ECC71") == (46, 204, 113)
    assert hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert hex_to_rgb("#000000") == (0, 0, 0)
