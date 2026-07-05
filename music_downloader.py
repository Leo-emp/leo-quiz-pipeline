# music_downloader.py
# ============================================================
# Auto-downloads royalty-free background music from Pixabay.
# Each quiz category gets a real music track instead of
# numpy-generated sine waves. Pixabay Music API is free
# (no API key needed), and all tracks are royalty-free for
# commercial use with attribution.
#
# Downloads on first run, then cached in assets/music/ forever.
# If a track already exists (user dropped in their own), skips it.
# ============================================================
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

import config


# --- Search terms per category ---
# Each category maps to a Pixabay music search query
# that returns upbeat, kid-friendly background tracks.
CATEGORY_SEARCH = {
    "animals": "happy kids playful ukulele",
    "dinosaurs": "epic adventure cinematic children",
    "space": "ambient dreamy electronic calm",
    "vehicles": "energetic upbeat fun driving",
    "fruits": "cheerful bright tropical happy",
    "flags": "world adventure upbeat positive",
}

# Pixabay API endpoint (no key needed for music search)
PIXABAY_MUSIC_API = "https://pixabay.com/api/videos/"
# Alternative: use their direct audio search page scraping
# since the official API doesn't have a music endpoint yet.
# We'll use their undocumented music CDN pattern instead.

# Curated free music URLs — hand-picked royalty-free tracks
# from Pixabay that match each category's mood.
# These are direct download links to CC0/Pixabay License tracks.
# If any link dies, the pipeline falls back to numpy-generated BGM.
CURATED_TRACKS = {
    "animals": {
        "url": "https://cdn.pixabay.com/download/audio/2022/10/25/audio_33f680db52.mp3",
        "name": "Happy Day",
        "artist": "Pixabay",
    },
    "dinosaurs": {
        "url": "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",
        "name": "Epic Adventure",
        "artist": "Pixabay",
    },
    "space": {
        "url": "https://cdn.pixabay.com/download/audio/2022/03/15/audio_5765e3458c.mp3",
        "name": "Ambient Dream",
        "artist": "Pixabay",
    },
    "vehicles": {
        "url": "https://cdn.pixabay.com/download/audio/2023/09/04/audio_98e0d46da4.mp3",
        "name": "Energetic Rock",
        "artist": "Pixabay",
    },
    "fruits": {
        "url": "https://cdn.pixabay.com/download/audio/2024/11/04/audio_54e103e8c1.mp3",
        "name": "Tropical Vibes",
        "artist": "Pixabay",
    },
    "flags": {
        "url": "https://cdn.pixabay.com/download/audio/2023/07/19/audio_e8a01e0e40.mp3",
        "name": "World Beat",
        "artist": "Pixabay",
    },
}


def _download_track(category: str) -> bool:
    """
    # Download a royalty-free music track for a specific category.
    # Saves as assets/music/{category}.mp3.
    # Returns True if successful, False on any error.
    """
    if category not in CURATED_TRACKS:
        print(f"[MUSIC] No curated track for category: {category}")
        return False

    track_info = CURATED_TRACKS[category]
    target_path = config.MUSIC_DIR / f"{category}.mp3"

    # Skip if already exists (user may have placed their own)
    if target_path.exists():
        return True

    url = track_info["url"]
    print(f"[MUSIC] Downloading {track_info['name']} for {category}...")

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "LeoQuiz-Pipeline/1.0",
            "Accept": "audio/mpeg, */*",
        })
        response = urllib.request.urlopen(req, timeout=60)
        audio_data = response.read()

        # Validate we got actual audio data (at least 10KB)
        if len(audio_data) < 10_000:
            print(f"[MUSIC] Downloaded file too small ({len(audio_data)} bytes), skipping")
            return False

        # Save the MP3 file
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(audio_data)
        size_kb = len(audio_data) // 1024
        print(f"[MUSIC] Saved {category}.mp3 ({size_kb}KB) — '{track_info['name']}'")
        return True

    except urllib.error.HTTPError as e:
        print(f"[MUSIC] HTTP error downloading {category}: {e.code} {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"[MUSIC] Network error downloading {category}: {e}")
        return False
    except Exception as e:
        print(f"[MUSIC] Unexpected error downloading {category}: {e}")
        return False


def _save_attribution():
    """
    # Save a MUSIC_CREDITS.txt file listing all downloaded tracks.
    # Important for royalty-free license compliance —
    # Pixabay License requires no attribution but it's good practice.
    """
    credits_path = config.MUSIC_DIR / "MUSIC_CREDITS.txt"
    if credits_path.exists():
        return

    lines = [
        "Leo Quiz — Background Music Credits",
        "=" * 45,
        "",
        "All tracks are royalty-free under the Pixabay License.",
        "Free for commercial use, no attribution required.",
        "https://pixabay.com/service/license-summary/",
        "",
    ]

    for category, info in CURATED_TRACKS.items():
        track_path = config.MUSIC_DIR / f"{category}.mp3"
        status = "downloaded" if track_path.exists() else "not downloaded"
        lines.append(f"  {category}: \"{info['name']}\" by {info['artist']} ({status})")

    lines.append("")
    lines.append("To replace any track, drop your own MP3/WAV into assets/music/")
    lines.append("using the category name (e.g., animals.mp3). The pipeline")
    lines.append("always prefers real files over generated fallbacks.")

    credits_path.parent.mkdir(parents=True, exist_ok=True)
    credits_path.write_text("\n".join(lines), encoding="utf-8")


def ensure_music():
    """
    # Download any missing background music tracks.
    # Called at pipeline startup, right after ensure_fonts().
    # Falls back gracefully to numpy-generated BGM if downloads fail.
    """
    config.MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    # Check what we already have — look for any real audio files
    existing = []
    missing = []
    for category in config.CATEGORIES:
        has_mp3 = (config.MUSIC_DIR / f"{category}.mp3").exists()
        has_wav = (config.MUSIC_DIR / f"{category}.wav").exists()
        if has_mp3 or has_wav:
            existing.append(category)
        else:
            missing.append(category)

    if not missing:
        print("[MUSIC] All category tracks already installed")
        return

    print(f"[MUSIC] Missing tracks for: {', '.join(missing)}")

    downloaded = []
    failed = []

    for category in missing:
        if _download_track(category):
            downloaded.append(category)
        else:
            failed.append(category)

    # Save attribution file
    _save_attribution()

    if downloaded:
        print(f"[MUSIC] Downloaded {len(downloaded)} tracks: {', '.join(downloaded)}")
    if failed:
        print(f"[MUSIC] Could not download: {', '.join(failed)} "
              "— pipeline will use generated BGM as fallback")


if __name__ == "__main__":
    ensure_music()
