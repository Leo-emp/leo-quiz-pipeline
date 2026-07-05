# font_downloader.py
# ============================================================
# Auto-downloads kid-friendly fonts from Google Fonts on first run.
# Baloo 2 (Bold) — rounded, playful, perfect for titles
# Fredoka One — thick, bubbly, great for countdown numbers
# Both are OFL-licensed (free for any use).
# ============================================================
import io
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

import config

# Google Fonts download API — returns ZIP with all weights
FONT_URLS = {
    "Baloo2": "https://fonts.google.com/download?family=Baloo+2",
    "FredokaOne": "https://fonts.google.com/download?family=Fredoka",
}

# Which specific file we want from each ZIP
FONT_FILE_MAP = {
    "Baloo2": {
        "target_name": "Baloo2-Bold.ttf",
        # Inside the ZIP, the bold weight may be named differently
        "search_patterns": ["Baloo2-Bold.ttf", "Baloo2-SemiBold.ttf",
                            "static/Baloo2-Bold.ttf", "Baloo2-ExtraBold.ttf"],
    },
    "FredokaOne": {
        "target_name": "FredokaOne-Regular.ttf",
        "search_patterns": ["FredokaOne-Regular.ttf", "Fredoka-SemiBold.ttf",
                            "static/Fredoka-SemiBold.ttf", "Fredoka-Bold.ttf",
                            "static/Fredoka-Bold.ttf"],
    },
}


def _download_and_extract(font_key: str) -> bool:
    """
    # Download a font family ZIP from Google Fonts and extract the
    # specific weight we need into assets/fonts/.
    # Returns True if successful.
    """
    url = FONT_URLS[font_key]
    file_info = FONT_FILE_MAP[font_key]
    target_path = config.FONTS_DIR / file_info["target_name"]

    if target_path.exists():
        return True  # Already have it

    print(f"[FONTS] Downloading {font_key} from Google Fonts...")
    try:
        # Download the ZIP file
        req = urllib.request.Request(url, headers={
            "User-Agent": "LeoQuiz-Pipeline/1.0"
        })
        response = urllib.request.urlopen(req, timeout=30)
        zip_data = response.read()

        # Open the ZIP and find the font file we need
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            # List all files in the ZIP for matching
            all_files = zf.namelist()

            # Try each search pattern to find our target file
            found = False
            for pattern in file_info["search_patterns"]:
                for zip_name in all_files:
                    if zip_name.endswith(pattern) or zip_name == pattern:
                        # Extract just this file
                        font_data = zf.read(zip_name)
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        target_path.write_bytes(font_data)
                        print(f"[FONTS] Saved {file_info['target_name']} "
                              f"({len(font_data) // 1024}KB)")
                        found = True
                        break
                if found:
                    break

            if not found:
                # Fallback: grab any .ttf file from the ZIP (bold preferred)
                ttf_files = [f for f in all_files if f.endswith(".ttf")]
                # Prefer files with "Bold" or "SemiBold" in the name
                bold_files = [f for f in ttf_files
                              if "Bold" in f or "SemiBold" in f]
                pick = bold_files[0] if bold_files else (ttf_files[0] if ttf_files else None)
                if pick:
                    font_data = zf.read(pick)
                    target_path.write_bytes(font_data)
                    print(f"[FONTS] Saved {file_info['target_name']} from {pick}")
                    found = True

            return found

    except urllib.error.URLError as e:
        print(f"[FONTS] Download failed for {font_key}: {e}")
        return False
    except zipfile.BadZipFile:
        print(f"[FONTS] Invalid ZIP received for {font_key}")
        return False
    except Exception as e:
        print(f"[FONTS] Unexpected error downloading {font_key}: {e}")
        return False


def _try_system_fonts() -> list[str]:
    """
    # Check if the required fonts are available as system fonts.
    # Returns list of font names that were found on the system.
    """
    from PIL import ImageFont
    found = []
    system_font_names = {
        "Baloo2-Bold.ttf": ["Baloo2-Bold", "Baloo 2 Bold", "Baloo2Bold"],
        "FredokaOne-Regular.ttf": ["FredokaOne-Regular", "Fredoka One",
                                    "FredokaOne", "Fredoka-SemiBold"],
    }

    for target_file, alt_names in system_font_names.items():
        target_path = config.FONTS_DIR / target_file
        if target_path.exists():
            found.append(target_file)
            continue

        # Try loading from system font directories
        for name in alt_names:
            try:
                font = ImageFont.truetype(f"{name}.ttf", 48)
                # If we can load it, copy it to our assets directory
                # (PIL doesn't expose the path, so we just note it works)
                found.append(target_file)
                print(f"[FONTS] Found {name} as system font")
                break
            except (OSError, IOError):
                continue

    return found


def ensure_fonts():
    """
    # Download any missing fonts from Google Fonts.
    # Called automatically at pipeline startup.
    # Falls back to system fonts, then to PIL default if download fails.
    """
    config.FONTS_DIR.mkdir(parents=True, exist_ok=True)

    # Check what we already have
    baloo_path = config.FONTS_DIR / "Baloo2-Bold.ttf"
    fredoka_path = config.FONTS_DIR / "FredokaOne-Regular.ttf"

    if baloo_path.exists() and fredoka_path.exists():
        print("[FONTS] All fonts already installed")
        return

    downloaded = []
    failed = []

    for font_key in FONT_URLS:
        target = FONT_FILE_MAP[font_key]["target_name"]
        if (config.FONTS_DIR / target).exists():
            continue

        if _download_and_extract(font_key):
            downloaded.append(target)
        else:
            failed.append(target)

    if downloaded:
        print(f"[FONTS] Downloaded {len(downloaded)} fonts: {', '.join(downloaded)}")
    if failed:
        print(f"[FONTS] Could not download: {', '.join(failed)} "
              "— pipeline will use system fonts as fallback")


if __name__ == "__main__":
    ensure_fonts()
