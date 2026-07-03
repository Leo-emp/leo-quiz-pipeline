# image_generator.py
# ============================================================
# AI image generation using Gemini Imagen.
# Generates cartoon-style quiz images on white backgrounds.
# Each image is a cute, kid-friendly illustration suitable
# for silhouette extraction and video compositing.
# ============================================================
from pathlib import Path

import config
from quiz_generator import QuizRound


def generate_quiz_image(round_data: QuizRound, output_path: Path) -> Path:
    """
    # Generate a cartoon quiz image for one round using Gemini Imagen.
    # Uses the image_prompt from the quiz round (customized by Gemini)
    # or falls back to the standard template.
    # Saves as 1024x1024 PNG with white background.
    """
    from google import genai
    from google.genai import types

    # Initialize Gemini client
    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Use the round's custom prompt, or generate from template
    prompt = round_data.image_prompt
    if not prompt:
        prompt = config.IMAGE_PROMPT_TEMPLATE.format(answer=round_data.answer)

    # Generate image via Gemini Imagen 3
    response = client.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,   # Only need one image per round
            aspect_ratio="1:1",   # Square for easy compositing
        ),
    )

    # Save the first generated image to disk
    if response.generated_images:
        image_data = response.generated_images[0].image.image_bytes
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(image_data)
        return output_path

    raise RuntimeError(f"Imagen failed to generate image for: {round_data.answer}")
