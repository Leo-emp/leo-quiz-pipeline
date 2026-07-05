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
    # Draw a simple geometric lion mascot as a fallback.
    # Not as good as Gemini-generated art, but ensures the pipeline
    # always has a mascot to render even without API access.
    # Creates a cute circular lion face with basic features.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    body_r = size // 3         # Body radius
    head_r = size // 4         # Head radius

    # Mane (orange circle behind head)
    mane_r = int(head_r * 1.4)
    draw.ellipse([cx - mane_r, cy - body_r // 2 - mane_r,
                  cx + mane_r, cy - body_r // 2 + mane_r],
                 fill=(230, 150, 30, 255))

    # Head (golden circle)
    head_cy = cy - body_r // 3
    draw.ellipse([cx - head_r, head_cy - head_r,
                  cx + head_r, head_cy + head_r],
                 fill=(255, 210, 80, 255))

    # Body (golden oval below head)
    draw.ellipse([cx - body_r // 2, cy,
                  cx + body_r // 2, cy + body_r],
                 fill=(255, 210, 80, 255))

    # Eyes (big white circles with black pupils)
    eye_offset = head_r // 3
    eye_r = head_r // 5
    for sign in (-1, 1):
        # White of eye
        ex = cx + sign * eye_offset
        ey = head_cy - eye_r
        draw.ellipse([ex - eye_r, ey - eye_r, ex + eye_r, ey + eye_r],
                     fill=(255, 255, 255, 255))
        # Pupil — shifts based on pose
        pupil_r = eye_r // 2
        px_shift = 0
        py_shift = 0
        if pose == "thinking":
            py_shift = -pupil_r  # Looking up
        elif pose == "surprised":
            pupil_r = eye_r // 3  # Smaller pupils = surprise
        draw.ellipse([ex - pupil_r + px_shift, ey - pupil_r + py_shift,
                      ex + pupil_r + px_shift, ey + pupil_r + py_shift],
                     fill=(40, 40, 40, 255))

    # Nose (small brown triangle)
    nose_y = head_cy + head_r // 4
    nose_s = head_r // 6
    draw.polygon([(cx, nose_y), (cx - nose_s, nose_y + nose_s),
                  (cx + nose_s, nose_y + nose_s)],
                 fill=(160, 90, 40, 255))

    # Mouth — varies by pose
    mouth_y = nose_y + nose_s + 5
    if pose == "excited":
        # Big smile (arc)
        draw.arc([cx - head_r // 3, mouth_y - head_r // 6,
                  cx + head_r // 3, mouth_y + head_r // 4],
                 start=0, end=180, fill=(80, 40, 20, 255), width=3)
    elif pose == "surprised":
        # Open mouth (circle)
        mouth_r = head_r // 5
        draw.ellipse([cx - mouth_r, mouth_y - mouth_r // 2,
                      cx + mouth_r, mouth_y + mouth_r],
                     fill=(180, 80, 60, 255))
    elif pose == "thinking":
        # Slight frown (thinking)
        draw.line([(cx - head_r // 5, mouth_y + 3),
                   (cx + head_r // 5, mouth_y)],
                  fill=(80, 40, 20, 255), width=3)
    else:
        # Gentle smile (waving)
        draw.arc([cx - head_r // 4, mouth_y - head_r // 8,
                  cx + head_r // 4, mouth_y + head_r // 6],
                 start=0, end=180, fill=(80, 40, 20, 255), width=2)

    # Arms/paws — vary by pose
    arm_y = cy + body_r // 4
    paw_r = head_r // 4
    if pose == "waving":
        # Right arm raised up waving
        draw.line([(cx + body_r // 2, arm_y), (cx + body_r, arm_y - body_r // 2)],
                  fill=(255, 210, 80, 255), width=12)
        draw.ellipse([cx + body_r - paw_r, arm_y - body_r // 2 - paw_r,
                      cx + body_r + paw_r, arm_y - body_r // 2 + paw_r],
                     fill=(255, 210, 80, 255))
    elif pose == "excited":
        # Both arms raised
        for sign in (-1, 1):
            draw.line([(cx + sign * body_r // 2, arm_y),
                       (cx + sign * body_r, arm_y - body_r // 2)],
                      fill=(255, 210, 80, 255), width=12)
            draw.ellipse([cx + sign * body_r - paw_r, arm_y - body_r // 2 - paw_r,
                          cx + sign * body_r + paw_r, arm_y - body_r // 2 + paw_r],
                         fill=(255, 210, 80, 255))
    elif pose == "thinking":
        # One paw on chin
        draw.line([(cx + body_r // 2, arm_y),
                   (cx + body_r // 3, head_cy + head_r)],
                  fill=(255, 210, 80, 255), width=12)
    elif pose == "surprised":
        # Paws up in surprise
        for sign in (-1, 1):
            draw.line([(cx + sign * body_r // 2, arm_y),
                       (cx + sign * body_r // 1.5, arm_y - body_r // 4)],
                      fill=(255, 210, 80, 255), width=12)

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
