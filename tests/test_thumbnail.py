# tests/test_thumbnail.py
import pytest
from pathlib import Path
from PIL import Image, ImageDraw

def _make_test_image(path, color=(200, 50, 30)):
    """# Helper: create test image with colored circle on white bg."""
    img = Image.new("RGBA", (512, 512), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([100, 100, 400, 400], fill=color + (255,))
    img.save(path)
    return path

def _make_test_silhouette(path):
    """# Helper: create test silhouette (black circle on transparent bg)."""
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([100, 100, 400, 400], fill=(0, 0, 0, 255))
    img.save(path)
    return path

def test_generate_thumbnail(tmp_path):
    """# Should create a 1280x720 thumbnail with split layout."""
    from thumbnail import generate_thumbnail
    from quiz_generator import QuizPack, QuizRound

    img_path = _make_test_image(tmp_path / "img.png")
    sil_path = _make_test_silhouette(tmp_path / "sil.png")

    pack = QuizPack(
        category="animals",
        rounds=[QuizRound("Lion", "q", "f", "easy", "p")]
    )

    out = tmp_path / "thumb.png"
    result = generate_thumbnail(pack, [img_path], [sil_path], out)
    assert result.exists()

    thumb = Image.open(result)
    assert thumb.size == (1280, 720)
