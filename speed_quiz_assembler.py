# speed_quiz_assembler.py
# ============================================================
# Frame-by-frame 16:9 landscape renderer for speed quiz format.
# PIL pushed to MAXIMUM quality — every trick in the book:
#
# Per-round effects:
# - Photo slides in from right (back_out ease)
# - Ken Burns slow zoom on photo during question
# - Pulsing glow ring behind photo card
# - Visual countdown 3-2-1 overlay (big numbers)
# - "?" mystery overlay fading as timer runs
# - Screen shake on answer reveal
# - Glow text on answer (neon bloom)
# - Green checkmark pop-in beside answer
# - Score counter ticking up
# - Confetti burst with ribbon shapes
# - Photo + elements slide out left during transition
# - Diagonal color wipe to next round's background
#
# Background effects (every frame):
# - Bright solid color rotating per round
# - Animated drifting pattern overlay per difficulty
# - Floating sparkle particles (gold/white)
# - Category-themed decorations (shapes)
# - Thin progress bar at very bottom
#
# Special screens:
# - Intro: staggered text pop-in + glow numbers + vignette
# - Subscribe: elastic button + dark overlay
# - Section card: glow text + radial burst lines + screen shake
# - Outro: glow celebration + confetti + vignette
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
    ConfettiBurst, ScreenShake, KenBurnsZoom, GlowRing,
    ThemedDecorations, apply_vignette, render_glow_text,
)
from frame_composer import _get_font, hex_to_rgb
from quiz_generator import QuizRound, QuizPack
from narration import RoundAudio


@dataclass
class SpeedQuizContext:
    width: int
    height: int
    category: str
    rounds: list[QuizRound]
    photo_paths: list[Path]
    mascot_images: dict
    total_rounds: int
    timeline: list[dict] = field(default_factory=list)
    confetti_bursts: list[ConfettiBurst] = field(default_factory=list)
    round_audios: list[RoundAudio] = field(default_factory=list)
    sparkles: ParticleSystem = None
    decorations: ThemedDecorations = None
    _photo_cache: dict = field(default_factory=dict)
    _mascot_cache: dict = field(default_factory=dict)
    # Leo's narration script — used for speech bubbles so Leo "speaks"
    narration_script: dict = field(default_factory=dict)
    # Per-round reveal text ("It's a Lion!") for speech bubbles
    round_reveal_texts: list[str] = field(default_factory=list)


# ============================================================
# MASCOT ANIMATION SYSTEM
# ============================================================

def _remove_white_bg(img: Image.Image, threshold: int = 215) -> Image.Image:
    """
    # Remove white background from mascot PNGs.
    # Uses radial mask to fade out scattered confetti at image edges,
    # preventing rectangular haze artifacts when composited on backgrounds.
    """
    data = np.array(img)
    if data.shape[2] < 4:
        return img
    h_img, w_img = data.shape[:2]

    # Remove white and near-white pixels
    white_mask = ((data[:, :, 0] > threshold) &
                  (data[:, :, 1] > threshold) &
                  (data[:, :, 2] > threshold))
    data[white_mask, 3] = 0

    # Remove low-saturation bright pixels (off-white edges)
    r = data[:, :, 0].astype(float)
    g = data[:, :, 1].astype(float)
    b = data[:, :, 2].astype(float)
    max_rgb = np.maximum(np.maximum(r, g), b)
    min_rgb = np.minimum(np.minimum(r, g), b)
    low_sat = (max_rgb - min_rgb < 30) & (max_rgb > 195)
    data[low_sat, 3] = 0

    # Radial mask fades out scattered confetti near image edges
    y_coords, x_coords = np.ogrid[:h_img, :w_img]
    cx, cy = w_img // 2, int(h_img * 0.48)
    dist = np.sqrt(((x_coords - cx) / (w_img * 0.38)) ** 2 +
                   ((y_coords - cy) / (h_img * 0.42)) ** 2)
    radial = np.clip(1.0 - (dist - 0.85) / 0.25, 0.0, 1.0)
    data[:, :, 3] = (data[:, :, 3].astype(float) * radial).astype(np.uint8)

    result = Image.fromarray(data)
    alpha = result.split()[3]
    alpha = alpha.filter(ImageFilter.GaussianBlur(radius=0.8))
    alpha_arr = np.array(alpha)
    alpha_arr[alpha_arr < 60] = 0
    result.putalpha(Image.fromarray(alpha_arr))
    return result


def _get_mascot_pose(phase: str, difficulty: str = "EASY",
                     round_idx: int = 0) -> str:
    """
    # Select which mascot pose to show based on current video phase.
    # Maps each phase to the pose that matches the emotional beat.
    """
    if phase in ("intro", "subscribe"):
        return "waving"
    if phase == "section_card":
        return "excited"
    if phase == "question":
        return "thinking"
    if phase in ("reveal", "fact"):
        # Surprised face for hard/impossible difficulty, excited otherwise
        if difficulty in ("HARD", "IMPOSSIBLE"):
            return "surprised"
        return "excited"
    if phase == "outro":
        return "excited"
    return "thinking"


def _get_speaking_state(t: float, phase: str, event_start: float) -> tuple:
    """
    # Detect if Leo is speaking and how far through the phrase he is.
    # Returns (is_speaking: bool, progress: float 0-1, text_key: str).
    # Progress is used for natural lip sync — ramps up, sustains, ramps down.
    # Based on known voice timing from speed_quiz_audio.py.
    """
    elapsed = t - event_start
    # Each phase has (voice_start_offset, voice_duration, script_key)
    windows = {
        "intro": (0.8, 3.2, "intro"),
        "subscribe": (0.5, 2.0, "subscribe"),
        "section_card": (0.4, 2.0, "section"),
        "reveal": (0.2, 1.2, "reveal"),
        "outro": (1.0, 3.0, "outro"),
    }
    if phase not in windows:
        return False, 0.0, ""

    voice_start, voice_dur, key = windows[phase]
    voice_elapsed = elapsed - voice_start
    if voice_elapsed < 0 or voice_elapsed > voice_dur:
        return False, 0.0, key

    progress = voice_elapsed / voice_dur
    return True, progress, key


def _get_speech_text(ctx: SpeedQuizContext, phase: str,
                     difficulty: str, round_idx: int) -> str:
    """
    # Get the text Leo is currently saying for the speech bubble.
    # Pulls from the narration script that Gemini generated.
    """
    script = ctx.narration_script
    if not script:
        return ""
    if phase == "intro":
        return script.get("intro", "")
    if phase == "subscribe":
        return script.get("subscribe", "")
    if phase == "section_card":
        sections = script.get("sections", {})
        return sections.get(difficulty, "")
    if phase in ("reveal", "fact"):
        if round_idx < len(ctx.round_reveal_texts):
            return ctx.round_reveal_texts[round_idx]
        return ""
    if phase == "outro":
        return script.get("outro", "")
    return ""


def _render_speech_bubble(frame: Image.Image, text: str,
                          mascot_cx: int, mascot_top_y: int,
                          progress: float, t: float) -> Image.Image:
    """
    # Draw a speech bubble above Leo with the text he's currently saying.
    # Animated: pops in with elastic ease, fades out at the end.
    # Tail points down toward Leo's mouth.
    # Text wraps to fit the bubble width.
    """
    if not text:
        return frame
    w, h = frame.size

    # Pop-in at start, fade-out at end of speech
    if progress < 0.1:
        opacity = progress / 0.1
        bubble_scale = 0.5 + 0.5 * (progress / 0.1)
    elif progress > 0.85:
        opacity = (1.0 - progress) / 0.15
        bubble_scale = 1.0
    else:
        opacity = 1.0
        bubble_scale = 1.0

    if opacity < 0.05:
        return frame

    # Speech bubble font
    font = _get_font(22, bold=True)

    # Word-wrap text to fit bubble (max ~22 chars per line for readability)
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        if font.getlength(test) > 280:
            if current_line:
                lines.append(current_line)
            current_line = word
        else:
            current_line = test
    if current_line:
        lines.append(current_line)

    if not lines:
        return frame

    # Calculate bubble dimensions
    line_height = 28
    padding_x, padding_y = 20, 14
    max_line_w = max(font.getlength(line) for line in lines)
    bubble_w = int(max_line_w + padding_x * 2)
    bubble_h = int(len(lines) * line_height + padding_y * 2)

    # Apply scale for pop-in
    bubble_w = int(bubble_w * bubble_scale)
    bubble_h = int(bubble_h * bubble_scale)

    # Position: above Leo, shifted left so it doesn't go off-screen
    bubble_cx = min(mascot_cx, w - bubble_w // 2 - 10)
    bubble_cx = max(bubble_cx, bubble_w // 2 + 10)
    bubble_top = mascot_top_y - bubble_h - 25

    # Clamp to screen
    bubble_top = max(8, bubble_top)

    # Draw on overlay for alpha compositing
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    bx1 = bubble_cx - bubble_w // 2
    by1 = bubble_top
    bx2 = bubble_cx + bubble_w // 2
    by2 = bubble_top + bubble_h

    # Bubble shadow
    alpha_bg = int(180 * opacity)
    draw.rounded_rectangle(
        [bx1 + 3, by1 + 3, bx2 + 3, by2 + 3],
        radius=16, fill=(0, 0, 0, int(40 * opacity)))

    # Bubble body (white with slight transparency)
    draw.rounded_rectangle(
        [bx1, by1, bx2, by2],
        radius=16, fill=(255, 255, 255, alpha_bg))
    draw.rounded_rectangle(
        [bx1, by1, bx2, by2],
        radius=16, outline=(255, 200, 50, alpha_bg), width=3)

    # Tail triangle pointing down to Leo
    tail_cx = min(max(mascot_cx, bx1 + 20), bx2 - 20)
    tail_points = [
        (tail_cx - 12, by2 - 2),
        (tail_cx + 12, by2 - 2),
        (tail_cx + 5, by2 + 18),
    ]
    draw.polygon(tail_points, fill=(255, 255, 255, alpha_bg))
    # Tail outline (match bubble border)
    draw.line([tail_points[1], tail_points[2]], fill=(255, 200, 50, alpha_bg), width=3)
    draw.line([tail_points[2], tail_points[0]], fill=(255, 200, 50, alpha_bg), width=3)

    # Text inside bubble (scaled font for pop-in)
    if bubble_scale > 0.7:
        text_font = _get_font(int(22 * min(1.0, bubble_scale)), bold=True)
        text_alpha = int(255 * opacity)
        for i, line in enumerate(lines):
            ty = by1 + padding_y + i * int(line_height * bubble_scale)
            draw.text((bubble_cx, ty + int(line_height * bubble_scale) // 2),
                      line, fill=(50, 50, 60, text_alpha),
                      anchor="mm", font=text_font)

    frame = Image.alpha_composite(frame, overlay)
    return frame


def _natural_lip_sync(t: float, speaking: bool, progress: float) -> dict:
    """
    # Generate natural lip sync animation values.
    # Instead of a simple bounce, models realistic jaw movement:
    # - Vowels open wide (low frequency, high amplitude)
    # - Consonants close quickly (high frequency, low amplitude)
    # - Natural rhythm varies — not a perfect sine wave
    # Returns dict with jaw_offset, scale_pulse, and head_nod values.
    """
    if not speaking:
        return {"jaw_y": 0.0, "scale": 0.0, "nod": 0.0}

    # Layer 1: Primary jaw movement — irregular vowel-consonant rhythm
    # Mix of frequencies simulates natural speech cadence
    jaw = (math.sin(t * 12.0 * math.pi) * 0.4 +    # ~6 Hz primary
           math.sin(t * 18.5 * math.pi) * 0.3 +    # ~9 Hz consonants
           math.sin(t * 7.3 * math.pi) * 0.2 +     # ~3.5 Hz vowel stretch
           math.sin(t * 25.0 * math.pi) * 0.1)     # ~12 Hz micro-detail

    # Clamp to 0-1 range (jaw only opens, doesn't go negative)
    jaw = max(0.0, jaw)

    # Layer 2: Emphasis pulse — bigger movements on stressed syllables
    # Slower wave that modulates amplitude (~2 Hz = natural word stress)
    emphasis = 0.6 + 0.4 * math.sin(t * 4.0 * math.pi)
    jaw *= emphasis

    # Layer 3: Ramp envelope — softer at start and end of phrase
    if progress < 0.08:
        jaw *= progress / 0.08
    elif progress > 0.9:
        jaw *= (1.0 - progress) / 0.1

    # Scale pulse: mascot slightly grows on emphasized syllables
    scale_pulse = jaw * 0.03

    # Head nod: subtle forward lean on emphasized words
    nod = math.sin(t * 3.5 * math.pi) * 2.0 * emphasis

    return {"jaw_y": jaw * 6.0, "scale": scale_pulse, "nod": nod}


def _render_mascot_animated(frame: Image.Image, ctx: SpeedQuizContext,
                            t: float, phase: str, difficulty: str = "EASY",
                            round_idx: int = 0, event_start: float = 0.0,
                            reveal_time: float = 0.0,
                            position: str = "right") -> Image.Image:
    """
    # Full mascot rendering — Leo as the speaking host of the quiz.
    # Applies to EVERY frame in the video.
    #
    # Animation layers:
    # 1. Idle bob — gentle float (always on)
    # 2. Pose-specific tilt — wave, wiggle, shake, or sway
    # 3. Natural lip sync — multi-frequency jaw simulation during voice
    # 4. Reveal pop — elastic scale burst on answer
    # 5. Breathing pulse — subtle scale oscillation
    # 6. Speech bubble — shows what Leo is saying above his head
    """
    pose = _get_mascot_pose(phase, difficulty, round_idx)
    mascot_img = ctx.mascot_images.get(pose)
    if mascot_img is None:
        for fallback in ("excited", "waving", "thinking", "surprised"):
            if fallback in ctx.mascot_images:
                mascot_img = ctx.mascot_images[fallback]
                break
    if mascot_img is None:
        return frame

    w, h = frame.size

    # --- Base size ---
    if position == "center":
        mh = int(h * 0.30)
    else:
        mh = int(h * 0.28)
    mw = int(mascot_img.width * (mh / mascot_img.height))

    # --- 1. Idle bob ---
    bob_y = math.sin(t * 2.5) * 5.0

    # --- 2. Pose-specific tilt ---
    rotation = 0.0
    if pose == "waving":
        rotation = math.sin(t * 5.0 * math.pi) * 8.0
    elif pose == "excited":
        rotation = math.sin(t * 6.0 * math.pi) * 4.0
    elif pose == "surprised":
        rotation = math.sin(t * 8.0 * math.pi) * 3.0
    else:
        rotation = math.sin(t * 2.0 * math.pi) * 2.0

    # --- 3. Natural lip sync ---
    speaking, speak_progress, _ = _get_speaking_state(t, phase, event_start)
    lip = _natural_lip_sync(t, speaking, speak_progress)

    # --- 4. Reveal pop ---
    scale = 1.0
    if phase in ("reveal", "fact") and reveal_time > 0:
        re = t - reveal_time
        if 0 < re < 0.6:
            scale = 1.0 + 0.22 * compute_scale(re, 0.0, 0.6, "elastic_out")

    # --- 5. Breathing pulse + lip sync scale ---
    scale += math.sin(t * 1.5 * math.pi) * 0.015
    scale += lip["scale"]

    # --- Apply scale ---
    sw = max(1, int(mw * scale))
    sh = max(1, int(mh * scale))
    mr = mascot_img.resize((sw, sh), Image.LANCZOS)

    # --- Apply rotation + head nod ---
    total_rotation = rotation + lip["nod"]
    if abs(total_rotation) > 0.3:
        mr = mr.rotate(total_rotation, resample=Image.BICUBIC, expand=True,
                       fillcolor=(0, 0, 0, 0))

    # --- Position ---
    if position == "center":
        mx = w // 2
        my = int(h * 0.78)
    elif position == "left":
        mx = int(w * 0.15)
        my = int(h * 0.60)
    else:
        mx = int(w * 0.88)
        my = int(h * 0.55)

    # Apply animation offsets (bob + jaw movement)
    my += int(bob_y + lip["jaw_y"])

    # --- Paste mascot ---
    px = mx - mr.width // 2
    py = my - mr.height // 2
    if mr.mode == "RGBA":
        frame.paste(mr, (px, py), mr)
    else:
        frame.paste(mr, (px, py))

    # --- 6. Speech bubble above Leo ---
    if speaking:
        speech_text = _get_speech_text(ctx, phase, difficulty, round_idx)
        if speech_text:
            mascot_top = py
            frame = _render_speech_bubble(
                frame, speech_text, mx, mascot_top,
                speak_progress, t)

    return frame


# ============================================================
# TIMELINE
# ============================================================
def build_speed_timeline(num_rounds: int) -> list[dict]:
    timeline = []
    t = 0.0

    timeline.append({
        "phase": "intro", "start": t,
        "end": t + config.SPEED_INTRO_DURATION, "round": -1,
    })
    t += config.SPEED_INTRO_DURATION

    timeline.append({
        "phase": "subscribe", "start": t,
        "end": t + config.SPEED_SUBSCRIBE_DURATION, "round": -1,
    })
    t += config.SPEED_SUBSCRIBE_DURATION

    for section_idx, difficulty in enumerate(config.SPEED_DIFFICULTIES):
        timeline.append({
            "phase": "section_card", "start": t,
            "end": t + config.SPEED_SECTION_CARD_DURATION,
            "round": -1, "difficulty": difficulty,
        })
        t += config.SPEED_SECTION_CARD_DURATION

        start_round = section_idx * config.SPEED_ROUNDS_PER_DIFFICULTY
        end_round = min(start_round + config.SPEED_ROUNDS_PER_DIFFICULTY, num_rounds)

        for round_idx in range(start_round, end_round):
            rs = t
            timeline.append({
                "phase": "question", "start": rs + config.SPEED_PHOTO_START,
                "end": rs + config.SPEED_REVEAL_START,
                "round": round_idx, "difficulty": difficulty,
            })
            timeline.append({
                "phase": "reveal", "start": rs + config.SPEED_REVEAL_START,
                "end": rs + config.SPEED_FACT_START,
                "round": round_idx, "difficulty": difficulty,
            })
            timeline.append({
                "phase": "fact", "start": rs + config.SPEED_FACT_START,
                "end": rs + config.SPEED_ROUND_DURATION,
                "round": round_idx, "difficulty": difficulty,
            })
            t += config.SPEED_ROUND_DURATION

    timeline.append({
        "phase": "outro", "start": t,
        "end": t + config.SPEED_OUTRO_DURATION, "round": -1,
    })
    return timeline


def _get_event(t: float, timeline: list[dict]) -> dict:
    for event in timeline:
        if event["start"] <= t < event["end"]:
            return event
    return timeline[-1] if timeline else {"phase": "outro", "start": 0, "end": 0, "round": -1}


# ============================================================
# BACKGROUND
# ============================================================
def _render_background(w: int, h: int, round_idx: int,
                       difficulty: str, t: float,
                       ctx: SpeedQuizContext) -> Image.Image:
    color_idx = round_idx % len(config.SPEED_BG_COLORS)
    bg_color = config.SPEED_BG_COLORS[color_idx]

    img = Image.new("RGBA", (w, h), bg_color + (255,))
    draw = ImageDraw.Draw(img)

    pattern_type = config.SPEED_PATTERNS.get(difficulty, "stars")
    pat_color = tuple(min(255, c + 30) for c in bg_color) + (40,)
    _draw_pattern(draw, w, h, pattern_type, pat_color, round_idx, t)

    if ctx.decorations:
        img = ctx.decorations.render(img, t)

    return img


def _draw_pattern(draw, w, h, pattern_type, color, seed=0, t=0.0):
    rng = random.Random(seed + 42)
    drift_x = int(t * 8) % w
    drift_y = int(t * 5) % h

    if pattern_type == "clouds":
        for _ in range(18):
            cx = (rng.randint(0, w) + drift_x) % w
            cy = (rng.randint(0, h) + drift_y) % h
            size = rng.randint(40, 90)
            for dx, dy in [(-size//2, 0), (size//2, 0), (0, -size//3),
                           (-size//3, -size//4), (size//3, -size//4)]:
                r = size // 2
                draw.ellipse([cx+dx-r, cy+dy-r, cx+dx+r, cy+dy+r], fill=color)
    elif pattern_type == "stars":
        for _ in range(25):
            cx = (rng.randint(0, w) + drift_x) % w
            cy = (rng.randint(0, h) + drift_y) % h
            _draw_star(draw, cx, cy, rng.randint(20, 50), color)
    elif pattern_type == "question_marks":
        try:
            font = ImageFont.truetype("arial.ttf", rng.randint(30, 60))
        except OSError:
            font = ImageFont.load_default()
        for _ in range(22):
            x = (rng.randint(0, w) + drift_x) % w
            y = (rng.randint(0, h) + drift_y) % h
            draw.text((x, y), "?", fill=color, font=font, anchor="mm")
    elif pattern_type == "lightning":
        for _ in range(20):
            cx = (rng.randint(0, w) + drift_x) % w
            cy = (rng.randint(0, h) + drift_y) % h
            _draw_lightning(draw, cx, cy, rng.randint(25, 55), color)


def _draw_star(draw, cx, cy, size, color):
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        r = size if i % 2 == 0 else size * 0.4
        points.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    draw.polygon(points, fill=color)


def _draw_lightning(draw, cx, cy, size, color):
    s = size
    draw.polygon([
        (cx - s*0.15, cy - s*0.5), (cx + s*0.25, cy - s*0.1),
        (cx, cy), (cx + s*0.3, cy + s*0.5),
        (cx - s*0.05, cy + s*0.1), (cx - s*0.25, cy),
    ], fill=color)


# ============================================================
# PHOTO CARD
# ============================================================
def _render_photo_card(frame, photo_path, center_x, center_y,
                       scale=1.0, ctx=None,
                       apply_zoom=False, zoom_progress=0.0):
    cache_key = str(photo_path)
    if ctx and cache_key in ctx._photo_cache:
        photo = ctx._photo_cache[cache_key].copy()
    else:
        try:
            photo = Image.open(photo_path).convert("RGBA")
            if ctx:
                ctx._photo_cache[cache_key] = photo.copy()
        except Exception:
            return frame

    pw = int(config.SPEED_PHOTO_WIDTH * scale)
    ph = int(config.SPEED_PHOTO_HEIGHT * scale)
    pad = int(config.SPEED_CARD_PADDING * scale)
    radius = int(config.SPEED_CARD_RADIUS * scale)
    if pw <= 0 or ph <= 0:
        return frame

    photo = photo.resize((pw, ph), Image.LANCZOS)

    # Ken Burns zoom
    if apply_zoom and zoom_progress > 0:
        z = 1.0 + 0.06 * zoom_progress
        zw, zh = int(pw * z), int(ph * z)
        photo = photo.resize((zw, zh), Image.LANCZOS)
        cx2, cy2 = (zw - pw) // 2, (zh - ph) // 2
        photo = photo.crop((cx2, cy2, cx2 + pw, cy2 + ph))

    card_w, card_h = pw + pad * 2, ph + pad * 2
    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle([0, 0, card_w - 1, card_h - 1],
                         radius=radius, fill=(255, 255, 255, 248))

    # Round photo corners
    pmask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(pmask).rounded_rectangle(
        [0, 0, pw - 1, ph - 1], radius=max(1, radius - pad // 2), fill=255)
    pr = photo.convert("RGBA")
    r, g, b, a = pr.split()
    a = Image.composite(a, Image.new("L", (pw, ph), 0), pmask)
    pr = Image.merge("RGBA", (r, g, b, a))
    card.paste(pr, (pad, pad), pr)

    # Multi-layer shadow for depth
    shadow = Image.new("RGBA", (card_w + 20, card_h + 20), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([6, 6, card_w + 5, card_h + 5],
                         radius=radius, fill=(0, 0, 0, 45))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=10))
    # Second shadow layer — tighter, darker
    sd2 = ImageDraw.Draw(shadow)
    sd2.rounded_rectangle([4, 4, card_w + 3, card_h + 3],
                          radius=radius, fill=(0, 0, 0, 25))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=4))

    px = center_x - card_w // 2
    py = center_y - card_h // 2
    frame.paste(shadow, (px - 6, py - 4), shadow)
    frame.paste(card, (px, py), card)

    return frame


# ============================================================
# UI ELEMENTS
# ============================================================
def _render_round_badge(frame, round_num, t=0.0):
    draw = ImageDraw.Draw(frame)
    cx, cy = int(frame.width * 0.045), int(frame.height * 0.065)
    r = config.SPEED_BADGE_RADIUS
    pulse = 1.0 + 0.04 * math.sin(t * 3.0)
    pr = int(r * pulse)

    # Shadow behind badge
    draw.ellipse([cx - pr + 3, cy - pr + 3, cx + pr + 3, cy + pr + 3],
                 fill=(0, 0, 0, 40))
    draw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr],
                 fill=config.SPEED_BADGE_COLOR + (255,))
    draw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr],
                 outline=(255, 255, 255, 180), width=3)

    font = _get_font(config.SPEED_ROUND_NUM_FONT_SIZE, bold=True)
    draw.text((cx, cy), str(round_num), fill=(255, 255, 255),
              anchor="mm", font=font,
              stroke_width=2, stroke_fill=(0, 0, 0))
    return frame


def _render_difficulty_sidebar(frame, current_difficulty):
    draw = ImageDraw.Draw(frame)
    x = int(frame.width * 0.045)
    start_y = int(frame.height * 0.16)
    spacing = int(frame.height * 0.045)
    font = _get_font(config.SPEED_DIFFICULTY_FONT_SIZE, bold=True)

    for i, diff in enumerate(config.SPEED_DIFFICULTIES):
        y = start_y + i * spacing
        if diff == current_difficulty:
            color = config.SPEED_DIFFICULTY_COLORS[diff]
            tw = font.getlength(diff)
            pw = int(tw + 24)
            ph = int(spacing * 0.78)
            # Shadow
            draw.rounded_rectangle(
                [x - 3, y - ph // 2 + 2, x + pw + 2, y + ph // 2 + 2],
                radius=ph // 2, fill=(0, 0, 0, 30))
            draw.rounded_rectangle(
                [x - 5, y - ph // 2, x + pw, y + ph // 2],
                radius=ph // 2, fill=color + (230,))
            draw.rounded_rectangle(
                [x - 5, y - ph // 2, x + pw, y + ph // 2],
                radius=ph // 2, outline=(255, 255, 255, 120), width=2)
            draw.text((x + pw // 2 - 3, y), diff,
                      fill=(255, 255, 255), anchor="mm", font=font,
                      stroke_width=1, stroke_fill=(0, 0, 0, 120))
        else:
            draw.text((x, y), diff, fill=(255, 255, 255, 70),
                      anchor="lm", font=font,
                      stroke_width=1, stroke_fill=(0, 0, 0, 40))
    return frame


def _render_title(frame, category):
    draw = ImageDraw.Draw(frame)
    cat_display = config.CATEGORIES[category]["display"]
    title = f"Guess The {cat_display}"
    font = _get_font(config.SPEED_TITLE_FONT_SIZE, bold=True)
    # Aligned with photo card center (0.42) not screen center
    cx = int(frame.width * 0.42)
    cy = int(frame.height * 0.065)

    draw.text((cx + 3, cy + 3), title, fill=(0, 0, 0, 100),
              anchor="mm", font=font,
              stroke_width=4, stroke_fill=(0, 0, 0, 100))
    draw.text((cx, cy), title, fill=(255, 255, 255),
              anchor="mm", font=font,
              stroke_width=4, stroke_fill=(0, 0, 0))
    return frame


def _render_timer_bar(frame, progress, difficulty, t=0.0):
    draw = ImageDraw.Draw(frame)
    w, h = frame.size
    # Aligned with photo card width — starts and ends at card edges
    photo_cx = int(w * 0.42)
    card_half_w = (config.SPEED_PHOTO_WIDTH + config.SPEED_CARD_PADDING * 2) // 2
    bar_x = photo_cx - card_half_w
    bar_y = int(h * 0.86)
    bar_w = card_half_w * 2
    bar_h = config.SPEED_TIMER_HEIGHT

    # Track shadow
    draw.rounded_rectangle(
        [bar_x + 2, bar_y + 2, bar_x + bar_w + 2, bar_y + bar_h + 2],
        radius=bar_h // 2, fill=(0, 0, 0, 30))
    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + bar_w, bar_y + bar_h],
        radius=bar_h // 2, fill=(180, 180, 180, 200))

    fill_w = int(bar_w * (1.0 - progress))
    if fill_w > 0:
        gc = (46, 204, 113)
        if progress > 0.7:
            rm = (progress - 0.7) / 0.3
            gc = (int(46 + (231 - 46) * rm), int(204 + (76 - 204) * rm),
                  int(113 + (60 - 113) * rm))

        bar_alpha = 235
        if progress > 0.8:
            bar_alpha = int(200 + 55 * (0.7 + 0.3 * math.sin(t * 14)))

        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + fill_w, bar_y + bar_h],
            radius=bar_h // 2, fill=gc + (bar_alpha,))

        # Diagonal stripes
        for sx in range(bar_x, bar_x + fill_w, 18):
            if sx + 8 < bar_x + fill_w:
                draw.polygon([
                    (sx, bar_y + bar_h), (sx + 8, bar_y + bar_h),
                    (sx + 8 + bar_h, bar_y), (sx + bar_h, bar_y),
                ], fill=(255, 255, 255, 35))

        # Bright tip
        if fill_w > bar_h:
            tx = bar_x + fill_w - 3
            draw.ellipse([tx - 5, bar_y - 2, tx + 5, bar_y + bar_h + 2],
                         fill=(255, 255, 255, 210))
    return frame


def _render_countdown_numbers(frame, seconds_left, elapsed_in_second, t):
    """
    # Big countdown number overlay during timer phase.
    # Shows 3, 2, 1 — each pops in and shrinks before the next.
    # This is what Quiz Blitz does and creates massive tension.
    """
    w, h = frame.size
    num = max(1, seconds_left)
    if num > 3:
        return frame

    # Pop-in at start of each second, shrink by end
    pop_scale = 1.0
    if elapsed_in_second < 0.2:
        pop_scale = compute_scale(elapsed_in_second, 0.0, 0.2, "back_out")
    elif elapsed_in_second > 0.7:
        fade_progress = (elapsed_in_second - 0.7) / 0.3
        pop_scale = 1.0 - 0.3 * fade_progress

    if pop_scale < 0.05:
        return frame

    font_size = int(160 * max(0.1, pop_scale))

    # Color shifts per second: green → yellow → red
    colors = {3: (46, 204, 113), 2: (255, 200, 0), 1: (255, 60, 60)}
    num_color = colors.get(num, (255, 255, 255))

    # Position: slightly right of photo center
    cx = int(w * 0.42)
    cy = int(h * 0.44)

    # Glow behind number
    frame = render_glow_text(
        frame, str(num), (cx, cy), font_size,
        glow_color=num_color, text_color=(255, 255, 255),
        glow_radius=15,
    )

    return frame


def _render_mystery_badge(frame, t):
    """
    # Small "?" badge in top-right corner of photo card area.
    # Subtle mystery hint without blocking the photo or countdown.
    """
    draw = ImageDraw.Draw(frame)
    w, h = frame.size

    # Position: just above photo card, right side
    bx = int(w * 0.42) + config.SPEED_PHOTO_WIDTH // 2 - 20
    by = int(h * 0.44) - config.SPEED_PHOTO_HEIGHT // 2 - 25

    pulse = 0.7 + 0.3 * math.sin(t * 3)
    r = int(22 * pulse)
    alpha = int(180 * pulse)

    draw.ellipse([bx - r, by - r, bx + r, by + r],
                 fill=(255, 255, 255, alpha))
    font = _get_font(28, bold=True)
    draw.text((bx, by), "?", fill=(0, 0, 0, alpha),
              anchor="mm", font=font)
    return frame


def _render_checkmark(frame, elapsed, answer_text=""):
    """
    # Green checkmark that pops in to the right of the answer pill.
    # Position adapts to actual answer text width.
    """
    w, h = frame.size
    scale = compute_scale(elapsed, 0.15, 0.35, "elastic_out")
    if scale < 0.01:
        return frame

    # Calculate pill width from actual answer text to place checkmark after it
    font = _get_font(config.SPEED_ANSWER_FONT_SIZE, bold=True)
    text = f"{answer_text}!"
    tw = font.getlength(text)
    pill_half_w = int((tw + 50) / 2)

    cx = int(w * 0.42) + pill_half_w + 30
    cy = int(h * 0.72)
    r = int(28 * max(0.1, scale))

    draw = ImageDraw.Draw(frame)
    # Green circle
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 fill=(46, 204, 113, 240))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 outline=(255, 255, 255, 180), width=2)

    # Checkmark lines
    lw = max(2, int(4 * scale))
    p1 = (cx - int(r * 0.4), cy + int(r * 0.05))
    p2 = (cx - int(r * 0.05), cy + int(r * 0.4))
    p3 = (cx + int(r * 0.45), cy - int(r * 0.35))
    draw.line([p1, p2], fill=(255, 255, 255), width=lw)
    draw.line([p2, p3], fill=(255, 255, 255), width=lw)

    return frame


def _render_score_counter(frame, score, total, t):
    """
    # Running score counter at bottom-right.
    # Increments on each reveal — gives viewers a target to beat.
    """
    draw = ImageDraw.Draw(frame)
    w, h = frame.size
    font = _get_font(30, bold=True)
    cx = int(w * 0.78)
    cy = int(h * 0.92)

    text = f"Score: {score}/{total}"
    tw = font.getlength(text)
    pw = int(tw + 24)
    ph = 40

    # Semi-transparent dark pill
    draw.rounded_rectangle(
        [cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2],
        radius=ph // 2, fill=(0, 0, 0, 100))
    draw.text((cx, cy), text, fill=(255, 255, 255, 220),
              anchor="mm", font=font,
              stroke_width=2, stroke_fill=(0, 0, 0, 150))
    return frame


def _render_progress_bar(frame, current_round, total_rounds):
    """
    # Ultra-thin progress bar at very bottom of screen.
    # Shows how far through the 120 rounds the viewer is.
    """
    draw = ImageDraw.Draw(frame)
    w, h = frame.size
    bar_h = 6
    bar_y = h - bar_h

    progress = max(0, min(1, current_round / max(1, total_rounds)))
    fill_w = int(w * progress)

    # Track
    draw.rectangle([0, bar_y, w, h], fill=(0, 0, 0, 50))
    # Fill — gradient from green to gold
    if fill_w > 0:
        r_val = int(46 + (255 - 46) * progress)
        g_val = int(204 + (200 - 204) * progress)
        b_val = int(113 + (0 - 113) * progress)
        draw.rectangle([0, bar_y, fill_w, h],
                       fill=(r_val, g_val, b_val, 200))
    return frame


def _render_transition_wipe(frame, progress, round_idx, ctx):
    """
    # Diagonal wipe transition to next round's background color.
    # A colored band sweeps from right to left during the last 0.5s,
    # giving a clean professional transition between rounds.
    # Also fades out current round elements (handled by caller scaling down).
    """
    w, h = frame.size
    progress = max(0, min(1, progress))

    # Next round's background color
    next_idx = (round_idx + 1) % len(config.SPEED_BG_COLORS)
    next_color = config.SPEED_BG_COLORS[next_idx]

    # Diagonal wipe band sweeping from right to left
    # The band leads with a white edge for the "swoosh" feel
    wipe_x = int(w * (1.2 - progress * 1.6))

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    skew = int(h * 0.2)

    # Colored fill behind the wipe line
    fill_points = [
        (wipe_x - skew, 0), (w + 10, 0),
        (w + 10, h), (wipe_x + skew, h),
    ]
    od.polygon(fill_points, fill=next_color + (255,))

    # White leading edge (thin bright line for the swoosh)
    edge_w = 8
    edge_points = [
        (wipe_x - skew - edge_w, 0), (wipe_x - skew, 0),
        (wipe_x + skew, h), (wipe_x + skew - edge_w, h),
    ]
    od.polygon(edge_points, fill=(255, 255, 255, 180))

    frame = Image.alpha_composite(frame, overlay)
    return frame


def _render_radial_burst(frame, cx, cy, progress, color):
    """
    # Radial lines emanating from center — used on section card transitions.
    # Creates the "explosion" feel when a new difficulty level starts.
    """
    if progress < 0.01:
        return frame

    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    num_rays = 24
    max_len = int(min(frame.width, frame.height) * 0.7)
    ray_len = int(max_len * min(1.0, progress * 1.5))
    ray_alpha = int(60 * (1.0 - progress * 0.7))

    for i in range(num_rays):
        angle = (i / num_rays) * 2 * math.pi
        ex = cx + int(ray_len * math.cos(angle))
        ey = cy + int(ray_len * math.sin(angle))
        od.line([(cx, cy), (ex, ey)],
                fill=color + (ray_alpha,), width=3)

    frame = Image.alpha_composite(frame, overlay)
    return frame


# _render_mascot replaced by _render_mascot_animated above


def _render_branding(frame):
    draw = ImageDraw.Draw(frame)
    font = _get_font(config.SPEED_BRANDING_FONT_SIZE, bold=True)
    cx = int(frame.width * 0.50)
    cy = int(frame.height * 0.95)
    draw.text((cx, cy), "LEO QUIZ", fill=(255, 255, 255, 160),
              anchor="mm", font=font,
              stroke_width=2, stroke_fill=(0, 0, 0, 80))
    return frame


def _render_answer_text(frame, answer, elapsed, t):
    w, h = frame.size
    cx = int(w * 0.42)
    cy = int(h * 0.72)

    text_scale = compute_scale(elapsed, 0.0, 0.4, "elastic_out")
    if text_scale < 0.01:
        return frame

    font_size = int(config.SPEED_ANSWER_FONT_SIZE * max(0.3, text_scale))
    text = f"{answer}!"

    draw = ImageDraw.Draw(frame)
    font = _get_font(font_size, bold=True)
    tw = font.getlength(text)
    pw = int(tw + 50)
    ph = int(font_size * 1.6)

    # Shadow behind pill
    draw.rounded_rectangle(
        [cx - pw // 2 + 3, cy - ph // 2 + 3,
         cx + pw // 2 + 3, cy + ph // 2 + 3],
        radius=ph // 2, fill=(0, 0, 0, 40))
    draw.rounded_rectangle(
        [cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2],
        radius=ph // 2, fill=(46, 204, 113, 235))
    draw.rounded_rectangle(
        [cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2],
        radius=ph // 2, outline=(255, 255, 255, 150), width=2)

    frame = render_glow_text(
        frame, text, (cx, cy), font_size,
        glow_color=(46, 230, 113), text_color=(255, 255, 255),
        glow_radius=6,
    )
    return frame


def _render_fun_fact(frame, fact, elapsed):
    draw = ImageDraw.Draw(frame)
    w, h = frame.size

    opacity = compute_opacity(elapsed, 0.0, 0.3, "quad_out")
    if opacity < 0.01:
        return frame

    slide = int(20 * (1.0 - opacity))
    font = _get_font(28, bold=True)
    cx = int(w * 0.42)
    # Positioned between answer pill (0.72) and timer bar (0.86)
    cy = int(h * 0.78) + slide

    tw = font.getlength(fact)
    pw = min(int(tw + 30), int(w * 0.6))
    ph = 42
    alpha = int(170 * opacity)
    draw.rounded_rectangle(
        [cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2],
        radius=ph // 2, fill=(0, 0, 0, alpha))
    draw.text((cx, cy), fact, fill=(255, 255, 255, int(255 * opacity)),
              anchor="mm", font=font,
              stroke_width=2, stroke_fill=(0, 0, 0, int(180 * opacity)))
    return frame


# ============================================================
# SPECIAL SCREENS
# ============================================================
def _render_intro(frame, t, event, ctx):
    draw = ImageDraw.Draw(frame)
    w, h = frame.size
    elapsed = t - event["start"]
    cat_display = config.CATEGORIES[ctx.category]["display"]

    # "GUESS"
    s1 = compute_scale(elapsed, 0.0, 0.4, "back_out")
    if s1 > 0.01:
        f1 = _get_font(int(90 * max(0.1, s1)), bold=True)
        draw.text((w // 2, int(h * 0.18)), "GUESS",
                  fill=(255, 255, 255), anchor="mm", font=f1,
                  stroke_width=5, stroke_fill=(0, 0, 0))

    # "120" with glow
    s2 = compute_scale(elapsed, 0.15, 0.4, "elastic_out")
    if s2 > 0.01:
        frame = render_glow_text(
            frame, str(ctx.total_rounds),
            (w // 2, int(h * 0.31)), int(120 * max(0.1, s2)),
            glow_color=(255, 200, 0), text_color=(255, 230, 0),
            glow_radius=12)

    # Category name
    s3 = compute_scale(elapsed, 0.3, 0.4, "back_out")
    if s3 > 0.01:
        f3 = _get_font(int(85 * max(0.1, s3)), bold=True)
        txt = f"{cat_display.upper()}S"
        draw = ImageDraw.Draw(frame)
        draw.text((w // 2, int(h * 0.44)), txt,
                  fill=(255, 255, 255), anchor="mm", font=f3,
                  stroke_width=5, stroke_fill=(0, 0, 0))

    # "IN 3 SECONDS"
    s4 = compute_scale(elapsed, 0.45, 0.4, "back_out")
    if s4 > 0.01:
        f4 = _get_font(int(75 * max(0.1, s4)), bold=True)
        draw = ImageDraw.Draw(frame)
        in_t, three_t, sec_t = "IN ", "3", " SECONDS"
        total_t = in_t + three_t + sec_t
        total_w = f4.getlength(total_t)
        sx = w // 2 - int(total_w // 2)
        ty = int(h * 0.56)
        iw = f4.getlength(in_t)
        tw2 = f4.getlength(three_t)
        draw.text((sx, ty), in_t, fill=(255, 255, 255), anchor="lm", font=f4,
                  stroke_width=4, stroke_fill=(0, 0, 0))
        draw.text((sx + int(iw), ty), three_t,
                  fill=(255, 230, 0), anchor="lm", font=f4,
                  stroke_width=4, stroke_fill=(0, 0, 0))
        draw.text((sx + int(iw + tw2), ty), sec_t,
                  fill=(255, 255, 255), anchor="lm", font=f4,
                  stroke_width=4, stroke_fill=(0, 0, 0))

    # Sample photos
    if elapsed > 1.0 and len(ctx.photo_paths) >= 3:
        idxs = [0, len(ctx.photo_paths) // 3, len(ctx.photo_paths) * 2 // 3]
        positions = [(int(w * 0.25), int(h * 0.76)),
                     (int(w * 0.50), int(h * 0.76)),
                     (int(w * 0.75), int(h * 0.76))]
        for j, (idx, (px, py)) in enumerate(zip(idxs, positions)):
            ps = compute_scale(elapsed, 1.0 + j * 0.15, 0.5, "back_out")
            if idx < len(ctx.photo_paths) and ps > 0.01:
                frame = _render_photo_card(
                    frame, ctx.photo_paths[idx], px, py,
                    scale=0.3 * max(0.1, ps), ctx=ctx)

    # Mascot waving on intro screen (right side)
    frame = _render_mascot_animated(
        frame, ctx, t, "intro", event_start=event["start"],
        position="right")

    frame = apply_vignette(frame, intensity=0.25)
    return frame


def _render_subscribe(frame, t, event, ctx):
    w, h = frame.size
    elapsed = t - event["start"]

    overlay = Image.new("RGBA", (w, h), (30, 30, 35, 220))
    frame = Image.alpha_composite(frame, overlay)
    draw = ImageDraw.Draw(frame)

    s = compute_scale(elapsed, 0.2, 0.5, "elastic_out")
    if s > 0.01:
        font = _get_font(int(70 * max(0.1, s)), bold=True)
        cx, cy = w // 2, int(h * 0.43)
        pw2 = int(500 * max(0.3, s))
        ph2 = int(90 * max(0.3, s))
        draw.rounded_rectangle(
            [cx - pw2 // 2 + 4, cy - ph2 // 2 + 4,
             cx + pw2 // 2 + 4, cy + ph2 // 2 + 4],
            radius=ph2 // 2, fill=(0, 0, 0, 30))
        draw.rounded_rectangle(
            [cx - pw2 // 2, cy - ph2 // 2, cx + pw2 // 2, cy + ph2 // 2],
            radius=ph2 // 2, fill=(255, 0, 0, 240))
        draw.rounded_rectangle(
            [cx - pw2 // 2, cy - ph2 // 2, cx + pw2 // 2, cy + ph2 // 2],
            radius=ph2 // 2, outline=(255, 255, 255, 150), width=3)
        draw.text((cx, cy), "SUBSCRIBE", fill=(255, 255, 255),
                  anchor="mm", font=font,
                  stroke_width=3, stroke_fill=(150, 0, 0))

    so = compute_opacity(elapsed, 0.8, 0.4, "quad_out")
    if so > 0.01:
        f2 = _get_font(36, bold=True)
        draw.text((w // 2, int(h * 0.58)),
                  "Hit subscribe and the bell before we start!",
                  fill=(255, 255, 255, int(255 * so)),
                  stroke_width=2, stroke_fill=(0, 0, 0, int(200 * so)),
                  anchor="mm", font=f2)

    # Mascot waving on subscribe screen (right side)
    frame = _render_mascot_animated(
        frame, ctx, t, "subscribe", event_start=event["start"],
        position="right")

    return frame


def _render_section_card(frame, t, event, ctx):
    w, h = frame.size
    elapsed = t - event["start"]
    difficulty = event.get("difficulty", "EASY")
    diff_color = config.SPEED_DIFFICULTY_COLORS.get(difficulty, (255, 230, 0))

    # Radial burst behind text
    burst_progress = compute_scale(elapsed, 0.0, 0.8, "quad_out")
    frame = _render_radial_burst(
        frame, w // 2, int(h * 0.45), burst_progress, diff_color)

    # Difficulty name with glow
    s = compute_scale(elapsed, 0.0, 0.5, "elastic_out")
    if s > 0.01:
        fs = int(config.SPEED_SECTION_FONT_SIZE * max(0.1, s))
        frame = render_glow_text(
            frame, difficulty, (w // 2, int(h * 0.40)), fs,
            glow_color=diff_color, text_color=diff_color,
            glow_radius=14)

    # "LEVEL"
    s2 = compute_scale(elapsed, 0.2, 0.5, "back_out")
    if s2 > 0.01:
        f2 = _get_font(int(80 * max(0.1, s2)), bold=True)
        draw = ImageDraw.Draw(frame)
        draw.text((w // 2, int(h * 0.56)), "LEVEL",
                  fill=(255, 255, 255), anchor="mm", font=f2,
                  stroke_width=5, stroke_fill=(0, 0, 0))

    # Round count preview ("Rounds 1-30" etc.)
    s3 = compute_opacity(elapsed, 0.5, 0.3, "quad_out")
    if s3 > 0.01:
        sec_idx = config.SPEED_DIFFICULTIES.index(difficulty)
        start_r = sec_idx * config.SPEED_ROUNDS_PER_DIFFICULTY + 1
        end_r = (sec_idx + 1) * config.SPEED_ROUNDS_PER_DIFFICULTY
        f3 = _get_font(34, bold=True)
        draw = ImageDraw.Draw(frame)
        draw.text((w // 2, int(h * 0.67)),
                  f"Rounds {start_r}-{end_r}",
                  fill=(255, 255, 255, int(180 * s3)),
                  anchor="mm", font=f3,
                  stroke_width=2, stroke_fill=(0, 0, 0, int(150 * s3)))

    # Mascot excited on section card (right side)
    frame = _render_mascot_animated(
        frame, ctx, t, "section_card", difficulty=difficulty,
        event_start=event["start"], position="right")

    frame = ScreenShake.apply(frame, t, event["start"],
                              duration=0.25, intensity=10.0,
                              seed=int(event["start"] * 100))
    return frame


def _render_outro(frame, t, event, ctx):
    draw = ImageDraw.Draw(frame)
    w, h = frame.size
    elapsed = t - event["start"]

    s = compute_scale(elapsed, 0.0, 0.5, "back_out")
    if s > 0.01:
        frame = render_glow_text(
            frame, f"YOU COMPLETED {ctx.total_rounds} QUESTIONS!",
            (w // 2, int(h * 0.22)), int(60 * max(0.1, s)),
            glow_color=(255, 200, 0), text_color=(255, 230, 0),
            glow_radius=10)

    o2 = compute_opacity(elapsed, 0.6, 0.4, "quad_out")
    if o2 > 0.01:
        draw = ImageDraw.Draw(frame)
        f2 = _get_font(48, bold=True)
        draw.text((w // 2, int(h * 0.38)),
                  "How many did YOU get right?",
                  fill=(255, 255, 255, int(255 * o2)),
                  anchor="mm", font=f2,
                  stroke_width=3, stroke_fill=(0, 0, 0, int(220 * o2)))

    o3 = compute_opacity(elapsed, 1.2, 0.5, "quad_out")
    if o3 > 0.01:
        draw = ImageDraw.Draw(frame)
        f3 = _get_font(44, bold=True)
        draw.text((w // 2, int(h * 0.55)),
                  "SUBSCRIBE for more quizzes!",
                  fill=(255, 100, 100, int(255 * o3)),
                  anchor="mm", font=f3,
                  stroke_width=3, stroke_fill=(0, 0, 0, int(220 * o3)))
        f4 = _get_font(34, bold=True)
        draw.text((w // 2, int(h * 0.64)),
                  "Like & Comment your score!",
                  fill=(255, 255, 255, int(200 * o3)),
                  anchor="mm", font=f4,
                  stroke_width=2, stroke_fill=(0, 0, 0, int(180 * o3)))

    # Mascot celebrating at bottom center on outro
    frame = _render_mascot_animated(
        frame, ctx, t, "outro", event_start=event["start"],
        position="center")

    frame = apply_vignette(frame, intensity=0.3)
    return frame


# ============================================================
# MAIN FRAME RENDERER
# ============================================================
def render_speed_frame(t: float, ctx: SpeedQuizContext) -> np.ndarray:
    w, h = ctx.width, ctx.height
    event = _get_event(t, ctx.timeline)
    phase = event["phase"]
    round_idx = event["round"]
    difficulty = event.get("difficulty", "EASY")

    bg_round = max(0, round_idx) if round_idx >= 0 else 0
    frame = _render_background(w, h, bg_round, difficulty, t, ctx)

    # ===== INTRO =====
    if phase == "intro":
        frame = _render_intro(frame, t, event, ctx)
        if ctx.sparkles:
            return ctx.sparkles.render(np.array(frame.convert("RGB")), t)
        return np.array(frame.convert("RGB"))

    # ===== SUBSCRIBE =====
    if phase == "subscribe":
        frame = _render_subscribe(frame, t, event, ctx)
        return np.array(frame.convert("RGB"))

    # ===== SECTION CARD =====
    if phase == "section_card":
        frame = _render_section_card(frame, t, event, ctx)
        if ctx.sparkles:
            return ctx.sparkles.render(np.array(frame.convert("RGB")), t)
        return np.array(frame.convert("RGB"))

    # ===== OUTRO =====
    if phase == "outro":
        frame = _render_outro(frame, t, event, ctx)
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)
        if ctx.sparkles:
            return ctx.sparkles.render(np.array(frame.convert("RGB")), t)
        return np.array(frame.convert("RGB"))

    # ===== QUIZ ROUND =====
    if round_idx < 0 or round_idx >= len(ctx.rounds):
        return np.array(frame.convert("RGB"))

    round_data = ctx.rounds[round_idx]
    round_events = [e for e in ctx.timeline if e["round"] == round_idx]
    round_start = round_events[0]["start"] if round_events else 0
    elapsed = t - round_start

    # --- Check if we're in the transition-out window (last 0.5s) ---
    transition_elapsed = elapsed - config.SPEED_TRANSITION_START
    in_transition = transition_elapsed > 0 and phase == "fact"

    # --- Round badge ---
    frame = _render_round_badge(frame, round_idx + 1, t)

    # --- Title ---
    frame = _render_title(frame, ctx.category)

    # --- Difficulty sidebar ---
    frame = _render_difficulty_sidebar(frame, difficulty)

    # --- Photo card ---
    photo_cx = int(w * 0.42)
    photo_cy = int(h * 0.44)

    if phase == "question":
        # Slide in from right
        slide = compute_scale(elapsed, 0.0, 0.35, "back_out")
        slide_x = int(photo_cx + (w * 0.25) * (1 - slide))

        # Ken Burns zoom progress
        q_dur = config.SPEED_REVEAL_START - config.SPEED_PHOTO_START
        zoom_p = min(1.0, elapsed / q_dur) if q_dur > 0 else 0

        # Glow ring behind photo
        if slide > 0.5:
            dc = config.SPEED_DIFFICULTY_COLORS.get(difficulty, (255, 230, 0))
            frame = GlowRing.render(
                frame, photo_cx, photo_cy,
                int(config.SPEED_PHOTO_WIDTH * 0.55), dc, t, pulse_speed=1.5)

        frame = _render_photo_card(
            frame, ctx.photo_paths[round_idx] if round_idx < len(ctx.photo_paths) else None,
            slide_x, photo_cy, scale=max(0.1, slide), ctx=ctx,
            apply_zoom=True, zoom_progress=zoom_p)

        # Mystery "?" overlay (fades as timer progresses)
        timer_start = round_start + config.SPEED_TIMER_START
        timer_end = round_start + config.SPEED_REVEAL_START
        if t >= timer_start:
            timer_progress = min(1.0, (t - timer_start) / (timer_end - timer_start))
            frame = _render_mystery_badge(frame, t)
            frame = _render_timer_bar(frame, timer_progress, difficulty, t)

            # Visual countdown 3-2-1
            seconds_total = config.SPEED_TIMER_SECONDS
            time_in_timer = t - timer_start
            seconds_left = max(1, seconds_total - int(time_in_timer))
            elapsed_in_second = time_in_timer - int(time_in_timer)
            frame = _render_countdown_numbers(frame, seconds_left, elapsed_in_second, t)
        else:
            frame = _render_timer_bar(frame, 0.0, difficulty, t)

    elif phase in ("reveal", "fact"):
        # Photo stays center (slide out during transition)
        photo_x = photo_cx
        if in_transition:
            # Slide out to the left during transition
            slide_out = transition_elapsed / (config.SPEED_ROUND_DURATION - config.SPEED_TRANSITION_START)
            photo_x = int(photo_cx - (w * 0.4) * slide_out)

        frame = _render_photo_card(
            frame, ctx.photo_paths[round_idx] if round_idx < len(ctx.photo_paths) else None,
            photo_x, photo_cy, ctx=ctx)

        frame = _render_timer_bar(frame, 1.0, difficulty, t)

        # Answer text with glow
        reveal_start = round_start + config.SPEED_REVEAL_START
        reveal_elapsed = t - reveal_start
        frame = _render_answer_text(frame, round_data.answer, reveal_elapsed, t)

        # Green checkmark — positioned after the answer pill
        frame = _render_checkmark(frame, reveal_elapsed, round_data.answer)

        # Screen shake on reveal
        frame = ScreenShake.apply(frame, t, reveal_start,
                                  duration=0.2, intensity=8.0,
                                  seed=round_idx * 7)

        # Fun fact
        if phase == "fact":
            fact_start = round_start + config.SPEED_FACT_START
            fact_elapsed = t - fact_start
            frame = _render_fun_fact(frame, round_data.fun_fact, fact_elapsed)

        # Confetti
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)

    # --- Diagonal wipe transition to next round ---
    if in_transition:
        wipe_progress = transition_elapsed / (config.SPEED_ROUND_DURATION - config.SPEED_TRANSITION_START)
        frame = _render_transition_wipe(frame, wipe_progress, round_idx, ctx)

    # --- Mascot (animated, pose changes by phase/difficulty) ---
    reveal_time = round_start + config.SPEED_REVEAL_START if phase in ("reveal", "fact") else 0
    frame = _render_mascot_animated(
        frame, ctx, t, phase, difficulty=difficulty,
        round_idx=round_idx, event_start=event["start"],
        reveal_time=reveal_time, position="right")

    # --- Branding ---
    frame = _render_branding(frame)

    # --- Score counter ---
    frame = _render_score_counter(frame, round_idx + 1, ctx.total_rounds, t)

    # --- Progress bar ---
    frame = _render_progress_bar(frame, round_idx + 1, ctx.total_rounds)

    # --- Sparkles ---
    if ctx.sparkles:
        return ctx.sparkles.render(np.array(frame.convert("RGB")), t)

    return np.array(frame.convert("RGB"))


# ============================================================
# ASSEMBLY
# ============================================================
def assemble_speed_quiz(quiz_pack, photo_paths, round_audios,
                        audio_path, output_path, mascot_dir=None,
                        narration_pack=None):
    from moviepy import VideoClip, AudioFileClip

    w, h = config.LONGFORM_SIZE
    num_rounds = len(quiz_pack.rounds)

    mascot_images = {}
    if mascot_dir is None:
        mascot_dir = config.MASCOT_DIR
    for pose_name, pose_path in config.MASCOT_POSES.items():
        if pose_path.exists():
            img = Image.open(pose_path).convert("RGBA")
            # Remove white background for clean compositing over video
            img = _remove_white_bg(img)
            mascot_images[pose_name] = img
            print(f"[SPEED] Loaded mascot pose: {pose_name} ({img.size[0]}x{img.size[1]})")

    timeline = build_speed_timeline(num_rounds)
    total_duration = timeline[-1]["end"]

    sparkles = ParticleSystem(w, h, count=25, seed=42)
    decorations = ThemedDecorations(quiz_pack.category, w, h, seed=99)

    confetti_bursts = []
    for event in timeline:
        if event["phase"] == "reveal":
            confetti_bursts.append(ConfettiBurst(
                center_x=int(w * 0.42), center_y=int(h * 0.44),
                trigger_time=event["start"], count=45,
                seed=int(event["start"] * 100)))
    outro_events = [e for e in timeline if e["phase"] == "outro"]
    if outro_events:
        confetti_bursts.append(ConfettiBurst(
            center_x=w // 2, center_y=int(h * 0.40),
            trigger_time=outro_events[0]["start"] + 0.3,
            count=80, seed=999))

    # Build per-round reveal text for speech bubbles ("It's a Lion!" etc.)
    narration_script = {}
    round_reveal_texts = []
    if narration_pack:
        narration_script = getattr(narration_pack, "script", {}) or {}
        # Reconstruct reveal text from templates + answers
        templates = narration_script.get("reveal_templates", [])
        if templates:
            for i, rnd in enumerate(quiz_pack.rounds):
                template = templates[i % len(templates)]
                try:
                    text = template.format(answer=rnd.answer)
                except (KeyError, IndexError):
                    text = f"It's a {rnd.answer}!"
                round_reveal_texts.append(text)
        else:
            round_reveal_texts = [f"It's a {r.answer}!" for r in quiz_pack.rounds]
    else:
        round_reveal_texts = [f"It's a {r.answer}!" for r in quiz_pack.rounds]

    ctx = SpeedQuizContext(
        width=w, height=h, category=quiz_pack.category,
        rounds=quiz_pack.rounds, photo_paths=photo_paths,
        mascot_images=mascot_images, total_rounds=num_rounds,
        timeline=timeline, confetti_bursts=confetti_bursts,
        round_audios=round_audios,
        sparkles=sparkles, decorations=decorations,
        narration_script=narration_script,
        round_reveal_texts=round_reveal_texts)

    print(f"[SPEED] Rendering {num_rounds} rounds, {total_duration:.0f}s total")
    print(f"[SPEED] Effects: sparkles, glow, shake, Ken Burns, confetti,")
    print(f"[SPEED]   countdown, wipe transitions, checkmarks, score, progress")

    video = VideoClip(lambda t: render_speed_frame(t, ctx), duration=total_duration)
    video = video.with_fps(config.FPS)

    if audio_path and audio_path.exists():
        audio = AudioFileClip(str(audio_path))
        video = video.with_audio(audio)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(output_path), codec="libx264",
        bitrate=config.LONGFORM_BITRATE, preset="medium",
        audio_codec="aac", audio_bitrate=config.AUDIO_BITRATE,
        threads=4, logger="bar")

    print(f"[SPEED] Video saved: {output_path}")
    return output_path
