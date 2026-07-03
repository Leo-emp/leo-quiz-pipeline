# thumbnail.py
# ============================================================
# Auto-generated YouTube thumbnails for Leo Quiz videos.
# Split layout: silhouette on left, colorful reveal on right.
# Bold text, bright colors, Leo mascot — designed to pop in search.
# ============================================================
from pathlib import Path
from PIL import Image, ImageDraw

import config
from frame_composer import render_gradient_background, render_text, hex_to_rgb
from quiz_generator import QuizPack

# YouTube recommended thumbnail size
THUMB_SIZE = (1280, 720)


def generate_thumbnail(quiz_pack: QuizPack,
                        image_paths: list[Path],
                        silhouette_paths: list[Path],
                        output_path: Path) -> Path:
    """
    # Generate a YouTube thumbnail for a quiz video.
    # Layout: silhouette on left half, reveal image on right half,
    # "CAN YOU GUESS?" text at top, bright yellow border,
    # Leo mascot (surprised pose) in bottom-right.
    """
    w, h = THUMB_SIZE
    category = quiz_pack.category

    # Gradient background matching category theme
    bg = render_gradient_background(w, h, category, t=0.0)
    thumb = bg.convert("RGBA")

    # Bright yellow border (8px) — catches attention in search results
    draw = ImageDraw.Draw(thumb)
    border = 8
    draw.rectangle([0, 0, w - 1, h - 1], outline=(255, 230, 0, 255), width=border)

    # Left half: silhouette (mystery shape)
    if silhouette_paths:
        sil = Image.open(silhouette_paths[0]).convert("RGBA")
        sil_size = int(h * 0.6)
        sil = sil.resize((sil_size, sil_size), Image.LANCZOS)
        sil_x = w // 4 - sil_size // 2
        sil_y = (h - sil_size) // 2 + 30
        thumb.paste(sil, (sil_x, sil_y), sil)

    # Right half: colorful reveal image
    if image_paths:
        img = Image.open(image_paths[0]).convert("RGBA")
        img_size = int(h * 0.6)
        img = img.resize((img_size, img_size), Image.LANCZOS)
        img_x = 3 * w // 4 - img_size // 2
        img_y = (h - img_size) // 2 + 30
        thumb.paste(img, (img_x, img_y), img)

    # Big "?" between the two halves
    thumb = render_text(thumb, "?",
                        position=(w // 2, h // 2 + 30),
                        font_size=120,
                        color=(255, 255, 255),
                        stroke_color=(0, 0, 0), stroke_width=5)

    # "CAN YOU GUESS?" header text
    thumb = render_text(thumb, "CAN YOU GUESS?",
                        position=(w // 2, 60),
                        font_size=72,
                        color=(255, 255, 255),
                        stroke_color=(0, 0, 0), stroke_width=5)

    # Category subtitle at bottom
    cat_display = config.CATEGORIES[category]["display"]
    thumb = render_text(thumb, f"{cat_display}s Edition!",
                        position=(w // 2, h - 40),
                        font_size=36,
                        color=(255, 255, 200))

    # Leo mascot (surprised pose) in bottom-right if available
    surprised_path = config.MASCOT_POSES.get("surprised")
    if surprised_path and surprised_path.exists():
        mascot = Image.open(surprised_path).convert("RGBA")
        mascot_h = int(h * 0.35)
        mascot_w = int(mascot.width * (mascot_h / mascot.height))
        mascot = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
        thumb.paste(mascot, (w - mascot_w - 20, h - mascot_h - 60), mascot)

    # Save as high-quality PNG
    output_path.parent.mkdir(parents=True, exist_ok=True)
    thumb.convert("RGB").save(output_path, "PNG", quality=95)
    return output_path
