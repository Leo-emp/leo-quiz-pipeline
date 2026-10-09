# image_generator.py
# ============================================================
# AI image generation for Leo Quiz.
# Generates cartoon-style quiz images on white backgrounds.
# Each image is a cute, kid-friendly illustration suitable
# for silhouette extraction and video compositing.
#
# PRIORITY ORDER:
#   1. Flux Pro v1.1 Ultra (fal.ai) — highest quality, consistent style
#   2. Gemini Flash — free tier, good quality
#   3. Imagen 4 — requires paid Gemini plan
#   4. PIL placeholder — colored circle with text (last resort)
#
# Flux Pro uses a locked kids illustration style suffix so every
# image in the video shares the same art style. No random AI salad.
# ============================================================
import io
import os
import requests
from pathlib import Path

from PIL import Image, ImageDraw

import config
from quiz_generator import QuizRound

# ============================================================
# FLUX PRO STYLE SUFFIX — Kids Cartoon Illustration
# ============================================================
# Appended to EVERY Flux prompt for visual consistency.
# Locked art direction: vibrant children's book illustrations
# with clean edges, white background, centered composition.
# This makes every frame look like it belongs in the same video.
FLUX_STYLE_SUFFIX = (
    "Children's book illustration style, vibrant flat colors, "
    "clean vector-like edges, cute and friendly appearance, "
    "solid pure white background, soft even studio lighting, "
    "front-facing centered composition, full body visible, "
    "high contrast for easy silhouette extraction, "
    "no text, no watermark, no shadows on background, "
    "highly detailed, professional illustration quality, 8K"
)


def generate_quiz_image(round_data: QuizRound, output_path: Path) -> Path:
    """
    # Generate a cartoon quiz image for one round.
    # Priority: Flux Pro → Gemini Flash → Imagen 4 → PIL placeholder.
    # Saves as 1024x1024 PNG with white background.
    """
    # --- Build the base prompt from round data ---
    prompt = round_data.image_prompt
    if not prompt:
        prompt = config.IMAGE_PROMPT_TEMPLATE.format(answer=round_data.answer)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Try Flux Pro first (best quality + consistent style) ---
    fal_key = os.getenv("FAL_KEY", "")
    if fal_key:
        try:
            return _generate_with_flux_pro(prompt, output_path, fal_key)
        except Exception as e:
            print(f"[IMAGE] Flux Pro failed: {e}")

    # --- Try Gemini Flash image generation (free tier fallback) ---
    try:
        return _generate_with_gemini_flash(prompt, output_path)
    except Exception as e:
        print(f"[IMAGE] Gemini Flash image gen failed: {e}")

    # --- Try Imagen 4 API (requires paid plan) ---
    try:
        return _generate_with_imagen(prompt, output_path)
    except Exception as e:
        print(f"[IMAGE] Imagen 4 failed: {e}")

    # --- PIL placeholder as last resort ---
    print(f"[IMAGE] Using PIL placeholder for: {round_data.answer}")
    return _generate_placeholder(round_data.answer, output_path)


def _generate_with_flux_pro(prompt: str, output_path: Path, fal_key: str) -> Path:
    """
    # Generates image via fal.ai Flux Pro v1.1 Ultra.
    # Appends the locked kids style suffix for consistency.
    # 1:1 aspect ratio, 1024x1024, PNG output.
    # Cost: ~$0.06 per image.
    """
    # --- Import fal client ---
    try:
        import fal_client
    except ImportError:
        try:
            import fal as fal_client
        except ImportError:
            raise RuntimeError("fal-client not installed. Run: pip install fal-client")

    # --- Build full prompt with style lock ---
    full_prompt = f"{prompt}. {FLUX_STYLE_SUFFIX}"

    # --- Set FAL_KEY for the client ---
    os.environ["FAL_KEY"] = fal_key

    print(f"[IMAGE] Flux Pro: {prompt[:60]}...")

    # --- Call Flux Pro v1.1 Ultra ---
    result = fal_client.subscribe(
        "fal-ai/flux-pro/v1.1-ultra",
        arguments={
            "prompt": full_prompt,
            "aspect_ratio": "1:1",
            "num_images": 1,
            "output_format": "png",
            # --- raw=True for more natural, less over-processed look ---
            "raw": True,
            # --- safety_tolerance 5 = permissive (no false blocks on animals) ---
            "safety_tolerance": "5",
        },
    )

    # --- Download the generated image ---
    if result and "images" in result and len(result["images"]) > 0:
        img_url = result["images"][0]["url"]
        resp = requests.get(img_url, timeout=30)
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            # --- Verify the image is valid and resize to 1024x1024 ---
            img = Image.open(output_path)
            if img.size != (1024, 1024):
                img = img.resize((1024, 1024), Image.LANCZOS)
                img.save(str(output_path), "PNG")
            file_kb = os.path.getsize(output_path) / 1024
            print(f"[IMAGE] Flux Pro saved: {output_path.name} ({file_kb:.0f} KB)")
            return output_path

    raise RuntimeError("Flux Pro returned empty result")


def _generate_with_gemini_flash(prompt: str, output_path: Path) -> Path:
    """
    # Gemini Flash can generate images via generate_content
    # when response_modalities includes "image".
    # Free tier compatible, good quality but less consistent.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Retry on 503 overload (Gemini Flash gets hammered)
    import time as _time
    response = None
    for _attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["image", "text"],
                ),
            )
            break
        except Exception as _e:
            if "503" in str(_e) or "UNAVAILABLE" in str(_e):
                wait = 10 * (_attempt + 1)
                print(f"[IMAGE] Gemini 503 — retrying in {wait}s (attempt {_attempt + 2}/3)")
                _time.sleep(wait)
            else:
                raise
    if response is None:
        raise RuntimeError("Gemini Flash unavailable after 3 retries")

    # --- Extract image from response parts ---
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            img = Image.open(io.BytesIO(part.inline_data.data))
            img.save(str(output_path), "PNG")
            return output_path

    raise RuntimeError("No image in Gemini Flash response")


def _generate_with_imagen(prompt: str, output_path: Path) -> Path:
    """
    # Imagen 4 API — requires paid Gemini plan.
    # Good quality but costs more per image than Flux Pro.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    response = client.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="1:1",
        ),
    )

    if response.generated_images:
        image_data = response.generated_images[0].image.image_bytes
        with open(output_path, "wb") as f:
            f.write(image_data)
        return output_path

    raise RuntimeError("Imagen returned no images")


def _generate_placeholder(answer: str, output_path: Path) -> Path:
    """
    # PIL placeholder — colored circle with text on white background.
    # Used when all AI image generators fail (no API keys, rate limits).
    # Still produces a valid image that the pipeline can process.
    """
    img = Image.new("RGB", (1024, 1024), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([212, 212, 812, 812], fill=(255, 210, 80))
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("arial.ttf", 64)
    except (OSError, IOError):
        font = ImageFont.load_default()
    draw.text((512, 512), answer, fill=(0, 0, 0), anchor="mm", font=font)
    img.save(str(output_path), "PNG")
    return output_path
