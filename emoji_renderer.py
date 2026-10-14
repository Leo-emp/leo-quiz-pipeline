# emoji_renderer.py
# ============================================================
# High-quality emoji renderer with STICKER EFFECT.
#
# Monkey Quiz uses emoji that look like 3D stickers:
#   - Thick white outline border around each emoji
#   - Strong drop shadow behind for depth/pop
#   - Detailed, polished emoji art (not flat Windows style)
#
# RENDER PRIORITY (best quality first):
#   1. EmojiOne/JoyPixels 128px PNGs (most detailed, cute style)
#   2. Twemoji 72px PNGs (good flat style, smaller source)
#   3. Segoe UI Emoji font (last resort — flat Windows style)
#
# Sticker effect (thick white outline + strong shadow) applied
# to all emoji for that premium 3D pop-out look.
# ============================================================
import io
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config

# --- Cache directory for downloaded emoji PNGs ---
EMOJI_CACHE_DIR = config.ASSETS_DIR / "emoji"

# --- EmojiOne / JoyPixels CDN (128px, highest quality art) ---
EMOJIONE_CDNS = [
    "https://cdn.jsdelivr.net/gh/joypixels/emoji-assets@7.0.0/png/128",
]

# --- Twemoji CDN URLs (72px, good fallback) ---
TWEMOJI_CDNS = [
    "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/72x72",
    "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72",
]

# --- Windows emoji font path (last resort) ---
_EMOJI_FONT_PATH = "C:/Windows/Fonts/seguiemj.ttf"
# Cache the font object per size to avoid re-loading
_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _get_emoji_font(size: int) -> ImageFont.FreeTypeFont:
    """# Load Segoe UI Emoji font at the given size, cached."""
    if size not in _font_cache:
        try:
            _font_cache[size] = ImageFont.truetype(_EMOJI_FONT_PATH, size)
        except (OSError, IOError):
            return None
    return _font_cache[size]


def _render_emoji_from_font(emoji_char: str, size: int) -> Image.Image:
    """
    # LAST RESORT: Render emoji using Windows Segoe UI Emoji.
    # Only used when both EmojiOne and Twemoji CDNs fail.
    # Returns RGBA image cropped to content, or None if fails.
    """
    font = _get_emoji_font(size)
    if font is None:
        return None

    # Render on transparent canvas with padding for measurement
    pad = size // 4
    canvas_size = size + pad * 2
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        draw.text((canvas_size // 2, canvas_size // 2), emoji_char,
                  anchor="mm", font=font, embedded_color=True)
    except Exception:
        return None

    # Crop to actual content
    bbox = img.getbbox()
    if not bbox:
        return None

    img = img.crop(bbox)

    # Make it square (pad shorter dimension to match longer)
    w, h = img.size
    max_dim = max(w, h)
    if w != h:
        square = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
        square.paste(img, ((max_dim - w) // 2, (max_dim - h) // 2), img)
        img = square

    # Resize to requested size
    if img.size[0] != size:
        img = img.resize((size, size), Image.LANCZOS)

    return img


def _emoji_to_codepoints(emoji_char: str) -> str:
    """# Convert emoji to Twemoji/EmojiOne filename format (hex codepoints)."""
    codepoints = []
    for char in emoji_char:
        cp = ord(char)
        # Skip variation selectors (FE0E text, FE0F emoji presentation)
        if cp in (0xFE0E, 0xFE0F):
            continue
        codepoints.append(f"{cp:x}")
    return "-".join(codepoints)


def _download_emoji_png(emoji_char: str) -> Path:
    """
    # Download emoji PNG from CDN in priority order:
    # 1. EmojiOne 128px (best quality, most detailed art)
    # 2. Twemoji 72px (good flat style, wide coverage)
    # Returns path to cached PNG, or None if all downloads fail.
    """
    EMOJI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    codepoints = _emoji_to_codepoints(emoji_char)

    # --- Check for existing high-res EmojiOne cache first ---
    eo_cache = EMOJI_CACHE_DIR / f"{codepoints}_eo.png"
    if eo_cache.exists() and eo_cache.stat().st_size > 500:
        return eo_cache

    # --- Try EmojiOne/JoyPixels 128px (best art quality) ---
    # Always attempt EmojiOne before falling back to Twemoji cache
    tw_cache = EMOJI_CACHE_DIR / f"{codepoints}.png"
    for base_url in EMOJIONE_CDNS:
        url = f"{base_url}/{codepoints}.png"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "LeoQuiz-Pipeline/2.0",
            })
            response = urllib.request.urlopen(req, timeout=10)
            data = response.read()
            # Verify it's a valid image
            img = Image.open(io.BytesIO(data))
            img.verify()
            with open(eo_cache, "wb") as f:
                f.write(data)
            return eo_cache
        except Exception:
            continue

    # --- Fallback: Twemoji 72px ---
    for base_url in TWEMOJI_CDNS:
        url = f"{base_url}/{codepoints}.png"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "LeoQuiz-Pipeline/2.0",
            })
            response = urllib.request.urlopen(req, timeout=10)
            data = response.read()
            img = Image.open(io.BytesIO(data))
            img.verify()
            with open(tw_cache, "wb") as f:
                f.write(data)
            return tw_cache
        except Exception:
            continue

    # --- Try without ZWJ components (compound emoji fallback) ---
    if "-200d-" in codepoints:
        simple = codepoints.split("-200d-")[0]
        for base_url in EMOJIONE_CDNS + TWEMOJI_CDNS:
            try:
                req = urllib.request.Request(
                    f"{base_url}/{simple}.png",
                    headers={"User-Agent": "LeoQuiz-Pipeline/2.0"})
                response = urllib.request.urlopen(req, timeout=10)
                data = response.read()
                with open(tw_cache, "wb") as f:
                    f.write(data)
                return tw_cache
            except Exception:
                continue

    return None


def _add_sticker_effect(img: Image.Image, outline_width: int = 6) -> Image.Image:
    """
    # Monkey Quiz-style premium sticker effect:
    # - THICK white outline border (smooth, clean edges)
    # - STRONG drop shadow for 3D pop-out depth
    #
    # Steps:
    # 1. Dilate alpha outward via MaxFilter → white outline mask
    # 2. Create offset + heavily blurred shadow layer
    # 3. Composite: shadow → white outline → emoji on top
    """
    w, h = img.size
    # Extra padding for the thicker outline + larger shadow
    pad = outline_width + 20

    # Extract alpha and dilate for the outline shape
    # MaxFilter(3) expands alpha by 1px per iteration
    alpha = img.split()[3]
    dilated_img = alpha
    for _ in range(outline_width):
        dilated_img = dilated_img.filter(ImageFilter.MaxFilter(3))
    dilated = np.array(dilated_img)

    # --- Smooth the outline edges for a cleaner look ---
    # Slight blur on the dilated mask removes jagged stair-stepping
    smooth_alpha = Image.fromarray(dilated).filter(
        ImageFilter.GaussianBlur(radius=1.5))
    dilated = np.array(smooth_alpha)

    # White outline layer
    outline_alpha = Image.fromarray(dilated)
    outline_layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    outline_white = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    outline_layer = Image.composite(outline_white, outline_layer, outline_alpha)

    # Shadow layer (bigger offset + stronger opacity + more blur)
    canvas_w, canvas_h = w + pad * 2, h + pad * 2
    shadow_offset = 10  # bigger offset for more depth
    shadow_opacity = 0.55  # stronger shadow (was 0.4)
    shadow_alpha = Image.fromarray(
        (dilated * shadow_opacity).astype(np.uint8))
    shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    shadow_rgb = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    shadow_img = Image.composite(
        shadow_rgb, Image.new("RGBA", (w, h), (0, 0, 0, 0)), shadow_alpha)
    shadow_layer.paste(shadow_img,
                       (pad + shadow_offset, pad + shadow_offset))
    # More blur for softer, more natural shadow spread
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=10))

    # Composite: shadow → outline → emoji
    result = shadow_layer.copy()
    result.paste(outline_layer, (pad, pad), outline_layer)
    result.paste(img, (pad, pad), img)
    return result


# --- In-memory cache for final emoji images ---
_emoji_image_cache: dict[tuple, Image.Image] = {}


def get_emoji_image(emoji_char: str, size: int = 200,
                    sticker: bool = True) -> Image.Image:
    """
    # Get a high-quality sticker-style emoji image.
    #
    # Priority: EmojiOne 128px → Twemoji 72px → Segoe UI Emoji font
    # All sources get upscaled to render_size (2x target) then
    # sticker effect applied, then downscaled for crisp result.
    #
    # Returns RGBA PIL Image, or None if unavailable.
    """
    cache_key = (emoji_char, size, sticker)
    if cache_key in _emoji_image_cache:
        return _emoji_image_cache[cache_key].copy()

    # --- Render at 2x then downscale for crisp, anti-aliased result ---
    render_size = size * 2
    img = None

    # --- PRIMARY: Download from CDN (EmojiOne 128px → Twemoji 72px) ---
    png_path = _download_emoji_png(emoji_char)
    if png_path is not None:
        img = Image.open(png_path).convert("RGBA")
        img = img.resize((render_size, render_size), Image.LANCZOS)

    # --- LAST RESORT: Segoe UI Emoji font (flat Windows style) ---
    if img is None:
        img = _render_emoji_from_font(emoji_char, render_size)

    if img is None:
        return None

    # --- Apply sticker effect at 2x (thicker outline + stronger shadow) ---
    if sticker:
        # Clean outline — visible but not chunky (between old thin and too thick)
        outline_w = max(8, render_size // 16)
        img = _add_sticker_effect(img, outline_width=outline_w)

    # --- Downscale to target size for crisp result ---
    final_w = int(img.width * size / render_size)
    final_h = int(img.height * size / render_size)
    img = img.resize((final_w, final_h), Image.LANCZOS)

    _emoji_image_cache[cache_key] = img.copy()
    return img


def preload_emoji_set(emoji_list: list[str], size: int = 200) -> None:
    """# Pre-load all emoji needed for a video into memory cache."""
    unique = set()
    for emoji_str in emoji_list:
        for char in emoji_str:
            unique.add(char)
    for emoji_str in emoji_list:
        unique.add(emoji_str)

    print(f"[EMOJI] Pre-loading {len(unique)} unique emoji images...")
    for emoji_char in unique:
        get_emoji_image(emoji_char, size)
    print(f"[EMOJI] All emoji images loaded and cached")
