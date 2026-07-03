# config.py
# ============================================================
# Central configuration for Leo Quiz pipeline.
# All constants, paths, colors, and timing values live here.
# ============================================================
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Project paths ---
# All paths are relative to this file's location
PROJECT_ROOT = Path(__file__).parent
ASSETS_DIR = PROJECT_ROOT / "assets"
MASCOT_DIR = ASSETS_DIR / "mascot"
SFX_DIR = ASSETS_DIR / "sfx"
MUSIC_DIR = ASSETS_DIR / "music"
FONTS_DIR = ASSETS_DIR / "fonts"
OUTPUT_DIR = PROJECT_ROOT / "output"
SHORTS_DIR = OUTPUT_DIR / "shorts"
LONGFORM_DIR = OUTPUT_DIR / "longform"
HISTORY_FILE = PROJECT_ROOT / "history.json"

# --- API keys (loaded from .env) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

# --- Video dimensions ---
SHORTS_SIZE = (1080, 1920)   # 9:16 vertical for YouTube Shorts / TikTok
LONGFORM_SIZE = (1920, 1080) # 16:9 horizontal for YouTube long-form
FPS = 30                     # Frames per second
VIDEO_BITRATE = "5000k"      # H.264 bitrate for shorts
LONGFORM_BITRATE = "8000k"   # Higher bitrate for long-form
AUDIO_BITRATE = "192k"       # AAC audio bitrate
AUDIO_PEAK_DB = -3.0         # Peak normalization target

# --- Timing (seconds) ---
# Overall video structure timing
INTRO_DURATION = 2.0         # Leo waves, title appears
OUTRO_DURATION = 4.0         # Score recap, subscribe CTA
ROUND_DURATION = 10.0        # Each quiz round is 10 seconds
ROUNDS_PER_SHORT = 5         # 5 rounds per short = ~56s total
COUNTDOWN_SECONDS = 3        # 3-2-1 countdown

# --- Round sub-timings (offsets within each 10s round) ---
SILHOUETTE_START = 0.0       # Silhouette slides in
SILHOUETTE_DURATION = 2.0    # Visible before countdown
COUNTDOWN_START = 2.0        # 3-2-1 begins
REVEAL_START = 5.0           # Answer reveals
REVEAL_DURATION = 1.5        # Reveal visible before fact
FUN_FACT_START = 6.5         # Fun fact appears
FUN_FACT_DURATION = 2.5      # Fun fact visible
SCORE_UPDATE_TIME = 9.0      # Score counter updates
TRANSITION_START = 9.5       # Transition to next round
TRANSITION_DURATION = 0.3    # Crossfade between rounds

# --- Animation durations (seconds) ---
# Penner easing function durations for each animation type
EASE_SLIDE_IN = 0.4          # CubicEaseOut slide-in
EASE_SLIDE_OUT = 0.25        # CubicEaseIn slide-out
EASE_COUNTDOWN_IN = 0.35     # BackEaseOut number pop
EASE_COUNTDOWN_OUT = 0.15    # Quick shrink
EASE_REVEAL = 0.5            # ElasticEaseOut image reveal
EASE_SCORE = 0.3             # BounceEaseOut score update
EASE_POSE_SWAP = 0.2         # Quick mascot pose swap
EASE_TRANSITION = 0.3        # Crossfade duration
EASE_TEXT_IN = 0.3            # Text fade-in
EASE_ANSWER_IN = 0.4          # Answer text pop-in

# --- Particle system ---
# Sparkle overlay parameters for premium depth
PARTICLE_COUNT = 20           # Number of floating sparkles
PARTICLE_SIZE_MIN = 2         # Smallest sparkle (pixels)
PARTICLE_SIZE_MAX = 6         # Largest sparkle (pixels)
PARTICLE_OPACITY_MIN = 0.2    # Minimum sparkle opacity
PARTICLE_OPACITY_MAX = 0.6    # Maximum sparkle opacity

# --- Categories ---
# Each category has a display name and keywords for Gemini prompts
CATEGORIES = {
    "animals": {"display": "Animal", "prompt_hint": "real animals from around the world"},
    "dinosaurs": {"display": "Dinosaur", "prompt_hint": "dinosaurs and prehistoric creatures"},
    "space": {"display": "Space Object", "prompt_hint": "planets, moons, stars, spacecraft, and space phenomena"},
    "vehicles": {"display": "Vehicle", "prompt_hint": "cars, planes, ships, trains, construction and military vehicles"},
    "fruits": {"display": "Fruit or Vegetable", "prompt_hint": "fruits and vegetables from around the world"},
    "flags": {"display": "Country Flag", "prompt_hint": "country flags and the countries they represent"},
}

# --- Category color themes ---
# Each category gets its own gradient for backgrounds and UI elements
CATEGORY_COLORS = {
    "animals":   {"primary": "#2ECC71", "secondary": "#27AE60", "gradient": ("green", "teal")},
    "dinosaurs": {"primary": "#E67E22", "secondary": "#D35400", "gradient": ("orange", "darkred")},
    "space":     {"primary": "#3498DB", "secondary": "#8E44AD", "gradient": ("deepblue", "purple")},
    "vehicles":  {"primary": "#E74C3C", "secondary": "#7F8C8D", "gradient": ("red", "darkgrey")},
    "fruits":    {"primary": "#F1C40F", "secondary": "#E91E63", "gradient": ("yellow", "pink")},
    "flags":     {"primary": "#9B59B6", "secondary": "#1ABC9C", "gradient": ("purple", "teal")},
}

# --- Day-of-week category rotation ---
# Monday=0, Sunday=6
DAY_CATEGORY_MAP = {
    0: "animals",
    1: "dinosaurs",
    2: "space",
    3: "vehicles",
    4: "fruits",
    5: "flags",
    6: "mixed",  # Sunday = mixed (random pick from all)
}


def get_today_category() -> str:
    """# Return today's category based on day of week rotation."""
    import random
    day = datetime.now().weekday()
    category = DAY_CATEGORY_MAP[day]
    # Sunday is "mixed" — randomly pick from all categories
    if category == "mixed":
        category = random.choice(list(CATEGORIES.keys()))
    return category


# --- Leo mascot poses ---
# Paths to pre-generated mascot images (4 poses)
MASCOT_POSES = {
    "thinking": MASCOT_DIR / "thinking.png",
    "excited": MASCOT_DIR / "excited.png",
    "waving": MASCOT_DIR / "waving.png",
    "surprised": MASCOT_DIR / "surprised.png",
}

# --- Sound effects ---
# Paths to bundled SFX files
SFX_FILES = {
    "tick": SFX_DIR / "tick.wav",
    "ding": SFX_DIR / "ding.wav",
    "whoosh": SFX_DIR / "whoosh.wav",
    "applause": SFX_DIR / "applause.wav",
    "drumroll": SFX_DIR / "drumroll.wav",
    "jingle_intro": SFX_DIR / "jingle_intro.wav",
    "jingle_outro": SFX_DIR / "jingle_outro.wav",
}

# --- Gemini image prompt template ---
# Used when a quiz round doesn't have a custom image_prompt
IMAGE_PROMPT_TEMPLATE = (
    "Cute colorful cartoon illustration of a {answer}, kid-friendly style, "
    "bright vibrant colors, clean edges, full body view, centered, "
    "pure white background, no text, no watermark, high quality, "
    "children's book illustration style"
)

# --- Typography ---
# Font sizes for different text elements (in pixels)
TITLE_FONT_SIZE = 64          # "GUESS THE ANIMAL" header
QUESTION_FONT_SIZE = 48       # Hint question text
ANSWER_FONT_SIZE = 56         # "It's a Lion!" reveal text
FACT_FONT_SIZE = 36           # Fun fact text
COUNTDOWN_FONT_SIZE = 200     # Large 3-2-1 countdown
SCORE_FONT_SIZE = 40          # Score counter
TEXT_STROKE_WIDTH = 3         # Outline stroke for readability
TEXT_SHADOW_OFFSET = 2        # Drop shadow pixel offset
TEXT_SHADOW_OPACITY = 0.5     # Drop shadow transparency
