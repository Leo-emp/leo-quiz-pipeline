# mascot_generator.py
# ============================================================
# Generates Leo the Lion mascot images using Gemini Imagen.
# Run once to create 4 poses (thinking, excited, waving, surprised)
# stored in assets/mascot/. The pipeline uses these automatically.
# If Gemini is unavailable, falls back to simple PIL-drawn mascot.
# ============================================================
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

import config


# --- Mascot generation prompts for Gemini Imagen ---
MASCOT_PROMPTS = {
    "thinking": (
        "Cute cartoon lion cub mascot character, thinking pose with paw on chin, "
        "big expressive eyes looking upward, golden yellow fur, small mane, "
        "chibi kawaii style, kid-friendly, full body, transparent background, "
        "no text, clean edges, children's animation style, bright colors"
    ),
    "excited": (
        "Cute cartoon lion cub mascot character, excited celebration pose, "
        "arms raised up happily, big smile with sparkle eyes, golden yellow fur, "
        "small mane, chibi kawaii style, kid-friendly, full body, "
        "transparent background, no text, clean edges, children's animation style"
    ),
    "waving": (
        "Cute cartoon lion cub mascot character, friendly waving pose, "
        "one paw waving hello, warm smile, golden yellow fur, small mane, "
        "chibi kawaii style, kid-friendly, full body, transparent background, "
        "no text, clean edges, children's animation style"
    ),
    "surprised": (
        "Cute cartoon lion cub mascot character, surprised amazed pose, "
        "mouth open in wow expression, wide eyes, paws up in surprise, "
        "golden yellow fur, small mane, chibi kawaii style, kid-friendly, "
        "full body, transparent background, no text, clean edges"
    ),
}


def _draw_simple_lion(pose: str, size: int = 512) -> Image.Image:
    """
    # Draw a detailed cartoon lion mascot using PIL as fallback.
    # UPGRADED: proper mane with spikes, round ears, cheek blush,
    # whiskers, belly patch, tail, feet, and expressive poses.
    # Much closer to the quality of AI-generated mascots.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx = size // 2
    # Shift everything up a bit so the full body fits
    cy = int(size * 0.45)

    # Color palette for Leo
    GOLD = (255, 210, 80, 255)        # Main body
    DARK_GOLD = (230, 180, 50, 255)   # Darker shade for depth
    MANE_ORANGE = (235, 140, 25, 255) # Mane color
    MANE_DARK = (200, 110, 15, 255)   # Mane shadow
    BELLY = (255, 240, 200, 255)      # Light belly patch
    NOSE_BROWN = (140, 80, 35, 255)
    EYE_WHITE = (255, 255, 255, 255)
    PUPIL = (35, 35, 35, 255)
    BLUSH = (255, 170, 140, 100)      # Semi-transparent cheek blush
    OUTLINE = (100, 60, 20, 255)      # Dark outline color

    head_r = int(size * 0.18)
    body_w = int(size * 0.22)
    body_h = int(size * 0.28)
    head_cy = cy - int(size * 0.08)

    # --- Tail (behind body) ---
    tail_start_x = cx + body_w - 10
    tail_start_y = cy + body_h // 2
    # Curving tail to the right
    draw.arc([tail_start_x - 20, tail_start_y - 40,
              tail_start_x + 50, tail_start_y + 30],
             start=200, end=360, fill=GOLD, width=10)
    # Tail tuft (darker)
    draw.ellipse([tail_start_x + 30, tail_start_y - 45,
                  tail_start_x + 55, tail_start_y - 20],
                 fill=MANE_ORANGE)

    # --- Feet (behind body) ---
    foot_w = int(size * 0.07)
    foot_h = int(size * 0.04)
    foot_y = cy + body_h - 5
    for foot_x_offset in [-body_w // 2 + foot_w, body_w // 2 - foot_w]:
        fx = cx + foot_x_offset
        draw.ellipse([fx - foot_w, foot_y, fx + foot_w, foot_y + foot_h],
                     fill=GOLD, outline=OUTLINE, width=2)

    # --- Body (oval torso) ---
    draw.ellipse([cx - body_w, cy - body_h // 4,
                  cx + body_w, cy + body_h],
                 fill=GOLD, outline=OUTLINE, width=3)

    # Belly patch (lighter oval on chest)
    belly_w = int(body_w * 0.6)
    belly_h = int(body_h * 0.5)
    draw.ellipse([cx - belly_w, cy + 5,
                  cx + belly_w, cy + belly_h],
                 fill=BELLY)

    # --- Mane (spiky circle behind head) ---
    mane_r = int(head_r * 1.6)
    # Draw mane as overlapping circles/triangles for spiky look
    spike_count = 12
    for i in range(spike_count):
        angle = math.radians(i * 360 / spike_count - 90)
        spike_x = int(cx + mane_r * 0.85 * math.cos(angle))
        spike_y = int(head_cy + mane_r * 0.85 * math.sin(angle))
        spike_r = int(mane_r * 0.4)
        # Alternate between two mane colors for depth
        color = MANE_ORANGE if i % 2 == 0 else MANE_DARK
        draw.ellipse([spike_x - spike_r, spike_y - spike_r,
                      spike_x + spike_r, spike_y + spike_r],
                     fill=color)
    # Solid mane center
    draw.ellipse([cx - mane_r + 15, head_cy - mane_r + 15,
                  cx + mane_r - 15, head_cy + mane_r - 15],
                 fill=MANE_ORANGE)

    # --- Head (golden circle on top of mane) ---
    draw.ellipse([cx - head_r, head_cy - head_r,
                  cx + head_r, head_cy + head_r],
                 fill=GOLD, outline=OUTLINE, width=3)

    # --- Ears (round, on top of head) ---
    ear_r = int(head_r * 0.3)
    for sign in (-1, 1):
        ear_x = cx + sign * int(head_r * 0.7)
        ear_y = head_cy - int(head_r * 0.7)
        draw.ellipse([ear_x - ear_r, ear_y - ear_r,
                      ear_x + ear_r, ear_y + ear_r],
                     fill=GOLD, outline=OUTLINE, width=2)
        # Inner ear (pink)
        inner_r = int(ear_r * 0.6)
        draw.ellipse([ear_x - inner_r, ear_y - inner_r,
                      ear_x + inner_r, ear_y + inner_r],
                     fill=(255, 180, 150, 255))

    # --- Eyes (big, expressive, anime-style) ---
    eye_offset = int(head_r * 0.38)
    eye_r = int(head_r * 0.28)
    for sign in (-1, 1):
        ex = cx + sign * eye_offset
        ey = head_cy - int(head_r * 0.05)
        # White sclera
        draw.ellipse([ex - eye_r, ey - eye_r, ex + eye_r, ey + eye_r],
                     fill=EYE_WHITE, outline=OUTLINE, width=2)

        # Pupil position varies by pose
        pupil_r = int(eye_r * 0.55)
        px_shift, py_shift = 0, 0
        if pose == "thinking":
            py_shift = -int(eye_r * 0.25)
            px_shift = sign * int(eye_r * 0.1)
        elif pose == "surprised":
            pupil_r = int(eye_r * 0.4)  # Smaller = surprise
        elif pose == "excited":
            # Sparkle eyes — pupils are star-shaped (just smaller)
            pupil_r = int(eye_r * 0.5)
        draw.ellipse([ex - pupil_r + px_shift, ey - pupil_r + py_shift,
                      ex + pupil_r + px_shift, ey + pupil_r + py_shift],
                     fill=PUPIL)
        # Eye highlight (white dot for life)
        highlight_r = int(pupil_r * 0.3)
        hx = ex - int(pupil_r * 0.3) + px_shift
        hy = ey - int(pupil_r * 0.3) + py_shift
        draw.ellipse([hx - highlight_r, hy - highlight_r,
                      hx + highlight_r, hy + highlight_r],
                     fill=EYE_WHITE)

    # --- Eyebrows (pose-specific) ---
    brow_w = int(eye_r * 0.8)
    brow_y = head_cy - int(head_r * 0.35)
    if pose == "thinking":
        # One raised, one lowered
        draw.line([(cx - eye_offset - brow_w, brow_y),
                   (cx - eye_offset + brow_w, brow_y - 5)],
                  fill=OUTLINE, width=4)
        draw.line([(cx + eye_offset - brow_w, brow_y - 8),
                   (cx + eye_offset + brow_w, brow_y - 3)],
                  fill=OUTLINE, width=4)
    elif pose == "surprised":
        # Both raised high
        for sign in (-1, 1):
            draw.line([(cx + sign * eye_offset - brow_w, brow_y - 5),
                       (cx + sign * eye_offset + brow_w, brow_y - 5)],
                      fill=OUTLINE, width=4)
    else:
        # Normal happy brows
        for sign in (-1, 1):
            draw.arc([cx + sign * eye_offset - brow_w, brow_y - 10,
                      cx + sign * eye_offset + brow_w, brow_y + 5],
                     start=200, end=340, fill=OUTLINE, width=3)

    # --- Nose (heart-shaped) ---
    nose_y = head_cy + int(head_r * 0.2)
    nose_s = int(head_r * 0.12)
    draw.ellipse([cx - nose_s, nose_y - nose_s // 2,
                  cx + nose_s, nose_y + nose_s],
                 fill=NOSE_BROWN)

    # --- Whiskers (3 per side) ---
    whisker_y = nose_y + nose_s
    whisker_len = int(head_r * 0.5)
    for sign in (-1, 1):
        for dy in range(-8, 12, 8):
            draw.line([(cx + sign * nose_s, whisker_y + dy),
                       (cx + sign * (nose_s + whisker_len), whisker_y + dy - 3)],
                      fill=OUTLINE, width=2)

    # --- Mouth (pose-specific) ---
    mouth_y = nose_y + nose_s + 8
    if pose == "excited":
        # Big open smile
        draw.arc([cx - int(head_r * 0.35), mouth_y - 15,
                  cx + int(head_r * 0.35), mouth_y + 20],
                 start=0, end=180, fill=OUTLINE, width=4)
        # Tongue
        tongue_r = int(head_r * 0.1)
        draw.ellipse([cx - tongue_r, mouth_y + 5,
                      cx + tongue_r, mouth_y + 5 + tongue_r],
                     fill=(255, 130, 130, 255))
    elif pose == "surprised":
        # Open "O" mouth
        mouth_r = int(head_r * 0.15)
        draw.ellipse([cx - mouth_r, mouth_y - mouth_r // 2,
                      cx + mouth_r, mouth_y + mouth_r],
                     fill=(180, 70, 60, 255), outline=OUTLINE, width=2)
    elif pose == "thinking":
        # Small wavy line
        draw.arc([cx - int(head_r * 0.15), mouth_y - 5,
                  cx + int(head_r * 0.15), mouth_y + 10],
                 start=180, end=360, fill=OUTLINE, width=3)
    else:
        # Gentle warm smile
        draw.arc([cx - int(head_r * 0.25), mouth_y - 10,
                  cx + int(head_r * 0.25), mouth_y + 15],
                 start=0, end=180, fill=OUTLINE, width=3)

    # --- Cheek blush (semi-transparent pink circles) ---
    blush_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    blush_draw = ImageDraw.Draw(blush_layer)
    blush_r = int(head_r * 0.15)
    for sign in (-1, 1):
        bx = cx + sign * int(head_r * 0.55)
        by = mouth_y - 5
        blush_draw.ellipse([bx - blush_r, by - blush_r,
                            bx + blush_r, by + blush_r],
                           fill=BLUSH)
    img = Image.alpha_composite(img, blush_layer)
    draw = ImageDraw.Draw(img)  # Re-create draw after composite

    # --- Arms/paws (pose-specific, with paw pads) ---
    arm_thickness = 14
    paw_r = int(head_r * 0.2)
    arm_y = cy + body_h // 6

    if pose == "waving":
        # Left arm resting
        draw.line([(cx - body_w + 10, arm_y + 10),
                   (cx - body_w - 15, arm_y + body_h // 3)],
                  fill=GOLD, width=arm_thickness)
        draw.ellipse([cx - body_w - 15 - paw_r, arm_y + body_h // 3 - paw_r,
                      cx - body_w - 15 + paw_r, arm_y + body_h // 3 + paw_r],
                     fill=GOLD, outline=OUTLINE, width=2)
        # Right arm waving up
        draw.line([(cx + body_w - 10, arm_y),
                   (cx + body_w + 30, arm_y - body_h // 2)],
                  fill=GOLD, width=arm_thickness)
        draw.ellipse([cx + body_w + 30 - paw_r, arm_y - body_h // 2 - paw_r,
                      cx + body_w + 30 + paw_r, arm_y - body_h // 2 + paw_r],
                     fill=GOLD, outline=OUTLINE, width=2)
    elif pose == "excited":
        # Both arms raised in celebration
        for sign in (-1, 1):
            draw.line([(cx + sign * (body_w - 10), arm_y),
                       (cx + sign * (body_w + 25), arm_y - body_h // 2 - 10)],
                      fill=GOLD, width=arm_thickness)
            px = cx + sign * (body_w + 25)
            py = arm_y - body_h // 2 - 10
            draw.ellipse([px - paw_r, py - paw_r, px + paw_r, py + paw_r],
                         fill=GOLD, outline=OUTLINE, width=2)
    elif pose == "thinking":
        # Left arm normal, right arm bent to chin
        draw.line([(cx - body_w + 10, arm_y + 10),
                   (cx - body_w - 10, arm_y + body_h // 4)],
                  fill=GOLD, width=arm_thickness)
        # Right arm to chin
        draw.line([(cx + body_w - 10, arm_y),
                   (cx + int(head_r * 0.4), head_cy + head_r - 5)],
                  fill=GOLD, width=arm_thickness)
        draw.ellipse([cx + int(head_r * 0.3) - paw_r,
                      head_cy + head_r - 5 - paw_r,
                      cx + int(head_r * 0.3) + paw_r,
                      head_cy + head_r - 5 + paw_r],
                     fill=GOLD, outline=OUTLINE, width=2)
    elif pose == "surprised":
        # Both paws up, spread apart
        for sign in (-1, 1):
            draw.line([(cx + sign * (body_w - 10), arm_y),
                       (cx + sign * (body_w + 20), arm_y - body_h // 4)],
                      fill=GOLD, width=arm_thickness)
            px = cx + sign * (body_w + 20)
            py = arm_y - body_h // 4
            draw.ellipse([px - paw_r, py - paw_r, px + paw_r, py + paw_r],
                         fill=GOLD, outline=OUTLINE, width=2)

    return img


def generate_mascot_with_gemini(pose: str, output_path: Path) -> bool:
    """
    # Generate a mascot image using Gemini Imagen API.
    # Returns True if successful, False if API unavailable.
    """
    try:
        from google import genai
        from google.genai import types

        if not config.GEMINI_API_KEY:
            print(f"[MASCOT] No GEMINI_API_KEY — skipping Imagen for {pose}")
            return False

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        prompt = MASCOT_PROMPTS[pose]

        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
            ),
        )

        if result.generated_images:
            img_bytes = result.generated_images[0].image.image_bytes
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(img_bytes)
            print(f"[MASCOT] Generated {pose} via Gemini Imagen → {output_path}")
            return True

    except Exception as e:
        print(f"[MASCOT] Gemini Imagen failed for {pose}: {e}")

    return False


def ensure_mascot_images():
    """
    # Generate any missing mascot pose images.
    # Tries Gemini Imagen first, falls back to simple PIL drawings.
    # Called automatically by the pipeline when mascot images are missing.
    """
    generated = []

    for pose_name, pose_path in config.MASCOT_POSES.items():
        if pose_path.exists():
            continue  # Already have this pose — skip

        print(f"[MASCOT] Missing {pose_name} mascot — generating...")

        # Try Gemini Imagen first (best quality)
        if generate_mascot_with_gemini(pose_name, pose_path):
            generated.append(f"{pose_name} (Gemini)")
            continue

        # Fallback: simple PIL-drawn mascot
        print(f"[MASCOT] Falling back to PIL drawing for {pose_name}")
        img = _draw_simple_lion(pose_name)
        pose_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(pose_path, "PNG")
        generated.append(f"{pose_name} (fallback)")

    if generated:
        print(f"[MASCOT] Generated {len(generated)} mascot poses: {', '.join(generated)}")
    else:
        print("[MASCOT] All mascot poses already exist")

    return generated


if __name__ == "__main__":
    # CLI: generate all mascot poses
    ensure_mascot_images()
