# font_downloader.py
# ============================================================
# Auto-downloads kid-friendly fonts from Google Fonts on first run.
# Baloo 2 (Bold) — rounded, playful, perfect for titles
# Fredoka One — thick, bubbly, great for countdown numbers
# Both are OFL-licensed (free for any use).
#
# FIXED: Uses Google Fonts CSS2 API with .ttf user-agent trick
# instead of ZIP endpoint (which was returning invalid ZIPs).
# ============================================================
import re
import urllib.request
import urllib.error
from pathlib import Path

import config

# Google Fonts CSS2 API — returns CSS with direct .ttf download URLs
# Using a legacy user-agent forces Google to serve .ttf instead of .woff2
FONT_CSS_URLS = {
    # Baloo 2 Bold weight (700) — rounded, kid-friendly title font
    "Baloo2-Bold.ttf": "https://fonts.googleapis.com/css2?family=Baloo+2:wght@700",
    # Fredoka Bold — thick, bubbly display font for numbers/headlines
    "FredokaOne-Regular.ttf": "https://fonts.googleapis.com/css2?family=Fredoka:wght@600",
}

# User-agent that triggers .ttf responses from Google Fonts
# (Modern browsers get .woff2 which PIL can't use)
LEGACY_UA = "Mozilla/4.0 (Windows NT 6.1) AppleWebKit/537.36"


def _download_font_via_css(target_name: str, css_url: str) -> bool:
    """
    # Download a font file using Google Fonts CSS2 API.
    # Step 1: Fetch CSS file (contains @font-face with .ttf URL)
    # Step 2: Extract the .ttf URL from the CSS
    # Step 3: Download the .ttf file directly
    # Returns True if successful.
    """
    target_path = config.FONTS_DIR / target_name

    # Already have this font — skip
    if target_path.exists():
        return True

    print(f"[FONTS] Downloading {target_name} via Google Fonts CSS API...")
    try:
        # Step 1: Fetch CSS with legacy user-agent to get .ttf URLs
        req = urllib.request.Request(css_url, headers={"User-Agent": LEGACY_UA})
        response = urllib.request.urlopen(req, timeout=15)
        css_text = response.read().decode("utf-8")

        # Step 2: Extract .ttf URL from @font-face src: url(...)
        # Pattern matches: url(https://fonts.gstatic.com/s/.../font.ttf)
        ttf_urls = re.findall(r'url\((https://fonts\.gstatic\.com/[^)]+\.ttf)\)', css_text)

        if not ttf_urls:
            print(f"[FONTS] No .ttf URL found in CSS for {target_name}")
            return False

        # Step 3: Download the .ttf file (use first match)
        ttf_url = ttf_urls[0]
        ttf_req = urllib.request.Request(ttf_url, headers={"User-Agent": LEGACY_UA})
        ttf_data = urllib.request.urlopen(ttf_req, timeout=30).read()

        # Save to assets/fonts/
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(ttf_data)
        print(f"[FONTS] Saved {target_name} ({len(ttf_data) // 1024}KB)")
        return True

    except urllib.error.URLError as e:
        print(f"[FONTS] Download failed for {target_name}: {e}")
        return False
    except Exception as e:
        print(f"[FONTS] Unexpected error downloading {target_name}: {e}")
        return False


def ensure_fonts():
    """
    # Download any missing fonts from Google Fonts.
    # Called automatically at pipeline startup.
    # Uses CSS2 API for reliable .ttf downloads.
    # Falls back to system Arial if downloads fail.
    """
    config.FONTS_DIR.mkdir(parents=True, exist_ok=True)

    # Check if all fonts are already present
    all_present = all(
        (config.FONTS_DIR / name).exists()
        for name in FONT_CSS_URLS
    )
    if all_present:
        print("[FONTS] All fonts already installed")
        return

    # Download each missing font
    downloaded = []
    failed = []
    for target_name, css_url in FONT_CSS_URLS.items():
        if (config.FONTS_DIR / target_name).exists():
            continue
        if _download_font_via_css(target_name, css_url):
            downloaded.append(target_name)
        else:
            failed.append(target_name)

    if downloaded:
        print(f"[FONTS] Downloaded {len(downloaded)} fonts: {', '.join(downloaded)}")
    if failed:
        print(f"[FONTS] Could not download: {', '.join(failed)} "
              "— pipeline will use system fonts as fallback")


if __name__ == "__main__":
    ensure_fonts()
