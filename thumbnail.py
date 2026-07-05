# thumbnail.py
# ============================================================
# Click-optimized YouTube thumbnails for Leo Quiz videos.
# MASSIVELY UPGRADED from v1: diagonal split layout, multiple
# silhouettes, emoji accents, glow effects, round count badge,
# brighter colors, bigger bolder text. Designed to maximize
# click-through rate in YouTube search/browse.
# ============================================================
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

import config
from frame_composer import render_gradient_background, render_text, hex_to_rgb, _get_font
from effects import render_glow_text, apply_vignette
from quiz_generator import QuizPack

# YouTube recommended thumbnail size (1280x720)
THUMB_SIZE = (1280, 720)


def _draw_diagonal_split(thumb: Image.Image, color: tuple) -> Image.Image:
    """
    # Draw a diagonal divider across the thumbnail.
    # Creates a dynamic split between silhouette and reveal sides.
    # More visually interesting than a straight vertical split.
    """
    draw = ImageDraw.Draw(thumb)
    w, h = thumb.size
    # Diagonal line from upper-center to lower-center
    # Creates two angled regions
    points = [(w // 2 - 50, 0), (w // 2 + 50, h)]
    # Draw thick diagonal band in bright color
    band_w = 8
    for offset in range(-band_w, band_w + 1):
        draw.line([(w // 2 - 50 + offset, 0), (w // 2 + 50 + offset, h)],
                  fill=color + (255,), width=1)
    return thumb


def _draw_badge(thumb: Image.Image, text: str,
                position: tuple, bg_color: tuple,
                text_color: tuple = (255, 255, 255)) -> Image.Image:
    """
    # Draw a rounded badge/pill with text (e.g., "5 ROUNDS!").
    # Used for attention-grabbing labels on thumbnails.
    """
    if thumb.mode != "RGBA":
        thumb = thumb.convert("RGBA")

    font = _get_font(32)
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x, pad_y = 20, 10

    # Badge background
    badge = Image.new("RGBA", thumb.size, (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(badge)
    badge_draw.rounded_rectangle([
        position[0] - text_w // 2 - pad_x,
        position[1] - text_h // 2 - pad_y,
        position[0] + text_w // 2 + pad_x,
        position[1] + text_h // 2 + pad_y,
    ], radius=12, fill=bg_color + (240,))
    thumb = Image.alpha_composite(thumb, badge)

    # Badge text
    draw = ImageDraw.Draw(thumb)
    draw.text(position, text, font=font, fill=text_color,
              anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))

    return thumb


def _draw_question_marks(thumb: Image.Image, count: int = 5) -> Image.Image:
    """
    # Scatter floating question marks across the thumbnail.
    # Creates curiosity and engagement — "what could it be?"
    """
    if thumb.mode != "RGBA":
        thumb = thumb.convert("RGBA")

    overlay = Image.new("RGBA", thumb.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Predetermined positions for question marks (avoid covering key content)
    positions = [
        (100, 150, 60, 120), (1180, 120, 50, 100),
        (150, 550, 45, 90), (1100, 580, 55, 110),
        (640, 650, 40, 80),
    ]

    for i, (x, y, size, alpha) in enumerate(positions[:count]):
        font = _get_font(size)
        color = (255, 255, 100, alpha)  # Yellow-ish, semi-transparent
        draw.text((x, y), "?", font=font, fill=color,
                  anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0, alpha))

    return Image.alpha_composite(thumb, overlay)


def generate_thumbnail(quiz_pack: QuizPack,
                        image_paths: list[Path],
                        silhouette_paths: list[Path],
                        output_path: Path) -> Path:
    """
    # Generate a click-optimized YouTube thumbnail.
    # UPGRADED LAYOUT:
    # - Top: "CAN YOU GUESS?" in huge glow text
    # - Left side: 2-3 silhouettes stacked (mystery shapes)
    # - Right side: One colorful reveal image (biggest, brightest)
    # - Diagonal divider between sides
    # - "5 ROUNDS!" badge in corner
    # - Scattered question marks for curiosity
    # - Leo mascot (surprised) in bottom-right
    # - Bright yellow border + vignette for depth
    """
    w, h = THUMB_SIZE
    category = quiz_pack.category
    colors = config.CATEGORY_COLORS[category]
    primary_rgb = hex_to_rgb(colors["primary"])

    # --- Background: category gradient ---
    bg = render_gradient_background(w, h, category, t=0.0)
    thumb = bg.convert("RGBA")

    # --- Bright yellow border (6px) — pops in search results ---
    draw = ImageDraw.Draw(thumb)
    border = 6
    draw.rectangle([0, 0, w - 1, h - 1], outline=(255, 230, 0, 255), width=border)

    # --- Diagonal split divider ---
    thumb = _draw_diagonal_split(thumb, (255, 255, 255))

    # --- Left side: Silhouettes (show 2-3 mystery shapes) ---
    num_sils = min(3, len(silhouette_paths))
    if num_sils >= 2:
        # Stack 2-3 smaller silhouettes vertically on left side
        sil_positions = [
            (w // 5, int(h * 0.32), int(h * 0.35)),  # Top-left
            (w // 4, int(h * 0.72), int(h * 0.30)),  # Bottom-left
        ]
        if num_sils >= 3:
            sil_positions.append((w // 8, int(h * 0.52), int(h * 0.22)))

        for idx, (sx, sy, ssize) in enumerate(sil_positions):
            if idx < len(silhouette_paths):
                sil = Image.open(silhouette_paths[idx]).convert("RGBA")
                sil = sil.resize((ssize, ssize), Image.LANCZOS)
                thumb.paste(sil, (sx - ssize // 2, sy - ssize // 2), sil)
    elif silhouette_paths:
        # Just one silhouette — make it big on the left
        sil = Image.open(silhouette_paths[0]).convert("RGBA")
        sil_size = int(h * 0.55)
        sil = sil.resize((sil_size, sil_size), Image.LANCZOS)
        sil_x = w // 4 - sil_size // 2
        sil_y = (h - sil_size) // 2 + 30
        thumb.paste(sil, (sil_x, sil_y), sil)

    # --- Right side: Bright reveal image (hero image) ---
    if image_paths:
        img = Image.open(image_paths[0]).convert("RGBA")
        img_size = int(h * 0.55)
        img = img.resize((img_size, img_size), Image.LANCZOS)
        img_x = 3 * w // 4 - img_size // 2 + 20
        img_y = (h - img_size) // 2 + 10
        thumb.paste(img, (img_x, img_y), img)

    # --- "CAN YOU GUESS?" header — glow text, huge ---
    thumb = render_glow_text(thumb, "CAN YOU GUESS?",
                             position=(w // 2, 55),
                             font_size=78,
                             glow_color=primary_rgb,
                             text_color=(255, 255, 255),
                             glow_radius=12)

    # --- Big "?" between the two halves ---
    thumb = render_glow_text(thumb, "?",
                             position=(w // 2 + 10, h // 2),
                             font_size=140,
                             glow_color=(255, 230, 0),
                             text_color=(255, 255, 255),
                             glow_radius=15)

    # --- Category subtitle at bottom ---
    cat_display = config.CATEGORIES[category]["display"]
    thumb = render_text(thumb, f"{cat_display}s Edition!",
                        position=(w // 2, h - 35),
                        font_size=38,
                        color=(255, 255, 200))

    # --- "5 ROUNDS!" badge in top-right corner ---
    num_rounds = len(quiz_pack.rounds)
    thumb = _draw_badge(thumb, f"{num_rounds} ROUNDS!",
                        position=(w - 100, 45),
                        bg_color=(255, 50, 50))

    # --- Floating question marks for curiosity ---
    thumb = _draw_question_marks(thumb, count=4)

    # --- Leo mascot (surprised pose) in bottom-right ---
    surprised_path = config.MASCOT_POSES.get("surprised")
    if surprised_path and surprised_path.exists():
        mascot = Image.open(surprised_path).convert("RGBA")
        mascot_h = int(h * 0.35)
        mascot_w = int(mascot.width * (mascot_h / mascot.height))
        mascot = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
        thumb.paste(mascot, (w - mascot_w - 20, h - mascot_h - 50), mascot)

    # --- Vignette for depth ---
    thumb = apply_vignette(thumb, 0.25)

    # Save as high-quality PNG
    output_path.parent.mkdir(parents=True, exist_ok=True)
    thumb.convert("RGB").save(output_path, "PNG", quality=95)
    return output_path
