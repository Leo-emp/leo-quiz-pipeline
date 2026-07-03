# tests/test_silhouette.py
import pytest
import numpy as np
from pathlib import Path
from PIL import Image

def _create_test_image(path: Path, bg_color=(255, 255, 255), subject_color=(200, 50, 30)):
    """# Helper: create a test image with a colored shape on white background."""
    img = Image.new("RGB", (512, 512), bg_color)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # Draw a circle in the center as the "subject"
    draw.ellipse([156, 156, 356, 356], fill=subject_color)
    img.save(path)
    return path

def test_extract_silhouette_creates_black_shape(tmp_path):
    """# Silhouette should convert subject to pure black on transparent bg."""
    from silhouette import extract_silhouette
    input_path = _create_test_image(tmp_path / "test_input.png")
    output_path = tmp_path / "test_silhouette.png"

    result = extract_silhouette(input_path, output_path)
    assert result.exists()

    # Load and verify — should have alpha channel (RGBA)
    sil = Image.open(result)
    assert sil.mode == "RGBA"

    # The subject area should be black and opaque
    arr = np.array(sil)
    center = arr[256, 256]
    assert center[0] < 30   # R near 0
    assert center[1] < 30   # G near 0
    assert center[2] < 30   # B near 0
    assert center[3] > 200  # A near 255 (opaque)

    # Corner pixel should be transparent
    corner = arr[10, 10]
    assert corner[3] < 30   # A near 0 (transparent)

def test_validate_silhouette_good(tmp_path):
    """# A silhouette with reasonable coverage should pass validation."""
    from silhouette import extract_silhouette, validate_silhouette
    input_path = _create_test_image(tmp_path / "test_input.png")
    sil_path = extract_silhouette(input_path, tmp_path / "test_sil.png")
    assert validate_silhouette(sil_path) is True

def test_validate_silhouette_too_small(tmp_path):
    """# A silhouette with tiny coverage (<5%) should fail validation."""
    from silhouette import validate_silhouette
    # Create a nearly empty image (tiny dot)
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([250, 250, 255, 255], fill=(0, 0, 0, 255))
    path = tmp_path / "tiny.png"
    img.save(path)
    assert validate_silhouette(path) is False
