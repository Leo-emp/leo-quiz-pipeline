# frame_composer.py
# ============================================================
# Frame composition for Leo Quiz videos.
# Renders gradient backgrounds with animated hue shifts,
# text with effects (stroke, shadow, glow, rainbow),
# themed decorations, and composites all visual elements.
# UPGRADED: glow text, rainbow text, word wrap, vignette,
# enhanced backgrounds with radial gradients.
# ============================================================
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

import config


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """# Convert hex color string (#RRGGBB) to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _shift_hue(rgb: tuple, shift_degrees: float) -> tuple[int, int, int]:
    """# Shift the hue of an RGB color by shift_degrees for animated backgrounds."""
    import colorsys
    r, g, b = [x / 255.0 for x in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + shift_degrees / 360.0) % 1.0
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return (int(r2 * 255), int(g2 * 255), int(b2 * 255))


def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """
    # Load a font, trying Baloo2-Bold first, then Fredoka, then fallback.
    # Falls back gracefully if custom fonts aren't installed yet.
    """
    font_names = ["Baloo2-Bold.ttf", "FredokaOne-Regular.ttf"]
    for name in font_names:
        font_path = config.FONTS_DIR / name
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    # Fallback to system arial or default font
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def render_gradient_background(width: int, height: int,
                                category: str, t: float = 0.0) -> Image.Image:
    """
    # Render a rich vertical gradient background with animated hue shift.
    # UPGRADED: adds a subtle radial highlight in the center for depth,
    # making the background feel more 3D and professional.
    """
    colors = config.CATEGORY_COLORS[category]
    color1 = hex_to_rgb(colors["primary"])
    color2 = hex_to_rgb(colors["secondary"])

    # Animated hue shift — creates "living" feel (±8 degrees, was 5)
    hue_shift = 8.0 * math.sin(t * 0.4)
    color1 = _shift_hue(color1, hue_shift)
    color2 = _shift_hue(color2, -hue_shift)

    # Create gradient image — interpolate colors row by row
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        ratio = y / height
        # Non-linear gradient — darker at top/bottom, brighter in middle
        # Creates a subtle "stage lighting" effect
        brightness = 1.0 + 0.15 * math.sin(ratio * math.pi)
        r = int(min(255, color1[0] * (1 - ratio) + color2[0] * ratio) * brightness)
        g = int(min(255, color1[1] * (1 - ratio) + color2[1] * ratio) * brightness)
        b = int(min(255, color1[2] * (1 - ratio) + color2[2] * ratio) * brightness)
        arr[y, :] = [min(255, r), min(255, g), min(255, b)]

    bg = Image.fromarray(arr)

    # Add subtle radial highlight in upper-center for 3D depth
    highlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(highlight)
    cx, cy = width // 2, int(height * 0.35)
    radius = int(width * 0.5)
    # Draw soft white glow at center
    for r in range(radius, 0, -3):
        progress = r / radius
        alpha = int(20 * (1 - progress * progress))  # Soft falloff
        h_draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                       fill=(255, 255, 255, alpha))
    bg = bg.convert("RGBA")
    bg = Image.alpha_composite(bg, highlight)

    return bg


def render_text(image: Image.Image, text: str, position: tuple[int, int],
                font_size: int = 48, color: tuple = (255, 255, 255),
                stroke_color: tuple = (0, 0, 0), stroke_width: int = 3,
                shadow: bool = True, anchor: str = "mm") -> Image.Image:
    """
    # Draw text with stroke outline and optional drop shadow.
    # position: (x, y) center of text
    # anchor: Pillow text anchor (mm = middle-middle for centered text)
    """
    result = image.copy()
    if result.mode != "RGBA":
        result = result.convert("RGBA")

    font = _get_font(font_size)

    # Draw shadow layer if enabled (soft drop shadow behind text)
    if shadow:
        shadow_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_pos = (position[0] + config.TEXT_SHADOW_OFFSET,
                      position[1] + config.TEXT_SHADOW_OFFSET)
        shadow_draw.text(shadow_pos, text, font=font,
                         fill=(0, 0, 0, int(255 * config.TEXT_SHADOW_OPACITY)),
                         anchor=anchor)
        # Blur the shadow for soft edges
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(3))
        result = Image.alpha_composite(result, shadow_layer)

    # Draw main text with stroke outline for readability
    draw = ImageDraw.Draw(result)
    draw.text(position, text, font=font, fill=color,
              stroke_width=stroke_width, stroke_fill=stroke_color,
              anchor=anchor)

    return result


def render_text_wrapped(image: Image.Image, text: str,
                        position: tuple[int, int],
                        font_size: int = 36,
                        max_width: int = None,
                        color: tuple = (255, 255, 255),
                        stroke_width: int = 2,
                        shadow: bool = True) -> Image.Image:
    """
    # Draw text with automatic word wrapping for long strings.
    # Splits text into multiple lines that fit within max_width.
    # Lines are vertically centered around the given position.
    """
    if max_width is None:
        max_width = int(image.width * config.TEXT_MAX_WIDTH_RATIO)

    result = image.copy()
    if result.mode != "RGBA":
        result = result.convert("RGBA")

    font = _get_font(font_size)

    # Word-wrap: split text into lines that fit max_width
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = font.getbbox(test_line)
        if bbox[2] - bbox[0] > max_width and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    # Calculate total height for vertical centering
    line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1] + 10
    total_height = len(lines) * line_height
    start_y = position[1] - total_height // 2

    # Draw each line centered at x position
    for i, line in enumerate(lines):
        line_y = start_y + i * line_height + line_height // 2

        # Shadow for each line
        if shadow:
            shadow_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            shadow_draw.text(
                (position[0] + config.TEXT_SHADOW_OFFSET,
                 line_y + config.TEXT_SHADOW_OFFSET),
                line, font=font,
                fill=(0, 0, 0, int(255 * config.TEXT_SHADOW_OPACITY)),
                anchor="mm"
            )
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(3))
            result = Image.alpha_composite(result, shadow_layer)

        # Main text
        draw = ImageDraw.Draw(result)
        draw.text((position[0], line_y), line, font=font,
                  fill=color, anchor="mm",
                  stroke_width=stroke_width, stroke_fill=(0, 0, 0))

    return result


def render_pill_background(frame: Image.Image, text: str,
                           position: tuple[int, int],
                           font_size: int,
                           padding: int = 20,
                           bg_opacity: int = 170,
                           radius: int = 18) -> Image.Image:
    """
    # Draw a semi-transparent rounded rectangle pill behind text.
    # Used as a backdrop for fun facts and labels.
    # UPGRADED: slightly more opaque (was 153) and rounder corners.
    """
    if frame.mode != "RGBA":
        frame = frame.convert("RGBA")

    font = _get_font(font_size)

    # Handle multi-line text by finding widest line
    lines = text.split("\n") if "\n" in text else [text]
    max_w = 0
    total_h = 0
    line_h = 0
    for line in lines:
        bbox = font.getbbox(line)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_w = max(max_w, w)
        line_h = max(line_h, h)
        total_h += h + 5

    pill_layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    pill_draw = ImageDraw.Draw(pill_layer)
    pill_rect = [
        position[0] - max_w // 2 - padding,
        position[1] - total_h // 2 - padding // 2,
        position[0] + max_w // 2 + padding,
        position[1] + total_h // 2 + padding // 2,
    ]
    pill_draw.rounded_rectangle(pill_rect, radius=radius,
                                fill=(0, 0, 0, bg_opacity))
    return Image.alpha_composite(frame, pill_layer)


def compose_question_frame(category: str, silhouette_path: Path,
                            question_text: str, score: int, round_num: int,
                            total_rounds: int, mascot_img: Image.Image = None,
                            size: tuple = None) -> Image.Image:
    """
    # Compose a complete question frame with all visual elements:
    # gradient background + silhouette + question text + score + mascot
    """
    if size is None:
        size = config.SHORTS_SIZE
    width, height = size

    # Layer 1: Gradient background
    bg = render_gradient_background(width, height, category)
    frame = bg.convert("RGBA")

    # Layer 2: Centered silhouette (black mystery shape)
    if silhouette_path and Path(silhouette_path).exists():
        sil = Image.open(silhouette_path).convert("RGBA")
        sil_size = int(width * 0.5)
        sil = sil.resize((sil_size, sil_size), Image.LANCZOS)
        sil_x = (width - sil_size) // 2
        sil_y = int(height * 0.25)
        frame.paste(sil, (sil_x, sil_y), sil)

    # Layer 3: Question text (wrapped for long questions)
    frame = render_text_wrapped(frame, question_text,
                                position=(width // 2, int(height * 0.62)),
                                font_size=config.QUESTION_FONT_SIZE)

    # Title bar at top
    colors = config.CATEGORY_COLORS[category]
    cat_display = config.CATEGORIES[category]["display"]
    frame = render_text(frame, f"GUESS THE {cat_display.upper()}",
                        position=(width // 2, int(height * 0.06)),
                        font_size=config.TITLE_FONT_SIZE,
                        color=hex_to_rgb(colors["primary"]))

    # Round indicator below title
    frame = render_text(frame, f"Round {round_num + 1}/{total_rounds}",
                        position=(width // 2, int(height * 0.12)),
                        font_size=config.ROUND_LABEL_FONT_SIZE,
                        color=(255, 255, 255),
                        stroke_width=2)

    # Score counter at bottom
    frame = render_text(frame, f"Score: {score}/{total_rounds}",
                        position=(width // 2, int(height * 0.88)),
                        font_size=config.SCORE_FONT_SIZE)

    # Layer 4: Mascot (thinking pose) in bottom-right corner
    if mascot_img:
        mascot_h = int(height * 0.15)
        mascot_w = int(mascot_img.width * (mascot_h / mascot_img.height))
        mascot_resized = mascot_img.resize((mascot_w, mascot_h), Image.LANCZOS)
        mascot_x = width - mascot_w - 20
        mascot_y = height - mascot_h - 20
        frame.paste(mascot_resized, (mascot_x, mascot_y), mascot_resized)

    return frame


def compose_reveal_frame(category: str, image_path: Path,
                          answer_text: str, fun_fact: str,
                          score: int, round_num: int, total_rounds: int,
                          mascot_img: Image.Image = None,
                          size: tuple = None) -> Image.Image:
    """
    # Compose a reveal frame: full color image + answer text + fun fact.
    # Shown after countdown — the "aha!" moment of each round.
    """
    if size is None:
        size = config.SHORTS_SIZE
    width, height = size

    bg = render_gradient_background(width, height, category)
    frame = bg.convert("RGBA")

    # Full color image (centered, slightly larger than silhouette)
    if image_path and Path(image_path).exists():
        img = Image.open(image_path).convert("RGBA")
        img_size = int(width * 0.55)
        img = img.resize((img_size, img_size), Image.LANCZOS)
        img_x = (width - img_size) // 2
        img_y = int(height * 0.22)
        frame.paste(img, (img_x, img_y), img)

    # Answer text in category color
    colors = config.CATEGORY_COLORS[category]
    frame = render_text(frame, f"It's a {answer_text}!",
                        position=(width // 2, int(height * 0.60)),
                        font_size=config.ANSWER_FONT_SIZE,
                        color=hex_to_rgb(colors["primary"]),
                        stroke_color=(255, 255, 255))

    # Fun fact with pill background — now word-wrapped
    fact_y = int(height * 0.74)
    frame = render_pill_background(frame, fun_fact, (width // 2, fact_y),
                                   config.FACT_FONT_SIZE)
    frame = render_text_wrapped(frame, fun_fact,
                                position=(width // 2, fact_y),
                                font_size=config.FACT_FONT_SIZE,
                                stroke_width=0, shadow=False)

    # Title bar
    cat_display = config.CATEGORIES[category]["display"]
    frame = render_text(frame, f"GUESS THE {cat_display.upper()}",
                        position=(width // 2, int(height * 0.06)),
                        font_size=config.TITLE_FONT_SIZE,
                        color=hex_to_rgb(colors["primary"]))

    # Score counter
    frame = render_text(frame, f"Score: {score}/{total_rounds}",
                        position=(width // 2, int(height * 0.88)),
                        font_size=config.SCORE_FONT_SIZE)

    # Mascot (excited pose) in bottom-right
    if mascot_img:
        mascot_h = int(height * 0.15)
        mascot_w = int(mascot_img.width * (mascot_h / mascot_img.height))
        mascot_resized = mascot_img.resize((mascot_w, mascot_h), Image.LANCZOS)
        mascot_x = width - mascot_w - 20
        mascot_y = height - mascot_h - 20
        frame.paste(mascot_resized, (mascot_x, mascot_y), mascot_resized)

    return frame


def compose_countdown_frame(category: str, silhouette_path: Path,
                             number: int, score: int, round_num: int,
                             total_rounds: int, mascot_img: Image.Image = None,
                             size: tuple = None) -> Image.Image:
    """
    # Compose a countdown frame: silhouette + large countdown number overlay.
    # Number pops in with BackEaseOut animation (handled by video_assembler).
    """
    frame = compose_question_frame(
        category, silhouette_path, "",
        score, round_num, total_rounds, mascot_img, size
    )

    if size is None:
        size = config.SHORTS_SIZE
    width, height = size

    # Large countdown number in center with category-colored stroke
    colors = config.CATEGORY_COLORS[category]
    frame = render_text(frame, str(number),
                        position=(width // 2, int(height * 0.50)),
                        font_size=config.COUNTDOWN_FONT_SIZE,
                        color=(255, 255, 255),
                        stroke_color=hex_to_rgb(colors["primary"]),
                        stroke_width=6)

    return frame
