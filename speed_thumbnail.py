# speed_thumbnail.py
# ============================================================
# 5 viral thumbnail variants for speed quiz format.
# Each variant is a DIFFERENT viral formula observed across
# top kids quiz YouTube channels (Quiz Blitz, 7-Second Riddles, etc.)
#
# Variants:
#   A: Grid        — Quiz Blitz formula (10 photos, 1 line text)
#   B: Challenge   — Big Leo + "CAN YOU BEAT ME?" + 4 preview photos
#   C: Giant Number — Massive "120" center, photos arranged around it
#   D: Mystery Wall — 3x4 grid, some covered with "?" cards
#   E: Difficulty   — 4 colored strips (EASY→IMPOSSIBLE) with photos
#
# Pipeline generates all 5, Gemini Vision picks the winner.
# ============================================================
import random
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config
from frame_composer import _get_font
from quiz_generator import QuizPack


def _remove_white_bg_clean(img):
    """# Remove white background with radial mask for clean compositing."""
    data = np.array(img.convert("RGBA"))
    h_img, w_img = data.shape[:2]

    # Kill pure white pixels
    white = ((data[:, :, 0] > 215) &
             (data[:, :, 1] > 215) &
             (data[:, :, 2] > 215))
    data[white, 3] = 0

    # Kill low-saturation bright pixels (off-white confetti)
    r = data[:, :, 0].astype(float)
    g = data[:, :, 1].astype(float)
    b = data[:, :, 2].astype(float)
    max_rgb = np.maximum(np.maximum(r, g), b)
    min_rgb = np.minimum(np.minimum(r, g), b)
    low_sat = (max_rgb - min_rgb < 30) & (max_rgb > 195)
    data[low_sat, 3] = 0

    # Radial mask to fade scattered edge artifacts
    y_coords, x_coords = np.ogrid[:h_img, :w_img]
    cx, cy = w_img // 2, int(h_img * 0.48)
    dist = np.sqrt(((x_coords - cx) / (w_img * 0.38)) ** 2 +
                   ((y_coords - cy) / (h_img * 0.42)) ** 2)
    radial = np.clip(1.0 - (dist - 0.85) / 0.25, 0.0, 1.0)
    data[:, :, 3] = (data[:, :, 3].astype(float) * radial).astype(np.uint8)

    # Feather edges + threshold cleanup
    result = Image.fromarray(data)
    alpha = result.split()[3]
    alpha = alpha.filter(ImageFilter.GaussianBlur(radius=0.8))
    alpha_arr = np.array(alpha)
    alpha_arr[alpha_arr < 60] = 0
    result.putalpha(Image.fromarray(alpha_arr))
    return result


# --- Category-specific solid backgrounds ---
_CATEGORY_BG = {
    "animals":   (30, 136, 229),   # Bright blue
    "dinosaurs": (230, 126, 34),   # Warm orange
    "space":     (26, 35, 126),    # Deep navy
    "vehicles":  (211, 47, 47),    # Bold red
    "fruits":    (56, 142, 60),    # Fresh green
    "flags":     (106, 27, 154),   # Rich purple
}
_DEFAULT_BG = (30, 136, 229)

# --- Category-specific gradient pairs for variant B/C ---
_CATEGORY_GRADIENT = {
    "animals":   ((30, 136, 229), (21, 101, 192)),
    "dinosaurs": ((230, 126, 34), (180, 80, 20)),
    "space":     ((26, 35, 126), (10, 10, 60)),
    "vehicles":  ((211, 47, 47), (150, 20, 20)),
    "fruits":    ((56, 142, 60), (30, 100, 40)),
    "flags":     ((106, 27, 154), (60, 15, 100)),
}

# --- Category emoji for flair ---
_CATEGORY_EMOJI = {
    "animals": "🦁", "dinosaurs": "🦕", "space": "🚀",
    "vehicles": "🚗", "fruits": "🍎", "flags": "🏳️",
}


# ============================================================
# SHARED HELPERS
# ============================================================

def _draw_placeholder(card, cw, ch):
    """# Draw a "?" placeholder when no photo is available."""
    d = ImageDraw.Draw(card)
    d.rectangle([6, 6, cw - 6, ch - 6], fill=(200, 200, 210))
    font = _get_font(60, bold=True)
    d.text((cw // 2, ch // 2), "?", fill=(100, 100, 120),
           anchor="mm", font=font)


def _round_corners(img, radius):
    """# Round the corners of an RGBA image using a mask."""
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, img.width, img.height],
                        radius=radius, fill=255)
    result = img.copy()
    result.putalpha(mask)
    return result


def _load_mascot(mascot_dir, target_h):
    """# Load Leo mascot, remove background, resize to target height."""
    if mascot_dir is None:
        mascot_dir = config.MASCOT_DIR
    mascot_path = mascot_dir / "excited.png"
    if not mascot_path.exists():
        return None
    try:
        mascot = Image.open(mascot_path).convert("RGBA")
        mascot = _remove_white_bg_clean(mascot)
        mascot_w = int(mascot.width * (target_h / mascot.height))
        mascot = mascot.resize((mascot_w, target_h), Image.LANCZOS)
        return mascot
    except Exception:
        return None


def _select_photos(photo_paths, count):
    """# Pick evenly spaced photos from available set, with fallback."""
    if len(photo_paths) >= count:
        step = len(photo_paths) // count
        return [photo_paths[i * step] for i in range(count)]
    elif len(photo_paths) > 0:
        selected = photo_paths[:count]
        while len(selected) < count:
            selected.append(random.choice(photo_paths))
        return selected
    return []


def _load_photo_card(photo_path, card_w, card_h, pad=6, radius=14):
    """# Load a photo into a white rounded card, center-cropped to fill."""
    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
    if photo_path and photo_path.exists():
        try:
            photo = Image.open(photo_path).convert("RGBA")
            inner_w = card_w - pad * 2
            inner_h = card_h - pad * 2
            pw, ph = photo.size
            scale = max(inner_w / pw, inner_h / ph)
            photo = photo.resize((int(pw * scale), int(ph * scale)), Image.LANCZOS)
            crop_x = (photo.width - inner_w) // 2
            crop_y = (photo.height - inner_h) // 2
            photo = photo.crop((crop_x, crop_y, crop_x + inner_w, crop_y + inner_h))
            card.paste(photo, (pad, pad))
        except Exception:
            _draw_placeholder(card, card_w, card_h)
    else:
        _draw_placeholder(card, card_w, card_h)
    return _round_corners(card, radius)


def _draw_3d_text(img, text, x, y, font, fill, stroke_fill=(0, 0, 0),
                  stroke_width=6, shadow_offset=4, anchor="lm"):
    """# Draw text with shadow + stroke for 3D pop effect."""
    w, h = img.size
    # Shadow layer
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text((x + shadow_offset, y + shadow_offset), text,
            fill=(0, 0, 0, 150), anchor=anchor, font=font,
            stroke_width=stroke_width + 2, stroke_fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=3))
    img = Image.alpha_composite(img, shadow)
    # Main text with stroke
    draw = ImageDraw.Draw(img)
    draw.text((x, y), text, fill=fill, anchor=anchor, font=font,
              stroke_width=stroke_width, stroke_fill=stroke_fill)
    return img


def _draw_3d_text_multicolor(img, parts, x, y, font, stroke_width=6,
                              shadow_offset=4, anchor="lm"):
    """# Draw multi-colored text segments with 3D effect.
    # parts = [(text, color), ...]"""
    w, h = img.size
    # Build full text for shadow
    full_text = "".join(t for t, _ in parts)
    # Shadow layer
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text((x + shadow_offset, y + shadow_offset), full_text,
            fill=(0, 0, 0, 150), anchor=anchor, font=font,
            stroke_width=stroke_width + 2, stroke_fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=3))
    img = Image.alpha_composite(img, shadow)
    # Each segment in its color
    draw = ImageDraw.Draw(img)
    cx = x
    for text, color in parts:
        draw.text((cx, y), text, fill=color, anchor=anchor, font=font,
                  stroke_width=stroke_width, stroke_fill=(0, 0, 0))
        cx += int(font.getlength(text))
    return img


def _make_gradient_bg(w, h, color_top, color_bottom):
    """# Create a vertical gradient background."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        t = y / h
        r = int(color_top[0] * (1 - t) + color_bottom[0] * t)
        g = int(color_top[1] * (1 - t) + color_bottom[1] * t)
        b = int(color_top[2] * (1 - t) + color_bottom[2] * t)
        arr[y, :] = [r, g, b, 255]
    return Image.fromarray(arr)


# ============================================================
# VARIANT A: GRID (Quiz Blitz formula)
# Massive text on top, 2x5 photo grid below, Leo brand stamp
# ============================================================

def _generate_variant_a(quiz_pack, photo_paths, output_path, mascot_dir=None):
    """# Quiz Blitz proven formula: text + 10-photo grid."""
    w, h = 1280, 720
    cat_display = config.CATEGORIES[quiz_pack.category]["display"]
    num_rounds = len(quiz_pack.rounds)
    category = quiz_pack.category

    # Solid bright background
    bg_color = _CATEGORY_BG.get(category, _DEFAULT_BG)
    img = Image.new("RGBA", (w, h), bg_color + (255,))

    # Massive title: "GUESS 120 ANIMALS"
    text_y = int(h * 0.12)
    full_text = f"GUESS {num_rounds} {cat_display.upper()}S"
    font_size = 95
    test_font = _get_font(font_size, bold=True)
    total_tw = test_font.getlength(full_text)
    if total_tw > w * 0.95:
        font_size = int(95 * (w * 0.95) / total_tw)
    title_font = _get_font(font_size, bold=True)
    total_tw = title_font.getlength(full_text)
    sx = (w - int(total_tw)) // 2

    # Draw title with 3D effect + number in red
    parts = [
        ("GUESS ", (255, 255, 255)),
        (str(num_rounds), (255, 50, 50)),
        (f" {cat_display.upper()}S", (255, 255, 255)),
    ]
    img = _draw_3d_text_multicolor(img, parts, sx, text_y, title_font)

    # 2x5 photo grid
    grid_top = int(h * 0.28)
    grid_left, grid_right = 12, w - 12
    cols, rows, gap = 5, 2, 8
    cell_w = (grid_right - grid_left - gap * (cols - 1)) // cols
    cell_h = (h - 8 - grid_top - gap * (rows - 1)) // rows

    selected = _select_photos(photo_paths, rows * cols)
    for idx in range(rows * cols):
        row, col = idx // cols, idx % cols
        cx = grid_left + col * (cell_w + gap)
        cy = grid_top + row * (cell_h + gap)
        photo_path = selected[idx] if idx < len(selected) else None
        card = _load_photo_card(photo_path, cell_w, cell_h)
        img.paste(card, (cx, cy), card)

    # Leo brand stamp bottom-right
    mascot = _load_mascot(mascot_dir, int(h * 0.35))
    if mascot:
        mx = w - mascot.width + 10
        my = h - mascot.height + 15
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(mascot, (mx, my))
        img = Image.alpha_composite(img, layer)

    img.convert("RGB").save(str(output_path), "PNG", quality=95)
    return output_path


# ============================================================
# VARIANT B: LEO CHALLENGE
# Big Leo on left, "CAN YOU BEAT ME?" stacked text right,
# 4 preview photos in a row at the bottom
# ============================================================

def _generate_variant_b(quiz_pack, photo_paths, output_path, mascot_dir=None):
    """# Leo Challenge: mascot hero + challenge text + photo previews."""
    w, h = 1280, 720
    cat_display = config.CATEGORIES[quiz_pack.category]["display"]
    num_rounds = len(quiz_pack.rounds)
    category = quiz_pack.category

    # Gradient background
    grad_top, grad_bot = _CATEGORY_GRADIENT.get(category,
                            ((30, 136, 229), (21, 101, 192)))
    img = _make_gradient_bg(w, h, grad_top, grad_bot)

    # Subtle radial glow behind Leo's area (left half)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_center = (w // 4, h // 2)
    for r in range(300, 0, -3):
        alpha = int(40 * (r / 300))
        glow_draw.ellipse(
            [glow_center[0] - r, glow_center[1] - r,
             glow_center[0] + r, glow_center[1] + r],
            fill=(255, 255, 255, alpha)
        )
    img = Image.alpha_composite(img, glow)

    # Big Leo on the left (65% of frame height)
    mascot = _load_mascot(mascot_dir, int(h * 0.65))
    if mascot:
        mx = 30
        my = h - mascot.height - 20
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(mascot, (mx, my))
        img = Image.alpha_composite(img, layer)
        text_left = mx + mascot.width + 20
    else:
        text_left = 60

    # Stacked text on the right side
    text_cx = text_left + (w - text_left) // 2

    # Line 1: "CAN YOU"
    font_big = _get_font(72, bold=True)
    img = _draw_3d_text(img, "CAN YOU", text_cx, int(h * 0.18),
                        font_big, (255, 255, 255), anchor="mm")

    # Line 2: "GUESS" in yellow
    font_huge = _get_font(90, bold=True)
    img = _draw_3d_text(img, "GUESS", text_cx, int(h * 0.35),
                        font_huge, (255, 230, 50), anchor="mm")

    # Line 3: "120 ANIMALS?" with number in red
    num_text = f"{num_rounds} {cat_display.upper()}S?"
    font_num = _get_font(68, bold=True)
    # Measure to center multicolor
    tw = font_num.getlength(num_text)
    nx = text_cx - int(tw) // 2
    parts = [
        (f"{num_rounds} ", (255, 70, 70)),
        (f"{cat_display.upper()}S?", (255, 255, 255)),
    ]
    img = _draw_3d_text_multicolor(img, parts, nx, int(h * 0.52),
                                    font_num, anchor="lm")

    # 4 preview photos in a row at the bottom
    photo_row_y = int(h * 0.70)
    photo_count = 4
    photo_w = 140
    photo_h = 120
    total_photos_w = photo_count * photo_w + (photo_count - 1) * 10
    photos_start_x = text_cx - total_photos_w // 2
    selected = _select_photos(photo_paths, photo_count)
    for i in range(photo_count):
        px = photos_start_x + i * (photo_w + 10)
        p = selected[i] if i < len(selected) else None
        card = _load_photo_card(p, photo_w, photo_h, pad=4, radius=10)
        img.paste(card, (px, photo_row_y), card)

    img.convert("RGB").save(str(output_path), "PNG", quality=95)
    return output_path


# ============================================================
# VARIANT C: GIANT NUMBER
# Massive "120" in center with glow, photos arranged in 2
# curved rows above and below, category text at top
# ============================================================

def _generate_variant_c(quiz_pack, photo_paths, output_path, mascot_dir=None):
    """# Giant Number: massive count as visual anchor, photos orbit it."""
    w, h = 1280, 720
    cat_display = config.CATEGORIES[quiz_pack.category]["display"]
    num_rounds = len(quiz_pack.rounds)
    category = quiz_pack.category

    # Dark gradient for dramatic contrast with the big number
    bg_color = _CATEGORY_BG.get(category, _DEFAULT_BG)
    dark_bg = tuple(max(0, c - 60) for c in bg_color)
    img = _make_gradient_bg(w, h, bg_color, dark_bg)

    # Radial glow behind the number
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    center = (w // 2, int(h * 0.52))
    for r in range(280, 0, -3):
        alpha = int(60 * (r / 280))
        bright = tuple(min(255, c + 80) for c in bg_color)
        glow_draw.ellipse(
            [center[0] - r, center[1] - r,
             center[0] + r, center[1] + r],
            fill=bright + (alpha,)
        )
    img = Image.alpha_composite(img, glow)

    # Category text at very top: "GUESS THE ANIMALS"
    font_top = _get_font(60, bold=True)
    top_text = f"GUESS THE {cat_display.upper()}S"
    img = _draw_3d_text(img, top_text, w // 2, int(h * 0.10),
                        font_top, (255, 255, 255), anchor="mm")

    # MASSIVE number in center
    font_number = _get_font(220, bold=True)
    img = _draw_3d_text(img, str(num_rounds), w // 2, int(h * 0.50),
                        font_number, (255, 230, 50),
                        stroke_width=10, shadow_offset=6, anchor="mm")

    # "IN 3 SECONDS!" below the number
    font_sub = _get_font(44, bold=True)
    img = _draw_3d_text(img, "IN 3 SECONDS!", w // 2, int(h * 0.78),
                        font_sub, (255, 255, 255), anchor="mm")

    # 5 photos across the top row (above the number)
    top_row_y = int(h * 0.20)
    photo_w, photo_h = 130, 100
    selected = _select_photos(photo_paths, 10)
    total_pw = 5 * photo_w + 4 * 10
    start_x = (w - total_pw) // 2
    for i in range(5):
        px = start_x + i * (photo_w + 10)
        p = selected[i] if i < len(selected) else None
        card = _load_photo_card(p, photo_w, photo_h, pad=3, radius=8)
        img.paste(card, (px, top_row_y), card)

    # 5 photos across the bottom row (below "IN 3 SECONDS!")
    bot_row_y = int(h * 0.86)
    for i in range(5):
        px = start_x + i * (photo_w + 10)
        p = selected[5 + i] if 5 + i < len(selected) else None
        card = _load_photo_card(p, photo_w, photo_h, pad=3, radius=8)
        img.paste(card, (px, bot_row_y), card)

    # Leo stamp bottom-right
    mascot = _load_mascot(mascot_dir, int(h * 0.30))
    if mascot:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(mascot, (w - mascot.width + 5, h - mascot.height + 10))
        img = Image.alpha_composite(img, layer)

    img.convert("RGB").save(str(output_path), "PNG", quality=95)
    return output_path


# ============================================================
# VARIANT D: MYSTERY WALL
# 3x4 grid of photos but some are covered with "?" cards
# (reveals concept — makes viewer want to click to find out)
# "HOW MANY CAN YOU GUESS?" text across top
# ============================================================

def _generate_variant_d(quiz_pack, photo_paths, output_path, mascot_dir=None):
    """# Mystery Wall: some photos revealed, some hidden with '?' — creates curiosity."""
    w, h = 1280, 720
    cat_display = config.CATEGORIES[quiz_pack.category]["display"]
    num_rounds = len(quiz_pack.rounds)
    category = quiz_pack.category

    # Solid background
    bg_color = _CATEGORY_BG.get(category, _DEFAULT_BG)
    img = Image.new("RGBA", (w, h), bg_color + (255,))

    # Title: "HOW MANY CAN YOU GUESS?"
    font_title = _get_font(68, bold=True)
    title_text = "HOW MANY CAN YOU GUESS?"
    tw = font_title.getlength(title_text)
    if tw > w * 0.95:
        font_title = _get_font(int(68 * (w * 0.95) / tw), bold=True)
    img = _draw_3d_text(img, title_text, w // 2, int(h * 0.10),
                        font_title, (255, 255, 255), anchor="mm")

    # 3x4 grid (12 cells)
    grid_top = int(h * 0.22)
    grid_left, grid_right = 20, w - 20
    cols, rows, gap = 4, 3, 8
    cell_w = (grid_right - grid_left - gap * (cols - 1)) // cols
    cell_h = (h - 12 - grid_top - gap * (rows - 1)) // rows

    selected = _select_photos(photo_paths, 12)

    # Randomly pick which cells are "mystery" (covered with ?)
    # Show 7 photos, hide 5 with question marks
    mystery_indices = set(random.sample(range(12), 5))

    for idx in range(12):
        row, col = idx // cols, idx % cols
        cx = grid_left + col * (cell_w + gap)
        cy = grid_top + row * (cell_h + gap)

        if idx in mystery_indices:
            # Mystery card: bright colored card with giant "?"
            accent = tuple(min(255, c + 40) for c in bg_color)
            card = Image.new("RGBA", (cell_w, cell_h), accent + (255,))
            d = ImageDraw.Draw(card)
            font_q = _get_font(90, bold=True)
            d.text((cell_w // 2, cell_h // 2), "?",
                   fill=(255, 255, 255), anchor="mm", font=font_q,
                   stroke_width=4, stroke_fill=(0, 0, 0))
            card = _round_corners(card, 14)
        else:
            # Revealed photo
            p = selected[idx] if idx < len(selected) else None
            card = _load_photo_card(p, cell_w, cell_h)

        img.paste(card, (cx, cy), card)

    # Leo peeking from bottom-left
    mascot = _load_mascot(mascot_dir, int(h * 0.30))
    if mascot:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(mascot, (-10, h - mascot.height + 10))
        img = Image.alpha_composite(img, layer)

    # Round count badge top-right
    badge_font = _get_font(36, bold=True)
    draw = ImageDraw.Draw(img)
    badge_text = f"{num_rounds} {cat_display.upper()}S"
    btw = badge_font.getlength(badge_text) + 30
    bth = 50
    bx = w - int(btw) - 15
    by = 10
    draw.rounded_rectangle([bx, by, bx + int(btw), by + bth],
                            radius=25, fill=(255, 50, 50, 230))
    draw.text((bx + int(btw) // 2, by + bth // 2), badge_text,
              fill=(255, 255, 255), anchor="mm", font=badge_font,
              stroke_width=2, stroke_fill=(0, 0, 0))

    img.convert("RGB").save(str(output_path), "PNG", quality=95)
    return output_path


# ============================================================
# VARIANT E: DIFFICULTY STAIRCASE
# 4 horizontal colored strips (EASY→IMPOSSIBLE), each with
# 3 photos, showing the difficulty progression.
# Text across the very top: "120 ANIMALS — ALL LEVELS!"
# ============================================================

_DIFF_COLORS = {
    "EASY":       (46, 204, 113),    # green
    "MEDIUM":     (241, 196, 15),    # yellow
    "HARD":       (231, 76, 60),     # red
    "IMPOSSIBLE": (142, 68, 173),    # purple
}

def _generate_variant_e(quiz_pack, photo_paths, output_path, mascot_dir=None):
    """# Difficulty Staircase: 4 colored tiers with photos, shows progression."""
    w, h = 1280, 720
    cat_display = config.CATEGORIES[quiz_pack.category]["display"]
    num_rounds = len(quiz_pack.rounds)
    category = quiz_pack.category

    # Dark background so colored strips pop
    img = Image.new("RGBA", (w, h), (25, 25, 35, 255))

    # Title: "120 ANIMALS — ALL LEVELS!"
    font_title = _get_font(62, bold=True)
    title_text = f"{num_rounds} {cat_display.upper()}S"
    subtitle_text = "ALL LEVELS!"

    # Title with number in yellow
    tw = font_title.getlength(title_text)
    sx = w // 2 - int(tw) // 2
    parts = [
        (f"{num_rounds} ", (255, 230, 50)),
        (f"{cat_display.upper()}S", (255, 255, 255)),
    ]
    img = _draw_3d_text_multicolor(img, parts, sx, int(h * 0.08),
                                    font_title, anchor="lm")

    # Subtitle
    font_sub = _get_font(34, bold=True)
    img = _draw_3d_text(img, subtitle_text, w // 2, int(h * 0.17),
                        font_sub, (200, 200, 200), stroke_width=3, anchor="mm")

    # 4 difficulty strips
    strip_top = int(h * 0.24)
    strip_height = int((h - strip_top - 10) / 4) - 6
    strip_left = 15
    strip_right = w - 15
    strip_gap = 6

    difficulties = ["EASY", "MEDIUM", "HARD", "IMPOSSIBLE"]
    selected = _select_photos(photo_paths, 12)
    photo_idx = 0

    for i, diff in enumerate(difficulties):
        sy = strip_top + i * (strip_height + strip_gap)
        diff_color = _DIFF_COLORS[diff]

        # Colored strip background
        strip = Image.new("RGBA", (strip_right - strip_left, strip_height),
                          diff_color + (255,))
        strip = _round_corners(strip, 12)
        img.paste(strip, (strip_left, sy), strip)

        # Difficulty label on left side
        draw = ImageDraw.Draw(img)
        font_diff = _get_font(28, bold=True)
        draw.text((strip_left + 20, sy + strip_height // 2), diff,
                  fill=(255, 255, 255), anchor="lm", font=font_diff,
                  stroke_width=3, stroke_fill=(0, 0, 0))

        # 3 photos in this strip (right-aligned)
        label_w = int(font_diff.getlength(diff)) + 50
        photos_area_left = strip_left + max(label_w, 160)
        photos_area_right = strip_right - 10
        ph_w = min(160, (photos_area_right - photos_area_left - 16) // 3)
        ph_h = strip_height - 16
        photos_total_w = 3 * ph_w + 2 * 8
        px_start = photos_area_left + (photos_area_right - photos_area_left - photos_total_w) // 2

        for j in range(3):
            px = px_start + j * (ph_w + 8)
            py = sy + 8
            p = selected[photo_idx] if photo_idx < len(selected) else None
            card = _load_photo_card(p, ph_w, ph_h, pad=3, radius=8)
            img.paste(card, (px, py), card)
            photo_idx += 1

    # Leo stamp bottom-right (small)
    mascot = _load_mascot(mascot_dir, int(h * 0.28))
    if mascot:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(mascot, (w - mascot.width + 5, h - mascot.height + 8))
        img = Image.alpha_composite(img, layer)

    img.convert("RGB").save(str(output_path), "PNG", quality=95)
    return output_path


# ============================================================
# PUBLIC API — generate all 5 + Gemini auto-select
# ============================================================

# Maps variant keys to generator functions
_VARIANT_GENERATORS = {
    "a": _generate_variant_a,
    "b": _generate_variant_b,
    "c": _generate_variant_c,
    "d": _generate_variant_d,
    "e": _generate_variant_e,
}


def generate_speed_thumbnail(quiz_pack: QuizPack, photo_paths: list[Path],
                              output_dir: Path, mascot_dir: Path = None) -> Path:
    """# Generate all 5 speed thumbnail variants + Gemini auto-select the best.
    # Returns path to the winning thumbnail (copied to thumbnail_speed.png)."""
    import shutil

    all_paths = generate_all_speed_thumbnails(quiz_pack, photo_paths,
                                               output_dir, mascot_dir)
    best_key = select_best_speed_thumbnail(all_paths)
    print(f"[THUMB] Gemini selected variant: {best_key.upper()}")

    # Copy winner to canonical thumbnail path
    final_path = output_dir / "thumbnail_speed.png"
    shutil.copy2(all_paths[best_key], final_path)
    print(f"[THUMB] Speed thumbnail saved: {final_path}")
    return final_path


def generate_all_speed_thumbnails(quiz_pack: QuizPack, photo_paths: list[Path],
                                   output_dir: Path,
                                   mascot_dir: Path = None) -> dict[str, Path]:
    """# Generate all 5 thumbnail variants. Returns {"a": path, "b": path, ...}."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, gen_func in _VARIANT_GENERATORS.items():
        out = output_dir / f"thumb_speed_{key}.png"
        try:
            gen_func(quiz_pack, photo_paths, out, mascot_dir)
            paths[key] = out
            print(f"[THUMB] Generated variant {key.upper()}: {out.name}")
        except Exception as e:
            print(f"[THUMB] Variant {key.upper()} failed: {e}")
    return paths


def select_best_speed_thumbnail(thumb_paths: dict[str, Path]) -> str:
    """# Use Gemini Vision to pick the most click-worthy thumbnail.
    # Evaluates all variants and returns the winning key."""
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Load all variant images for Gemini
    images = []
    keys = []
    labels = {
        "a": "A (Grid)", "b": "B (Challenge)", "c": "C (Giant Number)",
        "d": "D (Mystery Wall)", "e": "E (Difficulty Staircase)",
    }
    for key in sorted(thumb_paths.keys()):
        path = thumb_paths[key]
        if path and path.exists():
            images.append(Image.open(path))
            keys.append(key)

    if not images:
        return "a"

    # Build the label mapping for the prompt
    label_list = ", ".join(f"{labels.get(k, k.upper())}" for k in keys)

    prompt = (
        f"You are a YouTube thumbnail expert for kids quiz content (ages 4-10). "
        f"I'm showing you {len(images)} thumbnail variants: {label_list}. "
        f"Pick the ONE that would get the most clicks from kids and parents. "
        f"Consider: visual clarity at small size, curiosity/mystery factor, "
        f"color contrast, text readability, kid-friendliness, and how it looks "
        f"in a YouTube search results grid. "
        f"Reply with ONLY the letter: {', '.join(k.upper() for k in keys)}"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt] + images,
        )
        answer = response.text.strip().upper()
        # Extract just the letter
        for k in keys:
            if k.upper() in answer:
                return k
        return keys[0]
    except Exception as e:
        print(f"[THUMB] Gemini selection failed: {e}, defaulting to A")
        return "a"
