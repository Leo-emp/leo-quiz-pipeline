# image_generator.py
# ============================================================
# AI image generation using Gemini Flash with native image output.
# Generates cartoon-style quiz images on white backgrounds.
# Each image is a cute, kid-friendly illustration suitable
# for silhouette extraction and video compositing.
# Falls back to Imagen 4 if available, then to PIL placeholder.
# ============================================================
import io
from pathlib import Path

from PIL import Image, ImageDraw

import config
from quiz_generator import QuizRound


def generate_quiz_image(round_data: QuizRound, output_path: Path) -> Path:
    """
    # Generate a cartoon quiz image for one round.
    # Priority: Gemini Flash image gen → Imagen 4 API → PIL placeholder.
    # Saves as PNG with white background.
    """
    prompt = round_data.image_prompt
    if not prompt:
        prompt = config.IMAGE_PROMPT_TEMPLATE.format(answer=round_data.answer)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Try Gemini Flash image generation (works on free tier) ---
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


def _generate_with_gemini_flash(prompt: str, output_path: Path) -> Path:
    # Gemini 2.5 Flash can generate images via generate_content
    # when response_modalities includes "image"
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-05-20",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["image", "text"],
        ),
    )

    # Extract image from response parts
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            img = Image.open(io.BytesIO(part.inline_data.data))
            img.save(str(output_path), "PNG")
            return output_path

    raise RuntimeError("No image in Gemini Flash response")


def _generate_with_imagen(prompt: str, output_path: Path) -> Path:
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
    # Simple colored circle with text on white background
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
