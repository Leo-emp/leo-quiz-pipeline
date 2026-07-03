# tests/test_integration.py
# ============================================================
# Integration tests for Leo Quiz pipeline.
# Tests offline components working together (no API calls).
# API-dependent steps (Gemini, ElevenLabs) are skipped in CI.
# ============================================================
import pytest
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np

def _create_test_assets(tmp_path):
    """# Helper: create minimal test assets for pipeline testing."""
    # Create test image (white bg with colored circle as "subject")
    img = Image.new("RGB", (512, 512), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([100, 100, 400, 400], fill=(200, 100, 50))
    img_path = tmp_path / "test_image.png"
    img.save(img_path)

    # Create test silhouette from the image
    from silhouette import extract_silhouette
    sil_path = tmp_path / "test_silhouette.png"
    extract_silhouette(img_path, sil_path)

    return img_path, sil_path


def test_frame_composer_full_flow(tmp_path):
    """# Compose question → countdown → reveal frames without crashing."""
    from frame_composer import (
        compose_question_frame, compose_countdown_frame, compose_reveal_frame
    )
    img_path, sil_path = _create_test_assets(tmp_path)

    # Question frame with silhouette
    q_frame = compose_question_frame(
        "animals", sil_path, "What animal is this?",
        score=0, round_num=1, total_rounds=5
    )
    assert q_frame.size == (1080, 1920)

    # Countdown frame with number overlay
    cd_frame = compose_countdown_frame(
        "animals", sil_path, 3,
        score=0, round_num=1, total_rounds=5
    )
    assert cd_frame.size == (1080, 1920)

    # Reveal frame with full color image
    r_frame = compose_reveal_frame(
        "animals", img_path, "Lion", "Lions sleep 20 hours!",
        score=1, round_num=1, total_rounds=5
    )
    assert r_frame.size == (1080, 1920)


def test_video_context_creation(tmp_path):
    """# VideoContext should build correctly with test data."""
    from video_assembler import VideoContext, build_full_timeline
    from animations import ParticleSystem
    from quiz_generator import QuizRound

    img_path, sil_path = _create_test_assets(tmp_path)

    rounds = [QuizRound("Lion", "q", "f", "easy", "p")]
    timeline = build_full_timeline(1)

    ctx = VideoContext(
        width=1080, height=1920,
        category="animals",
        rounds=rounds,
        image_paths=[img_path],
        silhouette_paths=[sil_path],
        mascot_images={},
        particle_system=ParticleSystem(1080, 1920, count=5),
        timeline=timeline,
    )

    # Timeline: intro + 6 round events + outro = 8
    assert len(ctx.timeline) >= 7
    assert ctx.width == 1080


def test_thumbnail_generation(tmp_path):
    """# Thumbnail should generate from test assets."""
    from thumbnail import generate_thumbnail
    from quiz_generator import QuizPack, QuizRound

    img_path, sil_path = _create_test_assets(tmp_path)
    pack = QuizPack("animals", [QuizRound("Lion", "q", "f", "easy", "p")])

    result = generate_thumbnail(pack, [img_path], [sil_path],
                                 tmp_path / "thumb.png")
    assert result.exists()
    thumb = Image.open(result)
    assert thumb.size == (1280, 720)


def test_render_frame_with_round_data(tmp_path):
    """# render_frame should produce correct output during a quiz round."""
    from video_assembler import render_frame, VideoContext, build_full_timeline
    from animations import ParticleSystem
    from quiz_generator import QuizRound

    img_path, sil_path = _create_test_assets(tmp_path)

    rounds = [QuizRound("Lion", "King of the jungle!", "Lions sleep 20 hours!", "easy", "p")]
    timeline = build_full_timeline(1)

    ctx = VideoContext(
        width=1080, height=1920,
        category="animals",
        rounds=rounds,
        image_paths=[img_path],
        silhouette_paths=[sil_path],
        mascot_images={},
        particle_system=ParticleSystem(1080, 1920, count=5),
        timeline=timeline,
    )

    # Test intro frame (t=0.5)
    intro_frame = render_frame(0.5, ctx)
    assert intro_frame.shape == (1920, 1080, 3)

    # Test silhouette phase (t=2.5, within first round)
    sil_frame = render_frame(2.5, ctx)
    assert sil_frame.shape == (1920, 1080, 3)

    # Test reveal phase (t=7.5)
    reveal_frame = render_frame(7.5, ctx)
    assert reveal_frame.shape == (1920, 1080, 3)

    # Frames should be different (different content rendered)
    assert not np.array_equal(intro_frame, reveal_frame)
