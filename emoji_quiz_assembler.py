# emoji_quiz_assembler.py
# ============================================================
# Frame-by-frame 16:9 landscape renderer for Emoji Quiz format.
# "Guess the X by Emoji" — Monkey Quiz quality (18M+ views).
#
# QUALITY MATCHING — Monkey Quiz visual design:
# - Rich purple gradient background (deep purple → magenta)
# - HUGE Twemoji PNG images (not font glyphs) — 3D style, 200+ px
# - "GUESS THE" white + category in YELLOW with RED banner behind it
# - Large white "+" signs between emoji images
# - Drop shadows on emoji for depth
# - Smooth countdown timer bar (green → yellow → red)
# - Clean answer reveal with glow + confetti
# - Score counter, round badge, difficulty tiers
# - Sparkle particles for premium feel
# - Vignette for cinematic depth
#
# Per-round phases (8 seconds total):
#   0.0s - 0.5s : Emoji images bounce in (elastic ease)
#   0.5s - 5.5s : Timer countdown (5 seconds)
#   5.5s - 6.5s : Answer reveal + confetti + shake
#   6.5s - 7.6s : Fun fact overlay
#   7.6s - 8.0s : Transition to next round
# ============================================================
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import config
from animations import compute_scale, compute_opacity, ParticleSystem
from effects import (
    ConfettiBurst, ScreenShake, apply_vignette, render_glow_text,
)
from frame_composer import _get_font, hex_to_rgb
from emoji_quiz_generator import EmojiQuizRound, EmojiQuizPack
from emoji_renderer import get_emoji_image, preload_emoji_set


# ============================================================
# SCENE BACKGROUNDS — custom images for clue + reveal scenes
# Each background defines where emoji/photos should be placed.
# content_zone: (cx, cy) as ratio of 1920x1080 — center point
#   for placing emoji stickers (clue) or answer photos (reveal).
# ============================================================
_BG_DIR = config.ASSETS_DIR / "backgrounds"

# Clue scene backgrounds (whiteboard/rock with Leo Quizz branding)
# cx = horizontal center of blank area, emoji_y = vertical center
# emoji_w = max width for emoji row (all as ratios of 1920x1080)
CLUE_BACKGROUNDS = [
    # Whiteboard with paw logo, ? stones
    {"file": "clue/clue_01_jungle_board.png",
     "cx": 0.50, "emoji_w": 0.50, "emoji_y": 0.35},
    # Forest adventure board with Leo + signs
    {"file": "clue/clue_02_forest_adventure.png",
     "cx": 0.50, "emoji_w": 0.42, "emoji_y": 0.40},
    # Big whiteboard with Leo Quizz Kids logo
    {"file": "clue/clue_03_forest_board.png",
     "cx": 0.52, "emoji_w": 0.40, "emoji_y": 0.42},
    # Big rock face with Leo
    {"file": "clue/clue_04_rock.png",
     "cx": 0.50, "emoji_w": 0.38, "emoji_y": 0.48},
    # Jungle classroom board
    {"file": "clue/clue_05_jungle_classroom.png",
     "cx": 0.50, "emoji_w": 0.45, "emoji_y": 0.38},
    # Big round rock with Leo Kids
    {"file": "clue/clue_06_kids_rock.png",
     "cx": 0.52, "emoji_w": 0.35, "emoji_y": 0.46},
]

# Reveal scene backgrounds (stage/platform for answer photo)
REVEAL_BACKGROUNDS = [
    # Each BG has a stone pathway / clearing in the center-bottom
    # Photo is placed right in that blank space
    {"file": "reveal/reveal_01_tropical.png",
     "cx": 0.50, "cy": 0.58, "photo_w": 0.32, "photo_h": 0.38},
    {"file": "reveal/reveal_02_jungle.png",
     "cx": 0.50, "cy": 0.58, "photo_w": 0.32, "photo_h": 0.38},
    {"file": "reveal/reveal_03_pathway.png",
     "cx": 0.50, "cy": 0.58, "photo_w": 0.32, "photo_h": 0.38},
    {"file": "reveal/reveal_04_meadow.png",
     "cx": 0.50, "cy": 0.58, "photo_w": 0.32, "photo_h": 0.38},
    {"file": "reveal/reveal_05_night.png",
     "cx": 0.50, "cy": 0.58, "photo_w": 0.32, "photo_h": 0.38},
    {"file": "reveal/reveal_06_temple.png",
     "cx": 0.50, "cy": 0.58, "photo_w": 0.32, "photo_h": 0.38},
    {"file": "reveal/reveal_07_ruins.png",
     "cx": 0.50, "cy": 0.58, "photo_w": 0.32, "photo_h": 0.38},
]

# Caches for the chosen backgrounds (set once per video)
_clue_bg_cache: Image.Image = None
_clue_bg_config: dict = None
_reveal_bg_cache: Image.Image = None
_reveal_bg_config: dict = None
_transition_bg_cache: Image.Image = None
_transition_top_cache: Image.Image = None
_transition_bot_cache: Image.Image = None
_outro_bg_cache: Image.Image = None
_outro_top_cache: Image.Image = None
_outro_bot_cache: Image.Image = None


def _load_scene_bg(bg_config: dict, w: int, h: int) -> Image.Image:
    """# Load and resize a scene background to exact video dimensions."""
    path = _BG_DIR / bg_config["file"]
    if not path.exists():
        return None
    img = Image.open(path).convert("RGBA")
    # Cover-crop to video aspect ratio
    img_ratio = img.width / img.height
    target_ratio = w / h
    if img_ratio > target_ratio:
        new_h = h
        new_w = int(h * img_ratio)
    else:
        new_w = w
        new_h = int(w / img_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def _init_scene_backgrounds(w: int, h: int, seed: int = None):
    """# Pick one clue BG + one reveal BG for the whole video.
    # Also load the transition slide background.
    # Only picks from backgrounds whose image files actually exist."""
    global _clue_bg_cache, _clue_bg_config
    global _reveal_bg_cache, _reveal_bg_config
    global _transition_bg_cache, _outro_bg_cache
    rng = random.Random(seed)

    # Filter to only BGs with existing image files
    avail_clue = [bg for bg in CLUE_BACKGROUNDS
                  if (_BG_DIR / bg["file"]).exists()]
    avail_reveal = [bg for bg in REVEAL_BACKGROUNDS
                    if (_BG_DIR / bg["file"]).exists()]

    if avail_clue:
        chosen_clue = rng.choice(avail_clue)
        _clue_bg_config = chosen_clue
        _clue_bg_cache = _load_scene_bg(chosen_clue, w, h)
        print(f"[EMOJI] Clue BG: {Path(chosen_clue['file']).stem}")
    else:
        print("[EMOJI] No clue backgrounds found — using gradient fallback")

    if avail_reveal:
        chosen_reveal = rng.choice(avail_reveal)
        _reveal_bg_config = chosen_reveal
        _reveal_bg_cache = _load_scene_bg(chosen_reveal, w, h)
        print(f"[EMOJI] Reveal BG: {Path(chosen_reveal['file']).stem}")
    else:
        print("[EMOJI] No reveal backgrounds found — using gradient fallback")

    # Load transition slide (Leo Quizz branded bumper between rounds)
    # Pre-split into top/bottom halves for the split animation
    trans_path = _BG_DIR / "transition.png"
    if trans_path.exists():
        _transition_bg_cache = _load_scene_bg({"file": "transition.png"}, w, h)
        _transition_top_cache = _transition_bg_cache.crop((0, 0, w, h // 2))
        _transition_bot_cache = _transition_bg_cache.crop((0, h // 2, w, h))
        print("[EMOJI] Transition BG: loaded")
    else:
        _transition_bg_cache = None

    # Load outro background ("Good Job!" celebration scene)
    # Pre-split into top/bottom halves for split entrance animation
    outro_path = _BG_DIR / "outro.png"
    if outro_path.exists():
        _outro_bg_cache = _load_scene_bg({"file": "outro.png"}, w, h)
        _outro_top_cache = _outro_bg_cache.crop((0, 0, w, h // 2))
        _outro_bot_cache = _outro_bg_cache.crop((0, h // 2, w, h))
        print("[EMOJI] Outro BG: loaded")
    else:
        _outro_bg_cache = None


def _get_clue_bg() -> tuple[Image.Image, dict]:
    """# Return the cached clue background + config."""
    return _clue_bg_cache, _clue_bg_config


def _get_reveal_bg() -> tuple[Image.Image, dict]:
    """# Return the cached reveal background + config."""
    return _reveal_bg_cache, _reveal_bg_config


@dataclass
class EmojiQuizContext:
    """# All data needed to render any frame of the emoji quiz video."""
    width: int                          # Frame width (1920)
    height: int                         # Frame height (1080)
    category: str                       # Emoji category (animals, food, etc.)
    rounds: list[EmojiQuizRound]        # All quiz round data
    total_rounds: int                   # Total number of rounds
    mascot_images: dict                 # {"thinking": Image, "excited": Image, ...}
    timeline: list[dict]                # Timed events for the full video
    confetti_bursts: list[ConfettiBurst] = field(default_factory=list)
    sparkles: ParticleSystem = None     # Floating sparkle particles
    narration_pack: object = None       # EmojiNarrationPack for subtitles
    answer_images: dict = field(default_factory=dict)  # {round_idx: PIL.Image}
    _mascot_cache: dict = field(default_factory=dict)


# ============================================================
# TIMELINE BUILDER
# ============================================================

def build_emoji_timeline(num_rounds: int,
                          intro_duration: float = None) -> list[dict]:
    """
    # Build the complete video timeline for an emoji quiz.
    # Structure: intro → [section_card → 10 rounds] × 4 → outro
    #
    # intro_duration: if provided, uses this instead of the config
    #   default — ensures the intro phase is long enough for the
    #   voiceover to finish before rounds start (no overlap).
    """
    timeline = []
    t = 0.0

    # --- Intro phase ---
    # Use dynamic duration so voiceover finishes before rounds start.
    # Add 1.5s padding after voice ends for breathing room.
    actual_intro = max(
        config.EMOJI_INTRO_DURATION,
        (intro_duration or 0.0) + 1.5
    )
    timeline.append({
        "phase": "intro", "start": t,
        "end": t + actual_intro, "round": -1,
    })
    t += actual_intro

    # --- Quiz rounds grouped by difficulty ---
    # Supports dict or int for rounds-per-tier.
    # When total rounds < sum of tier allocations (e.g. --rounds 4),
    # scale proportionally so every tier gets some rounds.
    rpd = config.EMOJI_ROUNDS_PER_DIFFICULTY
    round_idx = 0

    # Pre-calculate actual rounds per tier (proportional scaling)
    tier_round_counts = {}
    if isinstance(rpd, dict):
        total_config = sum(rpd.get(d, 10) for d in config.EMOJI_DIFFICULTIES)
        assigned = 0
        for i, d in enumerate(config.EMOJI_DIFFICULTIES):
            if i == len(config.EMOJI_DIFFICULTIES) - 1:
                tier_round_counts[d] = num_rounds - assigned
            else:
                tier_round_counts[d] = round(num_rounds * rpd.get(d, 10) / total_config)
                assigned += tier_round_counts[d]
    else:
        for d in config.EMOJI_DIFFICULTIES:
            tier_round_counts[d] = num_rounds // len(config.EMOJI_DIFFICULTIES)

    for tier_idx, difficulty in enumerate(config.EMOJI_DIFFICULTIES):
        tier_rounds = tier_round_counts.get(difficulty, 0)
        if tier_rounds <= 0:
            continue

        # Section card before each tier
        timeline.append({
            "phase": "section_card", "start": t,
            "end": t + config.EMOJI_SECTION_CARD_DURATION,
            "round": -1, "difficulty": difficulty,
        })
        t += config.EMOJI_SECTION_CARD_DURATION
        for i in range(tier_rounds):
            rd = config.EMOJI_ROUND_DURATION
            timeline.extend([
                {"phase": "question", "start": t,
                 "end": t + config.EMOJI_REVEAL_START,
                 "round": round_idx, "difficulty": difficulty},
                {"phase": "reveal", "start": t + config.EMOJI_REVEAL_START,
                 "end": t + config.EMOJI_FACT_START,
                 "round": round_idx, "difficulty": difficulty},
                {"phase": "fact", "start": t + config.EMOJI_FACT_START,
                 "end": t + config.EMOJI_TRANSITION_START,
                 "round": round_idx, "difficulty": difficulty},
                {"phase": "transition",
                 "start": t + config.EMOJI_TRANSITION_START,
                 "end": t + rd,
                 "round": round_idx, "difficulty": difficulty},
            ])
            t += rd
            round_idx += 1

    # --- Outro phase ---
    timeline.append({
        "phase": "outro", "start": t,
        "end": t + config.EMOJI_OUTRO_DURATION, "round": -1,
    })

    return timeline


# ============================================================
# BACKGROUND RENDERER — Per-category colored gradient + emoji pattern
# ============================================================

# --- Caches for backgrounds (keyed by category + size) ---
_bg_composite_cache = {}
_spotlight_cache = {}


def _render_bg(w: int, h: int, t: float,
               category: str = "animals") -> Image.Image:
    """
    # Render a colored gradient background that changes per category.
    # Hot pink for animals, blue for food, red for restaurants, etc.
    # Adds a subtle emoji pattern overlay for visual texture.
    # Animated radial spotlight for cinematic depth.
    #
    # PERF: gradient + emoji pattern are pre-composited once and cached.
    # Spotlight is pre-rendered as a single radial image and shifted per frame.
    """
    # --- Build and cache the gradient + pattern composite (once) ---
    composite_key = (w, h, category)
    if composite_key not in _bg_composite_cache:
        gradients = config.EMOJI_BG_GRADIENTS.get(category, {})
        c1_tuple = gradients.get("top", config.EMOJI_BG_GRADIENT_TOP)
        c2_tuple = gradients.get("bottom", config.EMOJI_BG_GRADIENT_BOTTOM)

        c1 = np.array(c1_tuple, dtype=np.float32)
        c2 = np.array(c2_tuple, dtype=np.float32)
        ratios = np.linspace(0, 1, h, dtype=np.float32).reshape(-1, 1)
        gradient = c1 * (1 - ratios) + c2 * ratios
        brightness = 1.0 + 0.1 * np.sin(ratios * math.pi)
        gradient *= brightness
        gradient = np.clip(gradient, 0, 255).astype(np.uint8)
        arr = np.broadcast_to(gradient[:, np.newaxis, :], (h, w, 3)).copy()
        bg = Image.fromarray(arr).convert("RGBA")

        # Emoji pattern overlay (subtle tiled emoji)
        pattern = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        deco_map = {
            "animals": ["🐾", "🦁", "🐵"],
            "food": ["🍕", "🍔", "🌮"],
            "restaurant": ["🍽️", "🍟", "🥤"],
            "candy": ["🍬", "🍭", "🧁"],
            "country": ["🌍", "🗺️", "✈️"],
            "movie": ["🎬", "🎥", "🍿"],
            "sport": ["⚽", "🏀", "🏆"],
        }
        deco_emoji = deco_map.get(category, ["⭐", "✨", "🎯"])
        emoji_size = 40
        spacing = 140
        for row in range(0, h, spacing):
            for col in range(0, w, spacing):
                idx = ((row // spacing) + (col // spacing)) % len(deco_emoji)
                try:
                    em_img = get_emoji_image(deco_emoji[idx], emoji_size,
                                             sticker=False)
                    if em_img is None:
                        continue
                    em_arr = np.array(em_img)
                    em_arr[:, :, 3] = (em_arr[:, :, 3] * 0.12).astype(np.uint8)
                    faint = Image.fromarray(em_arr)
                    pattern.paste(faint, (col, row), faint)
                except Exception:
                    pass

        _bg_composite_cache[composite_key] = Image.alpha_composite(bg, pattern)

    # --- Build and cache the spotlight radial gradient (once) ---
    spot_key = (w, h)
    if spot_key not in _spotlight_cache:
        radius = int(w * 0.45)
        spot_size = radius * 2
        spot_img = Image.new("RGBA", (spot_size, spot_size), (0, 0, 0, 0))
        sd = ImageDraw.Draw(spot_img)
        for r in range(radius, 0, -6):
            progress = r / radius
            alpha = int(15 * (1 - progress * progress))
            sd.ellipse([radius - r, radius - r, radius + r, radius + r],
                       fill=(255, 255, 255, alpha))
        _spotlight_cache[spot_key] = spot_img

    # --- Compose: cached bg + shifted spotlight ---
    bg = _bg_composite_cache[composite_key].copy()
    spot = _spotlight_cache[spot_key]
    spot_r = spot.width // 2
    cx = int(w * 0.5 + w * 0.12 * math.sin(t * 0.25)) - spot_r
    cy = int(h * 0.38) - spot_r
    bg.paste(spot, (cx, cy), spot)

    return bg


# ============================================================
# TITLE BANNER — "GUESS THE [CATEGORY]" with red banner
# ============================================================

def _render_title_banner(frame: Image.Image, category: str,
                          round_num: int, total_rounds: int) -> Image.Image:
    """
    # Render the Monkey Quiz-style title at the top.
    # "GUESS THE" in white bold, then category word in YELLOW
    # on a RED banner/label shape.
    """
    w, h = frame.size
    cat_info = config.EMOJI_CATEGORIES.get(category, {})
    display = cat_info.get("display", category.upper())

    # --- Fonts ---
    title_font = _get_font(config.EMOJI_TITLE_FONT_SIZE, bold=True)
    cat_font = _get_font(int(config.EMOJI_TITLE_FONT_SIZE * 1.1), bold=True)

    # --- Calculate positions ---
    prefix = "GUESS THE "
    prefix_w = title_font.getlength(prefix)
    cat_w = cat_font.getlength(display)

    # Total width for centering
    total_w = prefix_w + cat_w + 20  # 20px gap
    start_x = (w - total_w) / 2
    title_y = 35

    # --- Draw on overlay for clean alpha ---
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # --- RED banner behind the category word ---
    banner_x1 = int(start_x + prefix_w + 5)
    banner_y1 = int(title_y - 8)
    banner_x2 = int(banner_x1 + cat_w + 24)
    banner_y2 = int(title_y + config.EMOJI_TITLE_FONT_SIZE + 8)
    # Banner shadow
    draw.rounded_rectangle(
        [banner_x1 + 4, banner_y1 + 4, banner_x2 + 4, banner_y2 + 4],
        radius=10, fill=(0, 0, 0, 80))
    # Red banner
    draw.rounded_rectangle(
        [banner_x1, banner_y1, banner_x2, banner_y2],
        radius=10, fill=(220, 20, 20, 255))

    # --- "GUESS THE" in white with shadow ---
    text_x = start_x
    text_cy = title_y + config.EMOJI_TITLE_FONT_SIZE // 2
    # Shadow
    draw.text((text_x + 3, text_cy + 3), prefix,
              fill=(0, 0, 0, 120), anchor="lm", font=title_font)
    # White text
    draw.text((text_x, text_cy), prefix,
              fill=(255, 255, 255, 255), anchor="lm", font=title_font)

    # --- Category word in YELLOW on the red banner ---
    cat_x = banner_x1 + 12
    # Shadow
    draw.text((cat_x + 2, text_cy + 2), display,
              fill=(0, 0, 0, 100), anchor="lm", font=cat_font)
    # Yellow text
    draw.text((cat_x, text_cy), display,
              fill=(255, 255, 0, 255), anchor="lm", font=cat_font)

    frame = Image.alpha_composite(frame, overlay)

    # --- Round counter badge (top-right) ---
    draw2 = ImageDraw.Draw(frame)
    badge_font = _get_font(30, bold=True)
    badge_text = f"Round {round_num}/{total_rounds}"
    badge_x = w - 200
    badge_y = 40
    draw2.rounded_rectangle(
        [badge_x - 10, badge_y - 8, badge_x + 180, badge_y + 38],
        radius=20, fill=(0, 0, 0, 130))
    draw2.text((badge_x + 85, badge_y + 15), badge_text,
               fill=(255, 255, 255), anchor="mm", font=badge_font)

    return frame


# ============================================================
# EMOJI CLUES RENDERER — Big Twemoji PNGs with shadows
# ============================================================

def _render_emoji_clues(frame: Image.Image, emoji_clues: list[str],
                         t: float, round_start: float) -> Image.Image:
    """
    # Render sticker emoji on the whiteboard/rock surface.
    # Position adapts to the chosen clue background's content zone.
    # Size adapts to number of clues.
    """
    w, h = frame.size
    elapsed = t - round_start

    num_emoji = len(emoji_clues)
    # --- Dynamic sizing: fewer clues = bigger emoji ---
    _CLUE_SIZES = {1: 280, 2: 240, 3: 200, 4: 170, 5: 150}
    emoji_size = _CLUE_SIZES.get(num_emoji, 140)
    gap = max(20, 50 - num_emoji * 6)

    # --- Position on whiteboard/rock using background config ---
    _, bg_cfg = _get_clue_bg()
    if bg_cfg:
        emoji_cx = bg_cfg.get("cx", 0.50)
        emoji_cy = bg_cfg.get("emoji_y", 0.34)
        max_emoji_w = bg_cfg.get("emoji_w", 0.60)
        # Clamp emoji row width to fit within the board
        total_w = num_emoji * emoji_size + (num_emoji - 1) * gap
        max_px = int(w * max_emoji_w)
        if total_w > max_px:
            ratio = max_px / total_w
            emoji_size = int(emoji_size * ratio)
            gap = int(gap * ratio)
            total_w = num_emoji * emoji_size + (num_emoji - 1) * gap
        start_x = int(w * emoji_cx - total_w / 2)
        center_y = int(h * emoji_cy) - emoji_size // 2
    else:
        total_w = num_emoji * emoji_size + (num_emoji - 1) * gap
        start_x = int((w - total_w) / 2)
        center_y = int(h * 0.38) - emoji_size // 2

    x_cursor = start_x
    for i, emoji_char in enumerate(emoji_clues):
        # --- Staggered entry: each emoji pops in 0.7s after the last ---
        entry_delay = i * 0.7
        entry_elapsed = elapsed - entry_delay

        if entry_elapsed < 0:
            x_cursor += emoji_size + gap
            continue

        # --- Big elastic bounce-in (dramatic pop) ---
        if entry_elapsed < 0.5:
            p = entry_elapsed / 0.5
            if p < 0.5:
                scale = p * 2.0 * 1.3
            else:
                overshoot = 1.3 - (p - 0.5) * 2.0 * 0.3
                scale = max(1.0, overshoot)
        else:
            scale = 1.0
            scale += math.sin(t * 1.8 + i * 1.5) * 0.02

        # --- Get sticker emoji at BASE size (cached), then resize for anim ---
        emoji_img = get_emoji_image(emoji_char, emoji_size)
        if emoji_img is None:
            x_cursor += emoji_size + gap
            continue
        if abs(scale - 1.0) > 0.01:
            new_w = int(emoji_img.width * scale)
            new_h = int(emoji_img.height * scale)
            emoji_img = emoji_img.resize((new_w, new_h), Image.LANCZOS)

        x_pos = x_cursor + (emoji_size - emoji_img.width) // 2
        y_pos = center_y + (emoji_size - emoji_img.height) // 2
        bob_y = int(math.sin(t * 2.0 + i * 1.5) * 5)

        frame.paste(emoji_img, (x_pos, y_pos + bob_y), emoji_img)
        x_cursor += emoji_size + gap

    return frame


# ============================================================
# QUESTION MARK + TIMER
# ============================================================

def _render_question_mark(frame: Image.Image, t: float,
                           round_start: float) -> Image.Image:
    """
    # Render a large pulsing "?" below the emoji with golden glow.
    """
    w, h = frame.size
    elapsed = t - round_start
    if elapsed < 0.5:
        return frame

    pulse = 0.85 + 0.15 * math.sin(t * 3.0)
    size = int(90 * pulse)
    font = _get_font(size, bold=True)
    qm_y = int(h * 0.65)

    # --- Golden glow ---
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(overlay)
    for r in range(50, 0, -3):
        a = int(25 * (1 - r / 50))
        glow_draw.ellipse([w // 2 - r, qm_y - r, w // 2 + r, qm_y + r],
                          fill=(255, 215, 0, a))
    frame = Image.alpha_composite(frame, overlay)

    draw = ImageDraw.Draw(frame)
    draw.text((w // 2 + 3, qm_y + 3), "?", fill=(0, 0, 0, 100),
              anchor="mm", font=font)
    draw.text((w // 2, qm_y), "?", fill=(255, 215, 0),
              anchor="mm", font=font)

    return frame


def _render_timer_bar(frame: Image.Image, t: float,
                       round_start: float) -> Image.Image:
    """
    # Monkey Quiz-style countdown timer bar.
    # Wide orange-to-red gradient bar at bottom center.
    # Depletes from right to left as time runs out.
    # Rounded pill shape with dark border.
    """
    w, h = frame.size
    elapsed = t - round_start - config.EMOJI_EMOJI_SETTLE
    if elapsed < 0:
        return frame

    timer_duration = config.EMOJI_TIMER_SECONDS
    progress = max(0.0, min(1.0, elapsed / timer_duration))
    remaining = 1.0 - progress

    # --- Dimensions (wide, prominent bar) ---
    bar_w = int(w * 0.65)
    bar_h = 32
    bar_x = (w - bar_w) // 2
    bar_y = int(h * 0.78)

    # --- Dark border/background ---
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    border = 4
    od.rounded_rectangle(
        [bar_x - border, bar_y - border,
         bar_x + bar_w + border, bar_y + bar_h + border],
        radius=(bar_h + border * 2) // 2,
        fill=(30, 20, 40, 220))

    # --- Colored fill (orange → red gradient as time depletes) ---
    fill_w = int(bar_w * remaining)
    if fill_w > bar_h // 2:
        # Color: orange when full → red when almost empty
        if remaining > 0.5:
            r_c = 255
            g_c = int(180 * remaining)
            b_c = 20
        else:
            r_c = 230
            g_c = int(80 * remaining * 2)
            b_c = int(30 * remaining)

        # Pulse in last 20%
        if remaining < 0.2:
            pulse = int(40 * abs(math.sin(t * 8.0)))
            r_c = min(255, r_c + pulse)
            g_c = max(0, g_c - pulse)

        od.rounded_rectangle(
            [bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
            radius=bar_h // 2, fill=(r_c, g_c, b_c))

        # Bright highlight stripe on top half for 3D look
        highlight_h = bar_h // 3
        od.rounded_rectangle(
            [bar_x + 4, bar_y + 2,
             bar_x + fill_w - 4, bar_y + highlight_h],
            radius=highlight_h // 2,
            fill=(255, 255, 255, 60))

    frame = Image.alpha_composite(frame, overlay)

    # --- Seconds countdown number above bar ---
    secs_left = max(0, int(timer_duration - elapsed))
    timer_font = _get_font(40, bold=True)
    draw = ImageDraw.Draw(frame)
    draw.text((w // 2 + 2, bar_y - 30 + 2), str(secs_left),
              fill=(0, 0, 0, 120), anchor="mm", font=timer_font)
    draw.text((w // 2, bar_y - 30), str(secs_left),
              fill=(255, 255, 255), anchor="mm", font=timer_font)

    return frame


def _render_emoji_reminder(frame: Image.Image,
                            emoji_clues: list[str]) -> Image.Image:
    """
    # Small emoji clues at the top of the reveal screen as a reminder.
    # Shows what the clues were, smaller than during the question phase.
    """
    w, h = frame.size
    emoji_size = 80
    gap = 20
    num = len(emoji_clues)
    total_w = num * emoji_size + (num - 1) * gap
    start_x = (w - total_w) // 2
    y = int(h * 0.06)

    for i, emoji_char in enumerate(emoji_clues):
        emoji_img = get_emoji_image(emoji_char, emoji_size)
        if emoji_img:
            # Center sticker image (includes outline padding) in the slot
            x = start_x + i * (emoji_size + gap) + (emoji_size - emoji_img.width) // 2
            y_adj = y + (emoji_size - emoji_img.height) // 2
            frame.paste(emoji_img, (x, y_adj), emoji_img)

    return frame


# ============================================================
# ANSWER REVEAL
# ============================================================

def _render_answer_reveal(frame: Image.Image, answer: str,
                           t: float, reveal_start: float,
                           answer_img: Image.Image = None) -> Image.Image:
    """
    # Monkey Quiz-style answer reveal:
    # LARGE photo filling center of screen in a rounded rectangle frame
    # with decorative border, answer name in a red banner below the photo.
    # If no photo available, falls back to text-only reveal.
    """
    w, h = frame.size
    elapsed = t - reveal_start
    if elapsed < 0:
        return frame

    # --- Pop-in scale animation ---
    if elapsed < 0.4:
        p = elapsed / 0.4
        scale = min(1.0, p * 1.2)
        if p > 0.7:
            scale = 1.0 + (1.2 - 1.0) * (1.0 - (p - 0.7) / 0.3) * 0.1
    else:
        scale = 1.0

    full_text = answer.upper()

    if answer_img is not None:
        # --- LARGE photo positioned on the reveal background stage ---
        _, rev_cfg = _get_reveal_bg()
        if rev_cfg:
            base_pw = int(w * rev_cfg.get("photo_w", 0.38))
            base_ph = int(h * rev_cfg.get("photo_h", 0.42))
            photo_cx = int(w * rev_cfg.get("cx", 0.50))
            photo_cy = int(h * rev_cfg.get("cy", 0.52))
        else:
            base_pw, base_ph = 700, 480
            photo_cx = w // 2
            photo_cy = int(h * 0.40)
        photo_w = int(base_pw * scale)
        photo_h = int(base_ph * scale)

        # Resize photo to fill frame (cover crop)
        img_ratio = answer_img.width / answer_img.height
        target_ratio = photo_w / photo_h
        if img_ratio > target_ratio:
            rh = photo_h
            rw = int(photo_h * img_ratio)
        else:
            rw = photo_w
            rh = int(photo_w / img_ratio)
        resized = answer_img.resize((rw, rh), Image.LANCZOS)
        left = (rw - photo_w) // 2
        top = (rh - photo_h) // 2
        cropped = resized.crop((left, top, left + photo_w, top + photo_h))

        # Rounded rectangle mask
        mask = Image.new("L", (photo_w, photo_h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle(
            [0, 0, photo_w - 1, photo_h - 1],
            radius=24, fill=255)

        # White border frame (8px)
        border = 8
        frame_w = photo_w + border * 2
        frame_h = photo_h + border * 2
        photo_frame = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
        pf_draw = ImageDraw.Draw(photo_frame)
        # Outer border (white with slight shadow)
        pf_draw.rounded_rectangle(
            [0, 0, frame_w - 1, frame_h - 1],
            radius=28, fill=(255, 255, 255))
        # Paste photo with mask
        photo_rgba = Image.new("RGBA", (photo_w, photo_h), (0, 0, 0, 0))
        photo_rgba.paste(cropped.convert("RGBA"), (0, 0), mask)
        photo_frame.paste(photo_rgba, (border, border), photo_rgba)

        # Shadow behind the frame
        shadow_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_overlay)
        sx = photo_cx - frame_w // 2 + 6
        sy = photo_cy - frame_h // 2 + 6
        sd.rounded_rectangle(
            [sx, sy, sx + frame_w, sy + frame_h],
            radius=30, fill=(0, 0, 0, 80))
        frame = Image.alpha_composite(frame, shadow_overlay)

        # Paste the framed photo
        fx = photo_cx - frame_w // 2
        fy = photo_cy - frame_h // 2
        frame.paste(photo_frame, (fx, fy), photo_frame)

        # --- Red banner with answer name below photo ---
        banner_y = photo_cy + frame_h // 2 + 20
    else:
        banner_y = int(h * 0.65)

    # --- Answer banner (red gradient pill with answer text) ---
    size = int(config.EMOJI_ANSWER_FONT_SIZE * scale)
    font = _get_font(size, bold=True)
    text_w = font.getlength(full_text)

    banner_w = int(text_w + 80)
    banner_h = size + 30
    banner_x = (w - banner_w) // 2

    banner_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(banner_overlay)
    # Shadow
    bd.rounded_rectangle(
        [banner_x + 4, banner_y + 4,
         banner_x + banner_w + 4, banner_y + banner_h + 4],
        radius=banner_h // 2, fill=(0, 0, 0, 100))
    # Red banner body
    bd.rounded_rectangle(
        [banner_x, banner_y, banner_x + banner_w, banner_y + banner_h],
        radius=banner_h // 2, fill=(200, 20, 30))
    # Highlight strip on top half
    bd.rounded_rectangle(
        [banner_x + 6, banner_y + 3,
         banner_x + banner_w - 6, banner_y + banner_h // 2],
        radius=banner_h // 4, fill=(240, 50, 50, 80))
    # Answer text (white, centered)
    bd.text((w // 2, banner_y + banner_h // 2), full_text,
            fill=(255, 255, 255), anchor="mm", font=font)
    frame = Image.alpha_composite(frame, banner_overlay)

    return frame


def _render_fun_fact(frame: Image.Image, fact: str,
                      t: float, fact_start: float) -> Image.Image:
    """# Fun fact text in a pill below the answer, fades in from below."""
    w, h = frame.size
    elapsed = t - fact_start
    if elapsed < 0 or not fact:
        return frame

    if elapsed < 0.3:
        alpha = int(255 * (elapsed / 0.3))
        offset_y = int(15 * (1 - elapsed / 0.3))
    else:
        alpha = 255
        offset_y = 0

    font = _get_font(30, bold=True)
    fact_y = int(h * 0.78) + offset_y

    draw = ImageDraw.Draw(frame)
    fact_w = font.getlength(fact)
    pill_pad = 24
    pill_x1 = int((w - fact_w) / 2 - pill_pad)
    pill_x2 = int((w + fact_w) / 2 + pill_pad)
    draw.rounded_rectangle(
        [pill_x1, fact_y - 20, pill_x2, fact_y + 20],
        radius=18, fill=(0, 0, 0, min(160, alpha)))
    draw.text((w // 2, fact_y), fact,
              fill=(255, 255, 255, alpha), anchor="mm", font=font)

    return frame


# ============================================================
# SCORE BAR
# ============================================================

def _render_score_bar(frame: Image.Image, score: int,
                       total_rounds: int) -> Image.Image:
    """# Score counter at bottom with progress bar."""
    w, h = frame.size

    # --- Semi-transparent bar ---
    bar_h = 50
    bar_overlay = Image.new("RGBA", (w, bar_h), (0, 0, 0, 110))
    frame.paste(bar_overlay, (0, h - bar_h), bar_overlay)

    draw = ImageDraw.Draw(frame)
    font = _get_font(26, bold=True)
    bar_y = h - bar_h

    # Score text (left)
    draw.text((30, bar_y + bar_h // 2),
              f"SCORE: {score}/{total_rounds}",
              fill=(255, 215, 0), anchor="lm", font=font)

    # Progress bar (right)
    prog_w = 280
    prog_h = 12
    prog_x = w - prog_w - 30
    prog_y = bar_y + (bar_h - prog_h) // 2
    progress = score / max(1, total_rounds)

    draw.rounded_rectangle(
        [prog_x, prog_y, prog_x + prog_w, prog_y + prog_h],
        radius=prog_h // 2, fill=(50, 20, 70))
    fill_w = int(prog_w * progress)
    if fill_w > 0:
        draw.rounded_rectangle(
            [prog_x, prog_y, prog_x + fill_w, prog_y + prog_h],
            radius=prog_h // 2, fill=(255, 215, 0))

    return frame


# ============================================================
# WORD-BY-WORD SUBTITLE RENDERER
# ============================================================

def _render_subtitle(frame: Image.Image, text: str, t: float,
                      clip_start: float, clip_duration: float,
                      y_pos: float = 0.88) -> Image.Image:
    """
    # TRUE word-by-word subtitle reveal synced to voiceover.
    # Shows ALL words on screen — already-spoken words in white,
    # currently-spoken word in bright YELLOW with scale pop,
    # upcoming words dimmed out. Dark pill background.
    """
    if not text or clip_duration <= 0:
        return frame

    w, h = frame.size
    elapsed = t - clip_start
    if elapsed < 0 or elapsed > clip_duration + 0.8:
        return frame

    words = text.split()
    if not words:
        return frame

    # --- Which word is currently being spoken? ---
    time_per_word = clip_duration / len(words)
    current_word_idx = min(len(words) - 1, int(elapsed / time_per_word))

    # --- For long sentences, show a sliding window of ~6 words ---
    max_visible = 6
    if len(words) > max_visible:
        # Center window around current word
        win_start = max(0, current_word_idx - max_visible // 2)
        win_end = min(len(words), win_start + max_visible)
        if win_end == len(words):
            win_start = max(0, win_end - max_visible)
        visible_words = words[win_start:win_end]
        visible_offset = win_start
    else:
        visible_words = words
        visible_offset = 0

    font = _get_font(46, bold=True)
    cx = w // 2
    cy = int(h * y_pos)

    # --- Measure total width of visible words ---
    space_w = font.getlength(" ")
    word_widths = [font.getlength(word) for word in visible_words]
    total_text_w = sum(word_widths) + space_w * (len(visible_words) - 1)

    # --- Dark pill background ---
    pill_pad = 36
    pill_h = 66
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    pill_x1 = int(cx - total_text_w / 2 - pill_pad)
    pill_x2 = int(cx + total_text_w / 2 + pill_pad)
    pill_y1 = cy - pill_h // 2
    pill_y2 = cy + pill_h // 2
    od.rounded_rectangle(
        [pill_x1, pill_y1, pill_x2, pill_y2],
        radius=pill_h // 2, fill=(0, 0, 0, 200))
    frame = Image.alpha_composite(frame, overlay)

    # --- Draw each word with color based on timing ---
    draw = ImageDraw.Draw(frame)
    x_cursor = cx - total_text_w / 2
    for i, word in enumerate(visible_words):
        abs_idx = i + visible_offset
        if abs_idx < current_word_idx:
            # Already spoken — white
            color = (255, 255, 255)
        elif abs_idx == current_word_idx:
            # Currently speaking — bright yellow
            color = (255, 255, 0)
        else:
            # Upcoming — dimmed
            color = (180, 180, 180, 120)
        draw.text((x_cursor, cy), word,
                  fill=color, anchor="lm", font=font)
        x_cursor += word_widths[i] + space_w

    return frame


# ============================================================
# SPECIAL SCREENS
# ============================================================

# --- Cached intro background image (loaded once) ---
_intro_bg_cache = None


def _get_intro_bg(w: int, h: int) -> Image.Image:
    """
    # Load and cache the branded intro background scene.
    # Uses the Leo Quizz landscape scene (rainbow, castle, mascot).
    # Falls back to gradient if the image file doesn't exist.
    """
    global _intro_bg_cache
    if _intro_bg_cache is not None:
        return _intro_bg_cache.copy()

    if config.INTRO_BACKGROUND.exists():
        img = Image.open(config.INTRO_BACKGROUND).convert("RGBA")
        # Resize to exact video dimensions (maintain aspect ratio, crop excess)
        img_ratio = img.width / img.height
        target_ratio = w / h
        if img_ratio > target_ratio:
            # Image is wider — fit height, crop width
            new_h = h
            new_w = int(h * img_ratio)
        else:
            # Image is taller — fit width, crop height
            new_w = w
            new_h = int(w / img_ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        # Center crop to exact video size
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        img = img.crop((left, top, left + w, top + h))
        _intro_bg_cache = img
        return img.copy()
    else:
        return None


# --- Cached scattered emoji positions (seeded per-video, not per-frame) ---
_intro_emoji_layout = None


def _get_intro_emoji_layout(w: int, h: int, category: str,
                             emoji_list: list, seed: int = 42) -> list:
    """
    # Structured emoji layout for intro — neat frame around the title.
    # 10 fixed positions: 3 left column, 3 right column, 2 top, 2 bottom.
    # All same size, evenly spaced, clean and intentional.
    """
    global _intro_emoji_layout
    if _intro_emoji_layout is not None:
        return _intro_emoji_layout

    rng = random.Random(seed)
    # Pick 10 unique emoji (no duplicates if possible)
    unique = list(dict.fromkeys(emoji_list))
    rng.shuffle(unique)
    chosen = unique[:10]
    while len(chosen) < 10:
        chosen.append(rng.choice(emoji_list))

    size = 200  # big sticker-style emoji for premium intro
    # Fixed grid positions (x, y) — frame around center title area
    # Left column (3 emoji, evenly spaced vertically)
    # Right column (3 emoji, evenly spaced vertically)
    # Top row (2 emoji, spaced between left/right columns)
    # Bottom row (2 emoji, spaced between left/right columns)
    slots = [
        # Left column
        (int(w * 0.08), int(h * 0.18)),
        (int(w * 0.10), int(h * 0.48)),
        (int(w * 0.08), int(h * 0.78)),
        # Right column
        (int(w * 0.88), int(h * 0.18)),
        (int(w * 0.86), int(h * 0.48)),
        (int(w * 0.88), int(h * 0.78)),
        # Top row
        (int(w * 0.30), int(h * 0.08)),
        (int(w * 0.68), int(h * 0.08)),
        # Bottom row (above subtitle area)
        (int(w * 0.30), int(h * 0.72)),
        (int(w * 0.68), int(h * 0.72)),
    ]

    positions = []
    for i, emoji_char in enumerate(chosen):
        x, y = slots[i]
        pop_time = 0.2 + i * 0.12
        wobble_phase = rng.random() * math.pi * 2
        positions.append((emoji_char, x, y, size, pop_time, wobble_phase))

    _intro_emoji_layout = positions
    return positions


def _render_intro_frame(t: float, ctx: EmojiQuizContext) -> np.ndarray:
    """
    # 3-phase intro matching Monkey Quiz quality:
    #
    # PHASE 1 (0-3s): Leo Quizz branding landscape with Ken Burns zoom.
    #   Shows the branded scene briefly — establishes the channel.
    #
    # PHASE 2 (3s - subscribe_start): Cross-fade to scattered emoji scene.
    #   "Guess The [CATEGORY] by EMOJI" title + round/timer info.
    #   Emoji pop in one by one around the edges.
    #
    # PHASE 3 (subscribe_start - intro_end): Subscribe/Follow buttons.
    #   Pulsing red subscribe + blue follow buttons with glow.
    #   Plays while the subscribe voiceover is heard.
    """
    w, h = ctx.width, ctx.height
    elapsed = t
    narr = ctx.narration_pack

    # --- Timing boundaries ---
    branding_end = 3.0  # phase 1 ends, cross-fade begins
    fade_dur = 0.6      # cross-fade duration
    # Subscribe phase starts when subscribe voice plays
    sub_start = 0.3 + (narr.intro_duration if narr else 8.0) + 0.3

    # ================================================================
    # PHASE 1: Leo Quizz branding landscape (0 - 3s)
    # ================================================================
    if elapsed < branding_end + fade_dur:
        intro_bg = _get_intro_bg(w, h)
        if intro_bg is not None:
            # Ken Burns slow zoom
            zoom = 1.0 + elapsed * 0.015
            zw = int(w * zoom)
            zh = int(h * zoom)
            zoomed = intro_bg.resize((zw, zh), Image.LANCZOS)
            left = (zw - w) // 2
            top = (zh - h) // 2
            branding_frame = zoomed.crop((left, top, left + w, top + h))
            branding_frame = branding_frame.convert("RGBA")
        else:
            branding_frame = _render_bg(w, h, t, ctx.category)

        # If still fully in phase 1 (no cross-fade yet), return early
        if elapsed < branding_end:
            frame = branding_frame
            # Subtitle during phase 1 too
            if narr and narr.intro_text and narr.intro_duration > 0:
                frame = _render_subtitle(
                    frame, narr.intro_text, t,
                    clip_start=0.3,
                    clip_duration=narr.intro_duration,
                    y_pos=0.88)
            return np.array(frame.convert("RGB"))

    # ================================================================
    # PHASE 2+3: Scattered emoji scene (3s onward)
    # ================================================================
    frame = _render_bg(w, h, t, ctx.category)

    # --- Scattered emoji popping in ---
    all_emoji = []
    for rnd in ctx.rounds:
        all_emoji.extend(rnd.emoji_clues)
    if all_emoji:
        layout = _get_intro_emoji_layout(w, h, ctx.category, all_emoji)
        scene_elapsed = elapsed - branding_end  # time since emoji scene started
        for emoji_char, ex, ey, esize, pop_time, wobble_phase in layout:
            if scene_elapsed < pop_time:
                continue
            pop_elapsed = scene_elapsed - pop_time
            if pop_elapsed < 0.3:
                scale = pop_elapsed / 0.3
                scale = 1.0 + 0.3 * math.sin(scale * math.pi)
            else:
                scale = 1.0
            wobble_y = math.sin(elapsed * 1.5 + wobble_phase) * 6
            wobble_x = math.cos(elapsed * 1.2 + wobble_phase) * 4
            # Get at base size (cached), resize for pop animation
            emoji_img = get_emoji_image(emoji_char, size=esize)
            if emoji_img is None:
                continue
            if abs(scale - 1.0) > 0.01:
                new_sz = int(emoji_img.width * scale)
                emoji_img = emoji_img.resize((new_sz, new_sz), Image.LANCZOS)
            if emoji_img:
                paste_x = int(ex + wobble_x - emoji_img.width // 2)
                paste_y = int(ey + wobble_y - emoji_img.height // 2)
                if (0 <= paste_x < w - 20 and 0 <= paste_y < h - 20):
                    frame.paste(emoji_img, (paste_x, paste_y), emoji_img)

    # --- Cross-fade from branding to emoji scene ---
    if elapsed < branding_end + fade_dur:
        fade_progress = (elapsed - branding_end) / fade_dur
        # Blend: branding fades out, emoji scene fades in
        blend_alpha = int(255 * fade_progress)
        branding_rgb = branding_frame.convert("RGB")
        emoji_rgb = frame.convert("RGB")
        blended = Image.blend(branding_rgb, emoji_rgb, fade_progress / 1.0)
        frame = blended.convert("RGBA")

    draw = ImageDraw.Draw(frame)

    # --- Title: "Guess The [CATEGORY] by EMOJI" ---
    cat_info = config.EMOJI_CATEGORIES.get(ctx.category, {})
    display = cat_info.get("display", ctx.category.upper())
    scene_elapsed = max(0, elapsed - branding_end)

    if scene_elapsed > 0.3:
        slide_progress = min(1.0, (scene_elapsed - 0.3) / 0.5)
        slide_ease = 1.0 - (1.0 - slide_progress) ** 3
        title_y = int(h * 0.32 + (1 - slide_ease) * 80)

        guess_font = _get_font(64, bold=True)
        draw.text((w // 2 + 3, title_y + 3), "Guess The",
                  fill=(0, 0, 0, 120), anchor="mm", font=guess_font)
        draw.text((w // 2, title_y), "Guess The",
                  fill=(255, 255, 255), anchor="mm", font=guess_font)

        cat_font = _get_font(90, bold=True)
        cat_w = cat_font.getlength(display)
        banner_pad = 24
        banner_x1 = int((w - cat_w) / 2 - banner_pad)
        banner_y1 = title_y + 30
        banner_x2 = int((w + cat_w) / 2 + banner_pad)
        banner_y2 = title_y + 105
        draw.rounded_rectangle(
            [banner_x1 + 4, banner_y1 + 4, banner_x2 + 4, banner_y2 + 4],
            radius=14, fill=(0, 0, 0, 80))
        draw.rounded_rectangle(
            [banner_x1, banner_y1, banner_x2, banner_y2],
            radius=14, fill=(220, 20, 20))
        draw.text((w // 2, title_y + 67), display,
                  fill=(255, 255, 0), anchor="mm", font=cat_font)

        if scene_elapsed > 0.8:
            emoji_font = _get_font(56, bold=True)
            sub_alpha = min(255, int((scene_elapsed - 0.8) * 600))
            draw.text((w // 2 + 3, title_y + 133), "by EMOJI",
                      fill=(0, 0, 0, min(120, sub_alpha)),
                      anchor="mm", font=emoji_font)
            draw.text((w // 2, title_y + 130), "by EMOJI",
                      fill=(255, 255, 255, sub_alpha),
                      anchor="mm", font=emoji_font)

    # --- Round count + timer info ---
    if scene_elapsed > 1.5:
        info_alpha = min(255, int((scene_elapsed - 1.5) * 500))
        info_font = _get_font(48, bold=True)
        num_text = f"{ctx.total_rounds} Questions"
        time_text = f"{config.EMOJI_TIMER_SECONDS} Seconds"
        info_y = int(h * 0.54)

        nw = info_font.getlength(num_text)
        pill_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pill_overlay)
        pd.rounded_rectangle(
            [int(w / 2 - nw / 2 - 20), info_y - 26,
             int(w / 2 + nw / 2 + 20), info_y + 26],
            radius=26, fill=(40, 180, 60, info_alpha))
        tw = info_font.getlength(time_text)
        pd.rounded_rectangle(
            [int(w / 2 - tw / 2 - 20), info_y + 38,
             int(w / 2 + tw / 2 + 20), info_y + 90],
            radius=26, fill=(240, 160, 20, info_alpha))
        frame = Image.alpha_composite(frame, pill_overlay)
        draw = ImageDraw.Draw(frame)

        draw.text((w // 2, info_y), num_text,
                  fill=(255, 255, 255, info_alpha),
                  anchor="mm", font=info_font)
        draw.text((w // 2, info_y + 64), time_text,
                  fill=(255, 255, 255, info_alpha),
                  anchor="mm", font=info_font)

    # ================================================================
    # PHASE 3: Subscribe + Follow buttons (when subscribe voice plays)
    # ================================================================
    if elapsed >= sub_start:
        sub_elapsed = elapsed - sub_start
        btn_font = _get_font(42, bold=True)
        btn_y = int(h * 0.72)

        # Pop-in scale for buttons
        if sub_elapsed < 0.4:
            btn_scale = sub_elapsed / 0.4
            btn_scale = 1.0 + 0.2 * math.sin(btn_scale * math.pi)
        else:
            btn_scale = 1.0

        # Pulsing glow effect
        pulse = 0.5 + 0.5 * math.sin(sub_elapsed * 4.0)
        glow_expand = int(6 * pulse)

        # --- SUBSCRIBE button (red, left of center) ---
        sub_text = "SUBSCRIBE"
        sub_w = btn_font.getlength(sub_text)
        sub_btn_w = int((sub_w + 60) * btn_scale)
        sub_btn_h = int(60 * btn_scale)
        sub_cx = w // 2 - 140
        sub_x1 = sub_cx - sub_btn_w // 2
        sub_y1 = btn_y - sub_btn_h // 2
        sub_x2 = sub_cx + sub_btn_w // 2
        sub_y2 = btn_y + sub_btn_h // 2

        btn_overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        bd = ImageDraw.Draw(btn_overlay)
        # Glow behind button
        glow_alpha = int(80 * pulse)
        bd.rounded_rectangle(
            [sub_x1 - glow_expand, sub_y1 - glow_expand,
             sub_x2 + glow_expand, sub_y2 + glow_expand],
            radius=sub_btn_h // 2 + glow_expand,
            fill=(255, 50, 50, glow_alpha))
        # Button body
        bd.rounded_rectangle(
            [sub_x1, sub_y1, sub_x2, sub_y2],
            radius=sub_btn_h // 2, fill=(220, 20, 20))
        # Button text
        bd.text((sub_cx, btn_y), sub_text,
                fill=(255, 255, 255), anchor="mm", font=btn_font)

        # --- FOLLOW button (blue, right of center) ---
        fol_text = "FOLLOW"
        fol_w = btn_font.getlength(fol_text)
        fol_btn_w = int((fol_w + 60) * btn_scale)
        fol_btn_h = int(60 * btn_scale)
        fol_cx = w // 2 + 140
        fol_x1 = fol_cx - fol_btn_w // 2
        fol_y1 = btn_y - fol_btn_h // 2
        fol_x2 = fol_cx + fol_btn_w // 2
        fol_y2 = btn_y + fol_btn_h // 2

        # Glow behind button
        bd.rounded_rectangle(
            [fol_x1 - glow_expand, fol_y1 - glow_expand,
             fol_x2 + glow_expand, fol_y2 + glow_expand],
            radius=fol_btn_h // 2 + glow_expand,
            fill=(50, 100, 255, glow_alpha))
        # Button body
        bd.rounded_rectangle(
            [fol_x1, fol_y1, fol_x2, fol_y2],
            radius=fol_btn_h // 2, fill=(30, 80, 220))
        # Button text
        bd.text((fol_cx, btn_y), fol_text,
                fill=(255, 255, 255), anchor="mm", font=btn_font)

        frame = Image.alpha_composite(frame, btn_overlay)

    # --- Word-by-word subtitle (intro voice, then subscribe voice) ---
    if narr and narr.intro_text and narr.intro_duration > 0:
        frame = _render_subtitle(
            frame, narr.intro_text, t,
            clip_start=0.3,
            clip_duration=narr.intro_duration,
            y_pos=0.88)
    if narr and narr.subscribe_text and narr.subscribe_duration > 0:
        frame = _render_subtitle(
            frame, narr.subscribe_text, t,
            clip_start=sub_start,
            clip_duration=narr.subscribe_duration,
            y_pos=0.88)

    return np.array(frame.convert("RGB"))


# Section card background images (pre-rendered with baked-in text)
_SECTION_BG_DIR = config.ASSETS_DIR / "backgrounds" / "section"
_section_bg_cache: dict[str, Image.Image] = {}
_section_halves_cache: dict[str, tuple] = {}


def _get_section_bg(difficulty: str, w: int, h: int) -> Image.Image:
    """# Load and cache the section card background for a difficulty."""
    key = difficulty.upper()
    if key in _section_bg_cache:
        return _section_bg_cache[key]
    filename = {"EASY": "easy.png", "MEDIUM": "medium.png",
                "HARD": "hard.png"}.get(key)
    if not filename:
        return None
    path = _SECTION_BG_DIR / filename
    if not path.exists():
        return None
    bg = _load_scene_bg({"file": f"section/{filename}"}, w, h)
    _section_bg_cache[key] = bg
    # Pre-split halves for the left/right slide animation
    if bg:
        half_w = w // 2
        _section_halves_cache[key] = (
            bg.crop((0, 0, half_w, h)),
            bg.crop((half_w, 0, w, h)),
        )
    return bg


def _render_section_card(t: float, ctx: EmojiQuizContext,
                          event: dict) -> np.ndarray:
    """# Difficulty section card with split transition from left + right."""
    w, h = ctx.width, ctx.height
    difficulty = event.get("difficulty", "EASY")
    elapsed = t - event["start"]

    # Use custom background (text already baked in)
    bg = _get_section_bg(difficulty, w, h)
    if bg is None:
        bg = _render_bg(w, h, t, ctx.category)

    # --- Split transition: left half from left, right half from right (1s) ---
    trans_dur = 1.0
    key = difficulty.upper()
    if elapsed < trans_dur and key in _section_halves_cache:
        progress = elapsed / trans_dur
        ease = 1.0 - (1.0 - progress) ** 3
        half_w = w // 2
        left_half, right_half = _section_halves_cache[key]
        left_offset = int(half_w * (1.0 - ease))
        right_offset = int(half_w * (1.0 - ease))

        frame = Image.new("RGBA", (w, h), (0, 0, 0, 255))
        if left_offset > 0:
            visible = left_half.crop((left_offset, 0, half_w, h))
            frame.paste(visible, (0, 0))
        else:
            frame.paste(left_half, (0, 0))
        frame.paste(right_half, (half_w + right_offset, 0))
    else:
        frame = bg.copy()

    # --- Subtitle for section voiceover ---
    narr = ctx.narration_pack
    if narr and difficulty in narr.section_texts:
        sec_dur = narr.section_durations.get(difficulty, 0)
        if sec_dur > 0:
            frame = _render_subtitle(
                frame, narr.section_texts[difficulty], t,
                clip_start=event["start"] + 0.1,
                clip_duration=sec_dur,
                y_pos=0.88)

    # --- Logo watermark in top-right corner ---
    frame = _stamp_logo(frame)

    return np.array(frame.convert("RGB"))


# --- Cached outro logo (loaded once) ---
_outro_logo_cache = None


def _get_outro_logo(max_size: int = 350) -> Image.Image:
    """
    # Load and cache the Leo Quizz logo for the outro screen.
    # Returns RGBA image resized to fit within max_size px.
    """
    global _outro_logo_cache
    if _outro_logo_cache is not None:
        return _outro_logo_cache.copy()

    if config.LOGO_IMAGE.exists():
        img = Image.open(config.LOGO_IMAGE).convert("RGBA")
        # Fit within max_size while keeping aspect ratio
        ratio = min(max_size / img.width, max_size / img.height)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        _outro_logo_cache = img
        return img.copy()
    return None


# --- Cached small logo for persistent top-right watermark ---
_logo_watermark_cache = None


def _stamp_logo(frame: Image.Image) -> Image.Image:
    """
    # Stamp Leo Quizz logo in the top-right corner of every scene.
    # Uses its own separate cache so it doesn't affect the outro's big logo.
    """
    global _logo_watermark_cache
    if _logo_watermark_cache is None:
        if config.LOGO_IMAGE.exists():
            img = Image.open(config.LOGO_IMAGE).convert("RGBA")
            logo_size = 70
            ratio = min(logo_size / img.width, logo_size / img.height)
            img = img.resize((int(img.width * ratio),
                              int(img.height * ratio)), Image.LANCZOS)
            _logo_watermark_cache = img
        else:
            return frame
    logo = _logo_watermark_cache.copy()
    w = frame.size[0]
    lx = w - logo.width - 20
    ly = 16
    frame.paste(logo, (lx, ly), logo)
    return frame


def _render_outro(t: float, ctx: EmojiQuizContext,
                   score: int) -> np.ndarray:
    """
    # Outro: custom "Good Job!" background with split transition entrance.
    # First 1s: top half slides down, bottom half slides up (same as round transitions).
    # After that: static background with confetti + subtitle.
    # Background already has Leo Quizz logo, "Good Job!", subscribe + like buttons.
    """
    w, h = ctx.width, ctx.height
    elapsed = t - ctx.timeline[-1]["start"]

    # Use custom outro background (already has all branding baked in)
    if _outro_bg_cache is not None:
        outro_img = _outro_bg_cache
    else:
        outro_img = _render_bg(w, h, t, ctx.category)

    # --- Split transition entrance for first 1s ---
    trans_dur = 1.0
    if elapsed < trans_dur and _outro_top_cache is not None:
        progress = elapsed / trans_dur
        ease = 1.0 - (1.0 - progress) ** 3
        half_h = h // 2
        top_offset = int(half_h * (1.0 - ease))
        bottom_offset = int(half_h * (1.0 - ease))

        frame = Image.new("RGBA", (w, h), (0, 0, 0, 255))
        # Crop the visible portion when offset is negative
        if top_offset > 0:
            visible = _outro_top_cache.crop((0, top_offset, w, half_h))
            frame.paste(visible, (0, 0))
        else:
            frame.paste(_outro_top_cache, (0, 0))
        frame.paste(_outro_bot_cache, (0, half_h + bottom_offset))
    else:
        frame = outro_img.copy()

    # Confetti (after transition completes)
    if elapsed >= trans_dur:
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)

    # --- Outro voiceover subtitle ---
    narr = ctx.narration_pack
    if narr and narr.outro_text and narr.outro_duration > 0:
        frame = _render_subtitle(
            frame, narr.outro_text, t,
            clip_start=ctx.timeline[-1]["start"] + 0.3,
            clip_duration=narr.outro_duration,
            y_pos=0.88)

    return np.array(frame.convert("RGB"))


# ============================================================
# MAIN FRAME RENDERER
# ============================================================

def render_emoji_frame(t: float, ctx: EmojiQuizContext) -> np.ndarray:
    """
    # Render a single frame at time t.
    # Returns numpy RGB array for ffmpeg pipe.
    """
    # --- Find current timeline event ---
    event = None
    for ev in ctx.timeline:
        if ev["start"] <= t < ev["end"]:
            event = ev
            break
    if event is None:
        event = ctx.timeline[-1] if ctx.timeline else {
            "phase": "intro", "start": 0, "end": 1}

    phase = event["phase"]
    round_idx = event.get("round", -1)

    # --- Calculate score ---
    score = min(round_idx + 1, ctx.total_rounds) if round_idx >= 0 else 0
    if phase in ("question", "transition"):
        score = round_idx

    # --- Special screens ---
    if phase == "intro":
        return _render_intro_frame(t, ctx)
    if phase == "section_card":
        return _render_section_card(t, ctx, event)
    if phase == "outro":
        return _render_outro(t, ctx, ctx.total_rounds)

    # --- Regular quiz round ---
    w, h = ctx.width, ctx.height

    # Find round start time
    round_start = event["start"]
    for ev in ctx.timeline:
        if ev.get("round") == round_idx and ev["phase"] == "question":
            round_start = ev["start"]
            break

    # Get round data
    if 0 <= round_idx < len(ctx.rounds):
        rnd = ctx.rounds[round_idx]
    else:
        rnd = EmojiQuizRound(answer="?", emoji_clues=["❓", "❓"],
                              fun_fact="", difficulty="easy")

    narr = ctx.narration_pack

    # --- QUESTION phase: clue background + emoji stickers ---
    if phase == "question":
        # Use the custom clue background (whiteboard/rock)
        clue_bg, _ = _get_clue_bg()
        if clue_bg is not None:
            frame = clue_bg.copy()
        else:
            frame = _render_bg(w, h, t, ctx.category)
        frame = _render_emoji_clues(frame, rnd.emoji_clues, t, round_start)
        frame = _render_timer_bar(frame, t, round_start)
        # Round counter badge (no full title banner — BG has branding)
        draw = ImageDraw.Draw(frame)
        badge_font = _get_font(30, bold=True)
        badge_text = f"Round {round_idx + 1}/{ctx.total_rounds}"
        badge_x = 40
        badge_y = h - 70
        draw.rounded_rectangle(
            [badge_x - 10, badge_y - 8, badge_x + 200, badge_y + 38],
            radius=20, fill=(0, 0, 0, 150))
        draw.text((badge_x + 95, badge_y + 15), badge_text,
                   fill=(255, 255, 255), anchor="mm", font=badge_font)
        if (narr and round_idx < len(narr.question_texts)
                and narr.question_durations[round_idx] > 0):
            frame = _render_subtitle(
                frame, narr.question_texts[round_idx], t,
                clip_start=round_start + 0.1,
                clip_duration=narr.question_durations[round_idx],
                y_pos=0.90)

    # --- REVEAL phase: reveal background + answer photo ---
    elif phase == "reveal":
        reveal_bg, _ = _get_reveal_bg()
        if reveal_bg is not None:
            frame = reveal_bg.copy()
        else:
            frame = _render_bg(w, h, t, ctx.category)
        reveal_start = event["start"]
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)
        ans_img = ctx.answer_images.get(round_idx)
        frame = _render_answer_reveal(frame, rnd.answer, t, reveal_start,
                                       answer_img=ans_img)
        if (narr and round_idx < len(narr.reveal_texts)
                and narr.reveal_texts[round_idx]
                and narr.reveal_durations[round_idx] > 0):
            frame = _render_subtitle(
                frame, narr.reveal_texts[round_idx], t,
                clip_start=reveal_start + 0.3,
                clip_duration=narr.reveal_durations[round_idx],
                y_pos=0.92)

    # --- FACT phase: reveal background + answer + fun fact ---
    elif phase == "fact":
        reveal_bg, _ = _get_reveal_bg()
        if reveal_bg is not None:
            frame = reveal_bg.copy()
        else:
            frame = _render_bg(w, h, t, ctx.category)
        # Reveal start is always EMOJI_REVEAL_START before fact start
        reveal_start = event["start"] - (config.EMOJI_FACT_START - config.EMOJI_REVEAL_START)
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)
        if reveal_start:
            ans_img = ctx.answer_images.get(round_idx)
            frame = _render_answer_reveal(frame, rnd.answer, t, reveal_start,
                                           answer_img=ans_img)
        frame = _render_fun_fact(frame, rnd.fun_fact, t, event["start"])

    elif phase == "transition":
        # Split transition: top half slides down from above,
        # bottom half slides up from below — they meet in the middle
        trans_elapsed = t - event["start"]
        trans_dur = event["end"] - event["start"]
        progress = min(1.0, trans_elapsed / trans_dur) if trans_dur > 0 else 1.0

        if _transition_top_cache is not None:
            ease = 1.0 - (1.0 - progress) ** 3
            half_h = h // 2
            top_offset = int(half_h * (1.0 - ease))
            bottom_offset = int(half_h * (1.0 - ease))

            frame = Image.new("RGBA", (w, h), (0, 0, 0, 255))
            if top_offset > 0:
                visible = _transition_top_cache.crop((0, top_offset, w, half_h))
                frame.paste(visible, (0, 0))
            else:
                frame.paste(_transition_top_cache, (0, 0))
            frame.paste(_transition_bot_cache, (0, half_h + bottom_offset))
        else:
            # Fallback: darken the reveal scene
            reveal_bg, _ = _get_reveal_bg()
            if reveal_bg is not None:
                frame = reveal_bg.copy()
            else:
                frame = _render_bg(w, h, t, ctx.category)
            if trans_dur > 0:
                darkness = int(100 * progress)
                dark = Image.new("RGBA", (w, h), (0, 0, 0, darkness))
                frame = Image.alpha_composite(frame, dark)

    # --- Score bar (no logo — backgrounds have branding) ---
    frame = _render_score_bar(frame, score, ctx.total_rounds)

    return np.array(frame.convert("RGB"))


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def assemble_emoji_quiz(emoji_pack: EmojiQuizPack, audio_path: Path,
                         output_path: Path,
                         narration_pack=None,
                         answer_images: dict = None) -> Path:
    """
    # Assemble a complete emoji quiz video.
    # Pre-downloads all Twemoji PNGs, then renders frame-by-frame.
    # answer_images: {round_idx: PIL.Image} for reveal screen photos.
    # narration_pack: EmojiNarrationPack with durations for dynamic
    #   intro length and script texts for word-by-word subtitles.
    """
    w, h = config.LONGFORM_SIZE
    num_rounds = len(emoji_pack.rounds)

    # --- Reset cached intro layout for fresh render ---
    global _intro_emoji_layout
    _intro_emoji_layout = None

    # --- Load and resize custom scene backgrounds ---
    _init_scene_backgrounds(w, h)

    # --- Pre-download all emoji images ---
    all_emoji = []
    for rnd in emoji_pack.rounds:
        all_emoji.extend(rnd.emoji_clues)
    preload_emoji_set(all_emoji, size=250)

    # --- Load mascot images ---
    mascot_images = {}
    for pose_name, pose_path in config.MASCOT_POSES.items():
        if pose_path.exists():
            img = Image.open(pose_path).convert("RGBA")
            arr = np.array(img)
            white_mask = ((arr[:, :, 0] > 230) &
                          (arr[:, :, 1] > 230) &
                          (arr[:, :, 2] > 230))
            arr[white_mask, 3] = 0
            mascot_images[pose_name] = Image.fromarray(arr)

    # --- Calculate dynamic intro duration from narration ---
    # Intro voiceover must finish BEFORE rounds start (no overlap)
    intro_voice_dur = 0.0
    if narration_pack:
        intro_voice_dur = (narration_pack.intro_duration +
                           narration_pack.subscribe_duration)
    print(f"[EMOJI] Intro voice duration: {intro_voice_dur:.1f}s")

    # --- Build timeline with dynamic intro ---
    timeline = build_emoji_timeline(num_rounds,
                                     intro_duration=intro_voice_dur)
    total_duration = timeline[-1]["end"]

    # --- Sparkles ---
    sparkles = ParticleSystem(w, h, count=18, seed=42)

    # --- Confetti on reveals ---
    confetti_bursts = []
    for event in timeline:
        if event["phase"] == "reveal":
            confetti_bursts.append(ConfettiBurst(
                center_x=w // 2, center_y=int(h * 0.50),
                trigger_time=event["start"], count=45,
                seed=int(event["start"] * 100)))
    outro_events = [e for e in timeline if e["phase"] == "outro"]
    if outro_events:
        confetti_bursts.append(ConfettiBurst(
            center_x=w // 2, center_y=int(h * 0.40),
            trigger_time=outro_events[0]["start"] + 0.3,
            count=70, seed=999))

    # --- Context (includes narration pack for subtitle rendering) ---
    ctx = EmojiQuizContext(
        width=w, height=h, category=emoji_pack.category,
        rounds=emoji_pack.rounds, total_rounds=num_rounds,
        mascot_images=mascot_images, timeline=timeline,
        confetti_bursts=confetti_bursts, sparkles=sparkles,
        narration_pack=narration_pack,
        answer_images=answer_images or {})

    print(f"[EMOJI] Rendering {num_rounds} rounds, {total_duration:.0f}s total")
    print(f"[EMOJI] Twemoji PNGs, sparkles, confetti, shake, timer, glow")

    # --- Pipe to ffmpeg ---
    from ffmpeg_pipe import pipe_frames_to_video

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = pipe_frames_to_video(
        render_fn=lambda t: render_emoji_frame(t, ctx),
        duration=total_duration,
        fps=config.FPS,
        width=w, height=h,
        audio_path=str(audio_path) if audio_path and audio_path.exists() else None,
        output_path=str(output_path),
        bitrate=config.LONGFORM_BITRATE,
        preset="fast",
        audio_bitrate=config.AUDIO_BITRATE,
    )

    print(f"[EMOJI] Video saved: {output_path}")
    return output_path if result else None
