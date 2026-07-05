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


def test_variant_b_giant_mystery(tmp_path):
    """# Variant B should create a 1280x720 thumbnail with giant silhouette."""
    from thumbnail import generate_thumbnail_variant_b
    from quiz_generator import QuizPack, QuizRound
    rounds = [QuizRound(answer="Lion", hint_question="?", fun_fact="fact",
                         difficulty="easy", image_prompt="lion")]
    pack = QuizPack(category="animals", rounds=rounds)
    sil_path = _make_test_silhouette(tmp_path / "sil.png")

    output = tmp_path / "thumb_b.png"
    generate_thumbnail_variant_b(pack, [sil_path], output)
    assert output.exists()
    img = Image.open(output)
    assert img.size == (1280, 720)


def test_variant_c_grid_challenge(tmp_path):
    """# Variant C should create a 1280x720 thumbnail with 2x2 grid."""
    from thumbnail import generate_thumbnail_variant_c
    from quiz_generator import QuizPack, QuizRound
    rounds = [QuizRound(answer=f"Animal{i}", hint_question="?", fun_fact="fact",
                         difficulty="easy", image_prompt="animal")
              for i in range(4)]
    pack = QuizPack(category="animals", rounds=rounds)
    sil_paths = [_make_test_silhouette(tmp_path / f"sil_{i}.png") for i in range(4)]

    output = tmp_path / "thumb_c.png"
    generate_thumbnail_variant_c(pack, sil_paths, output)
    assert output.exists()
    img = Image.open(output)
    assert img.size == (1280, 720)


def test_generate_all_thumbnails(tmp_path):
    """# generate_all_thumbnails should create 3 files (a, b, c)."""
    from thumbnail import generate_all_thumbnails
    from quiz_generator import QuizPack, QuizRound
    rounds = [QuizRound(answer=f"Animal{i}", hint_question="?", fun_fact="fact",
                         difficulty="easy", image_prompt="animal")
              for i in range(5)]
    pack = QuizPack(category="animals", rounds=rounds)
    img_paths = [_make_test_image(tmp_path / f"img_{i}.png") for i in range(5)]
    sil_paths = [_make_test_silhouette(tmp_path / f"sil_{i}.png") for i in range(5)]

    out_dir = tmp_path / "thumbs"
    out_dir.mkdir()
    result = generate_all_thumbnails(pack, img_paths, sil_paths, out_dir)
    assert (out_dir / "thumb_a.png").exists()
    assert (out_dir / "thumb_b.png").exists()
    assert (out_dir / "thumb_c.png").exists()
    assert len(result) == 3
