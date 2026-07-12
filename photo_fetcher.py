# photo_fetcher.py
# ============================================================
# Fetches real photos from Pexels API for speed quiz format.
# Top creators (Quiz Blitz, Monkey Quiz) use real photos — not
# cartoons — because the "guess from photo" format requires
# genuine images to create the recognition challenge.
#
# Pexels API: free, no attribution required, high quality.
# Falls back to a colored placeholder if API fails.
# ============================================================
import json
import random
import urllib.request
import urllib.parse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import io

import config


def fetch_photo(search_term: str, output_path: Path,
                orientation: str = "landscape") -> Path:
    """
    # Fetch a real photo from Pexels API by search term.
    # search_term: what to search for (e.g., "lion", "kangaroo")
    # Returns path to downloaded photo.
    # Picks randomly from top results for variety across videos.
    """
    if not config.PEXELS_API_KEY:
        print(f"[PHOTO] No PEXELS_API_KEY — using placeholder for: {search_term}")
        return _generate_placeholder(search_term, output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Build Pexels search URL
        params = urllib.parse.urlencode({
            "query": search_term,
            "per_page": 8,            # get 8 results to pick from
            "orientation": orientation, # landscape for 16:9 quiz
            "size": "large",           # high quality photos
        })
        url = f"https://api.pexels.com/v1/search?{params}"

        # Pexels requires API key in Authorization header
        req = urllib.request.Request(url, headers={
            "Authorization": config.PEXELS_API_KEY,
            "User-Agent": "LeoQuiz-Pipeline/2.0",
        })
        response = urllib.request.urlopen(req, timeout=15)
        data = json.loads(response.read().decode("utf-8"))

        photos = data.get("photos", [])
        if not photos:
            print(f"[PHOTO] No results for '{search_term}' — trying simpler query")
            # Retry with just the first word (e.g., "African elephant" → "elephant")
            simple_term = search_term.split()[0] if " " in search_term else search_term
            return _fetch_with_query(simple_term, output_path, orientation)

        # Pick randomly from top 3 results for variety
        # (avoids using the same photo every time for common animals)
        photo = random.choice(photos[:min(3, len(photos))])

        # Download the large2x version (highest quality available)
        img_url = photo["src"].get("large2x", photo["src"]["large"])
        return _download_image(img_url, output_path)

    except Exception as e:
        print(f"[PHOTO] Pexels API failed for '{search_term}': {e}")
        return _generate_placeholder(search_term, output_path)


def _fetch_with_query(query: str, output_path: Path,
                      orientation: str = "landscape") -> Path:
    """
    # Retry fetch with a simplified query.
    # Used when the full search term returns no results.
    """
    try:
        params = urllib.parse.urlencode({
            "query": query,
            "per_page": 5,
            "orientation": orientation,
            "size": "large",
        })
        url = f"https://api.pexels.com/v1/search?{params}"
        req = urllib.request.Request(url, headers={
            "Authorization": config.PEXELS_API_KEY,
        })
        response = urllib.request.urlopen(req, timeout=15)
        data = json.loads(response.read().decode("utf-8"))

        photos = data.get("photos", [])
        if photos:
            photo = random.choice(photos[:3])
            img_url = photo["src"].get("large2x", photo["src"]["large"])
            return _download_image(img_url, output_path)

    except Exception as e:
        print(f"[PHOTO] Retry also failed for '{query}': {e}")

    return _generate_placeholder(query, output_path)


def _download_image(img_url: str, output_path: Path) -> Path:
    """
    # Download an image URL and save to disk.
    # Converts to RGB PNG regardless of source format.
    """
    req = urllib.request.Request(img_url, headers={
        "User-Agent": "LeoQuiz-Pipeline/2.0",
    })
    img_data = urllib.request.urlopen(req, timeout=30).read()

    # Open with PIL to ensure valid image + convert to PNG
    img = Image.open(io.BytesIO(img_data)).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG")
    print(f"[PHOTO] Downloaded {output_path.name} ({img.width}x{img.height})")
    return output_path


def _generate_placeholder(answer: str, output_path: Path) -> Path:
    """
    # Generate a colored placeholder when Pexels is unavailable.
    # Uses a gradient background with the answer text centered.
    # Not ideal but keeps the pipeline running.
    """
    # Create a landscape placeholder with gradient
    w, h = 1200, 800
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)

    # Pick a random bright color for the gradient
    colors = config.SPEED_BG_COLORS
    bg_color = random.choice(colors)
    # Darker version for gradient bottom
    dark = tuple(max(0, c - 60) for c in bg_color)

    # Draw gradient
    for y in range(h):
        ratio = y / h
        r = int(bg_color[0] * (1 - ratio) + dark[0] * ratio)
        g = int(bg_color[1] * (1 - ratio) + dark[1] * ratio)
        b = int(bg_color[2] * (1 - ratio) + dark[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Draw question mark icon centered
    try:
        font = ImageFont.truetype("arial.ttf", 180)
    except OSError:
        font = ImageFont.load_default()
    draw.text((w // 2, h // 2 - 40), "?", fill=(255, 255, 255), anchor="mm", font=font)

    # Draw answer name at bottom (for debugging — won't show in final video
    # since the photo card crops to fit)
    try:
        small_font = ImageFont.truetype("arial.ttf", 36)
    except OSError:
        small_font = ImageFont.load_default()
    draw.text((w // 2, h - 60), answer, fill=(255, 255, 255, 180),
              anchor="mm", font=small_font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG")
    return output_path


def fetch_photos_batch(rounds_data: list, output_dir: Path) -> list[Path]:
    """
    # Fetch photos for all rounds in a quiz pack.
    # Uses the answer field as the Pexels search term.
    # Returns list of photo file paths in round order.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    photo_paths = []

    for i, rd in enumerate(rounds_data):
        photo_path = output_dir / f"round_{i+1}_photo.png"

        # Skip if already downloaded (for re-runs)
        if photo_path.exists():
            print(f"[PHOTO] Already have photo for round {i+1}: {rd.answer}")
            photo_paths.append(photo_path)
            continue

        # Use the answer as search term (e.g., "Lion", "Kangaroo")
        # For better results, use pexels_search if available
        search_term = getattr(rd, 'pexels_search', None) or rd.answer
        print(f"[PHOTO] Fetching photo {i+1}/{len(rounds_data)}: {search_term}")
        path = fetch_photo(search_term, photo_path)
        photo_paths.append(path)

    return photo_paths
