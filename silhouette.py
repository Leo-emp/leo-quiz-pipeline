# silhouette.py
# ============================================================
# Silhouette extraction from AI-generated quiz images.
# Converts a cartoon image on white background into a pure
# black silhouette with transparent background.
# Used for the "guess what this is" mystery phase of each round.
# ============================================================
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter


def extract_silhouette(image_path: Path, output_path: Path,
                       threshold: int = 240, blur_radius: float = 1.5) -> Path:
    """
    # Extract a black silhouette from a white-background image.
    # Steps:
    # 1. Convert to grayscale
    # 2. Threshold: anything not-white becomes subject
    # 3. Smooth edges with slight Gaussian blur
    # 4. Output: pure black shape on transparent background (RGBA)
    """
    # Open image and convert to RGB for consistent processing
    img = Image.open(image_path).convert("RGB")

    # Convert to grayscale for thresholding
    gray = img.convert("L")
    gray_arr = np.array(gray)

    # Threshold: pixels darker than threshold = subject (255), lighter = background (0)
    mask = (gray_arr < threshold).astype(np.uint8) * 255

    # Smooth edges with Gaussian blur to remove jagged aliasing
    mask_img = Image.fromarray(mask)
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Re-threshold after blur to keep edges clean but smooth
    mask_arr = np.array(mask_img)
    mask_arr = ((mask_arr > 128).astype(np.uint8)) * 255

    # Create RGBA output: pure black where subject is, transparent elsewhere
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    result_arr = np.array(result)

    # Set all channels: black (0,0,0) with alpha from mask
    result_arr[:, :, 0] = 0         # R = 0 (black)
    result_arr[:, :, 1] = 0         # G = 0 (black)
    result_arr[:, :, 2] = 0         # B = 0 (black)
    result_arr[:, :, 3] = mask_arr  # Alpha = mask (opaque where subject is)

    result = Image.fromarray(result_arr)
    result.save(output_path, "PNG")
    return output_path


def validate_silhouette(silhouette_path: Path,
                        min_coverage: float = 0.05,
                        max_coverage: float = 0.80) -> bool:
    """
    # Validate that a silhouette is recognizable.
    # Checks that the opaque area is between 5% and 80% of total pixels.
    # Too small = unrecognizable shape, too large = bad background extraction.
    """
    img = Image.open(silhouette_path).convert("RGBA")
    arr = np.array(img)

    # Count opaque pixels (alpha > 128)
    opaque_pixels = np.sum(arr[:, :, 3] > 128)
    total_pixels = arr.shape[0] * arr.shape[1]
    coverage = opaque_pixels / total_pixels

    # Valid if coverage falls within acceptable range (cast to native bool)
    return bool(min_coverage <= coverage <= max_coverage)
