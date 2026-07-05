# thumbnail.py
# ============================================================
# Click-optimized YouTube thumbnails for Leo Quiz videos.
# 3 A/B test variants for maximum CTR:
#   A: Diagonal split layout (silhouette vs reveal)
#   B: Giant Mystery (huge centered silhouette + glowing "?")
#   C: Grid Challenge (2x2 silhouette grid + "HOW MANY?")
#
# Gemini Vision auto-selects the best variant per video.
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


def generate_thumbnail_variant_b(quiz_pack: QuizPack,
                                   silhouette_paths: list[Path],
                                   output_path: Path) -> Path:
    """
    # Variant B: "Giant Mystery" layout.
    # - Full category gradient background
    # - Single giant silhouette centered (70% of height)
    # - Giant "?" overlaid on silhouette (yellow glow)
    # - "GUESS THE [CATEGORY]!" at bottom (glow text)
    # - Bright yellow/red 8px border
    # - Leo mascot (surprised) in corner
    # - Vignette for depth
    """
    w, h = THUMB_SIZE
    category = quiz_pack.category
    colors = config.CATEGORY_COLORS[category]
    primary_rgb = hex_to_rgb(colors["primary"])
    cat_display = config.CATEGORIES[category]["display"]

    # Background gradient
    bg = render_gradient_background(w, h, category, t=0.0)
    thumb = bg.convert("RGBA")

    # Bright yellow/red border (8px)
    draw = ImageDraw.Draw(thumb)
    draw.rectangle([0, 0, w - 1, h - 1], outline=(255, 50, 50, 255), width=8)

    # Giant centered silhouette (70% of height)
    if silhouette_paths:
        sil = Image.open(silhouette_paths[0]).convert("RGBA")
        sil_size = int(h * 0.70)
        sil = sil.resize((sil_size, sil_size), Image.LANCZOS)
        sil_x = w // 2 - sil_size // 2
        sil_y = (h - sil_size) // 2 - 10
        thumb.paste(sil, (sil_x, sil_y), sil)

    # Giant "?" overlaid on the silhouette (yellow glow)
    thumb = render_glow_text(thumb, "?",
                              position=(w // 2, h // 2 - 20),
                              font_size=200,
                              glow_color=(255, 230, 0),
                              text_color=(255, 255, 255),
                              glow_radius=20)

    # "GUESS THE ANIMAL!" at bottom
    thumb = render_glow_text(thumb, f"GUESS THE {cat_display.upper()}!",
                              position=(w // 2, h - 55),
                              font_size=64,
                              glow_color=primary_rgb,
                              text_color=(255, 255, 255),
                              glow_radius=12)

    # Rounds badge top-right
    num_rounds = len(quiz_pack.rounds)
    thumb = _draw_badge(thumb, f"{num_rounds} ROUNDS!",
                         position=(w - 100, 45),
                         bg_color=(255, 50, 50))

    # Leo mascot (surprised) bottom-left
    surprised_path = config.MASCOT_POSES.get("surprised")
    if surprised_path and surprised_path.exists():
        mascot = Image.open(surprised_path).convert("RGBA")
        mascot_h = int(h * 0.30)
        mascot_w = int(mascot.width * (mascot_h / mascot.height))
        mascot = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
        thumb.paste(mascot, (20, h - mascot_h - 15), mascot)

    # Vignette
    thumb = apply_vignette(thumb, 0.30)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    thumb.convert("RGB").save(output_path, "PNG", quality=95)
    return output_path


def generate_thumbnail_variant_c(quiz_pack: QuizPack,
                                   silhouette_paths: list[Path],
                                   output_path: Path) -> Path:
    """
    # Variant C: "Grid Challenge" layout.
    # - Category gradient background
    # - 2×2 grid of 4 silhouettes (numbered 1-4)
    # - "HOW MANY CAN YOU GUESS?" header (glow text)
    # - Leo mascot in bottom-right corner
    # - Rounds badge in top-right
    # - Vignette for depth
    """
    w, h = THUMB_SIZE
    category = quiz_pack.category
    colors = config.CATEGORY_COLORS[category]
    primary_rgb = hex_to_rgb(colors["primary"])

    # Background gradient
    bg = render_gradient_background(w, h, category, t=0.0)
    thumb = bg.convert("RGBA")

    # Bright border
    draw = ImageDraw.Draw(thumb)
    draw.rectangle([0, 0, w - 1, h - 1], outline=(255, 230, 0, 255), width=6)

    # "HOW MANY CAN YOU GUESS?" header
    thumb = render_glow_text(thumb, "HOW MANY CAN YOU GUESS?",
                              position=(w // 2, 50),
                              font_size=62,
                              glow_color=primary_rgb,
                              text_color=(255, 255, 255),
                              glow_radius=12)

    # 2×2 grid of silhouettes with number labels
    grid_size = int(h * 0.30)
    grid_gap = 30
    grid_start_x = w // 2 - grid_size - grid_gap // 2
    grid_start_y = 110
    positions = [
        (grid_start_x, grid_start_y),
        (grid_start_x + grid_size + grid_gap, grid_start_y),
        (grid_start_x, grid_start_y + grid_size + grid_gap),
        (grid_start_x + grid_size + grid_gap, grid_start_y + grid_size + grid_gap),
    ]

    for i, (gx, gy) in enumerate(positions):
        # Draw semi-transparent cell background
        cell_bg = Image.new("RGBA", (grid_size, grid_size), (0, 0, 0, 80))
        thumb.paste(cell_bg, (gx, gy), cell_bg)

        # Paste silhouette if available
        if i < len(silhouette_paths):
            sil = Image.open(silhouette_paths[i]).convert("RGBA")
            sil = sil.resize((grid_size - 20, grid_size - 20), Image.LANCZOS)
            thumb.paste(sil, (gx + 10, gy + 10), sil)

        # Number label in top-left of each cell
        thumb = render_glow_text(thumb, str(i + 1),
                                  position=(gx + 25, gy + 25),
                                  font_size=32,
                                  glow_color=(255, 230, 0),
                                  text_color=(255, 255, 255),
                                  glow_radius=6)

    # Rounds badge top-right
    num_rounds = len(quiz_pack.rounds)
    thumb = _draw_badge(thumb, f"{num_rounds} ROUNDS!",
                         position=(w - 100, 45),
                         bg_color=(255, 50, 50))

    # Category subtitle at bottom
    cat_display = config.CATEGORIES[category]["display"]
    thumb = render_text(thumb, f"{cat_display}s Edition!",
                         position=(w // 2, h - 35),
                         font_size=38,
                         color=(255, 255, 200))

    # Leo mascot in bottom-right
    excited_path = config.MASCOT_POSES.get("excited")
    if excited_path and excited_path.exists():
        mascot = Image.open(excited_path).convert("RGBA")
        mascot_h = int(h * 0.30)
        mascot_w = int(mascot.width * (mascot_h / mascot.height))
        mascot = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
        thumb.paste(mascot, (w - mascot_w - 20, h - mascot_h - 50), mascot)

    # Floating question marks
    thumb = _draw_question_marks(thumb, count=3)

    # Vignette
    thumb = apply_vignette(thumb, 0.25)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    thumb.convert("RGB").save(output_path, "PNG", quality=95)
    return output_path


def generate_all_thumbnails(quiz_pack: QuizPack,
                              image_paths: list[Path],
                              silhouette_paths: list[Path],
                              output_dir: Path) -> dict[str, Path]:
    """# Generate 3 A/B test thumbnail variants.
    # Returns dict mapping variant key to file path: {"a": ..., "b": ..., "c": ...}."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    paths["a"] = generate_thumbnail(quiz_pack, image_paths, silhouette_paths,
                                     output_dir / "thumb_a.png")
    paths["b"] = generate_thumbnail_variant_b(quiz_pack, silhouette_paths,
                                               output_dir / "thumb_b.png")
    paths["c"] = generate_thumbnail_variant_c(quiz_pack, silhouette_paths,
                                               output_dir / "thumb_c.png")
    return paths


def select_best_thumbnail(thumb_paths: dict[str, Path]) -> str:
    """# Use Gemini Vision to evaluate 3 thumbnails and pick the most click-worthy.
    # Returns the winning variant key ('a', 'b', or 'c').
    # Evaluates: visual clarity, kid-appeal, click-worthiness, color contrast."""
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Load all 3 thumbnails as PIL images for Gemini Vision
    images = []
    for key in ["a", "b", "c"]:
        if thumb_paths.get(key) and thumb_paths[key].exists():
            images.append(Image.open(thumb_paths[key]))

    if not images:
        return "a"

    prompt = (
        "You are a YouTube thumbnail expert for kids content. "
        "I'm showing you 3 thumbnail variants (A, B, C) for a children's quiz video. "
        "Pick the ONE that would get the most clicks from kids aged 4-10 and their parents. "
        "Consider: visual clarity, mystery/curiosity factor, color contrast, kid-friendliness. "
        "Reply with ONLY the letter: A, B, or C"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt] + images,
        )
        choice = response.text.strip().upper()
        variant_map = {"A": "a", "B": "b", "C": "c"}
        return variant_map.get(choice, "a")
    except Exception as e:
        print(f"[THUMBNAIL] Gemini Vision failed, defaulting to variant A: {e}")
        return "a"
