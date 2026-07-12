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
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# --- ElevenLabs voice tuning ---
# These settings make the voice sound energetic and natural for kids content.
# stability: lower = more expressive/varied, higher = more consistent
# similarity_boost: how closely to match the reference voice
# style: 0 = neutral, 1 = maximum expressiveness (only on v2 models)
# use_speaker_boost: enhances clarity for small speakers (phones, tablets)
ELEVENLABS_STABILITY = 0.35          # Low stability = more natural variation
ELEVENLABS_SIMILARITY_BOOST = 0.75   # Keep recognizable but allow expression
ELEVENLABS_STYLE = 0.45              # Moderate style for energetic delivery
ELEVENLABS_USE_SPEAKER_BOOST = True  # Kids watch on phones — boost clarity

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
ROUNDS_PER_SHORT = 6         # 6 rounds per short = ~66s total (TikTok requires 60s+ for monetization)
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

# --- Long-form video timing (8s per round, 16:9 landscape) ---
# Used by longform_assembler.py for daily 10-minute videos.
# Faster pace than shorts to keep kids engaged over 60 rounds.
LONGFORM_ROUND_DURATION = 8.0        # Each round is 8 seconds (vs 10 for shorts)
LONGFORM_ROUNDS = 60                  # 60 rounds for ~10 min total
LONGFORM_TIMER_SECONDS = 5            # 5-second visible countdown timer
LONGFORM_INTRO_DURATION = 3.0         # Intro: Leo waves + "60 QUESTIONS!" hype
LONGFORM_OUTRO_DURATION = 5.0         # Outro: final score + star rating + subscribe CTA
LONGFORM_SECTION_CARD_DURATION = 2.0  # Motivational milestone card duration (25/50/75%)

# Long-form round sub-timings (offsets within each 8s round)
# Every round uses identical timing — consistent pacing keeps kids engaged
LONGFORM_SILHOUETTE_START = 0.0       # Silhouette slides in
LONGFORM_COUNTDOWN_START = 0.5        # 5-second timer begins
LONGFORM_REVEAL_START = 5.5           # Answer reveals (after timer)
LONGFORM_FUN_FACT_START = 6.5         # Fun fact overlay
LONGFORM_TRANSITION_START = 7.7       # Transition to next round

# --- Mega quiz timing (7s per round, 16:9 landscape) ---
# Used for weekly 100-round mega quizzes (15-20 min).
# Even faster pace — pure rapid-fire guessing energy.
MEGA_ROUND_DURATION = 7.0             # Each round is 7 seconds
MEGA_ROUNDS = 100                     # 100 rounds for ~15 min total
MEGA_TIMER_SECONDS = 4                # 4-second countdown (faster pressure)
MEGA_INTRO_DURATION = 4.0             # Longer intro: "100 QUESTIONS!" + category showcase
MEGA_OUTRO_DURATION = 6.0             # Longer outro: big score + celebration

# Mega quiz round sub-timings (offsets within each 7s round)
# Same consistent pacing principle — every round identical
MEGA_SILHOUETTE_START = 0.0           # Fast slide-in
MEGA_COUNTDOWN_START = 0.3            # Timer starts almost immediately
MEGA_REVEAL_START = 4.8               # Quick reveal
MEGA_FUN_FACT_START = 5.6             # Brief fact overlay
MEGA_TRANSITION_START = 6.7           # Transition to next round

# --- Particle system ---
# Sparkle overlay parameters for premium depth
PARTICLE_COUNT = 30           # Number of floating sparkles (was 20, now denser)
PARTICLE_SIZE_MIN = 2         # Smallest sparkle (pixels)
PARTICLE_SIZE_MAX = 6         # Largest sparkle (pixels)
PARTICLE_OPACITY_MIN = 0.2    # Minimum sparkle opacity
PARTICLE_OPACITY_MAX = 0.6    # Maximum sparkle opacity

# --- Visual effects ---
# Confetti burst settings for reveal moments
CONFETTI_COUNT = 60           # Particles per burst
CONFETTI_DURATION = 1.5       # How long confetti stays visible (seconds)
# Screen shake on reveal and final countdown
SHAKE_DURATION = 0.3          # Shake duration (seconds)
SHAKE_INTENSITY = 12.0        # Max pixel offset
# Ken Burns zoom during silhouette phase
ZOOM_MAX = 1.06               # Max zoom level (1.06 = 6% zoom)
# Vignette (darkened edges for cinematic depth)
VIGNETTE_INTENSITY = 0.35     # 0.0 = none, 1.0 = heavy
# Glow effects on countdown numbers and reveal text
GLOW_RADIUS = 10              # Blur radius for text glow
# Progress indicator dots at bottom
PROGRESS_DOT_RADIUS = 8       # Size of each progress dot
PROGRESS_DOT_GAP = 30         # Spacing between dots

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
# Paths to SFX files (auto-generated by sfx_generator.py if missing)
SFX_FILES = {
    "tick": SFX_DIR / "tick.wav",
    "ding": SFX_DIR / "ding.wav",
    "whoosh": SFX_DIR / "whoosh.wav",
    "applause": SFX_DIR / "applause.wav",
    "drumroll": SFX_DIR / "drumroll.wav",
    "jingle_intro": SFX_DIR / "jingle_intro.wav",
    "jingle_outro": SFX_DIR / "jingle_outro.wav",
    "correct": SFX_DIR / "correct.wav",
    "countdown_beep": SFX_DIR / "countdown_beep.wav",
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
TITLE_FONT_SIZE = 68          # "GUESS THE ANIMAL" header (bumped from 64)
QUESTION_FONT_SIZE = 44       # Hint question text (slightly smaller for wrapping)
ANSWER_FONT_SIZE = 62         # "It's a Lion!" reveal text (bumped from 56)
FACT_FONT_SIZE = 32           # Fun fact text (smaller to fit wrapped lines)
COUNTDOWN_FONT_SIZE = 220     # Large 3-2-1 countdown (bumped from 200)
SCORE_FONT_SIZE = 40          # Score counter
CTA_FONT_SIZE = 52            # Subscribe/like call-to-action text
ROUND_LABEL_FONT_SIZE = 36    # "Round 3/5" label
TEXT_STROKE_WIDTH = 3         # Outline stroke for readability
TEXT_SHADOW_OFFSET = 3        # Drop shadow pixel offset (bumped from 2)
TEXT_SHADOW_OPACITY = 0.6     # Drop shadow transparency (bumped from 0.5)
TEXT_MAX_WIDTH_RATIO = 0.85   # Max text width as ratio of frame width

# ============================================================
# SPEED QUIZ FORMAT — Quiz Blitz style (top creator format)
# 120 rounds, 3-second timer, real photos, 16:9 landscape
# Based on research: Quiz Blitz (913K subs, 229M views)
# ============================================================

# --- Speed quiz structure ---
SPEED_ROUNDS = 120                     # 120 rounds total (proven format for millions of views)
SPEED_TIMER_SECONDS = 3                # 3-second guess window (creates urgency)
SPEED_ROUND_DURATION = 8.0             # 8s per round: 3s timer + 2s reveal + 2s fact + 1s transition
SPEED_INTRO_DURATION = 6.0             # Title card + subscribe prompt
SPEED_SUBSCRIBE_DURATION = 4.0         # "Subscribe before we start!" screen
SPEED_SECTION_CARD_DURATION = 3.0      # "EASY LEVEL" / "MEDIUM LEVEL" etc.
SPEED_OUTRO_DURATION = 7.0             # Score + subscribe CTA + Leo celebration

# --- Speed round sub-timings (offsets within each 8s round) ---
SPEED_PHOTO_START = 0.0                # Photo slides in immediately
SPEED_TIMER_START = 0.4                # Timer begins after photo settles
SPEED_REVEAL_START = 3.4               # Answer reveals after 3-second timer
SPEED_FACT_START = 5.0                 # Fun fact appears briefly
SPEED_TRANSITION_START = 7.5           # Quick crossfade to next round

# --- Difficulty tiers (30 rounds each = 120 total) ---
# Progression hooks viewers: easy start builds confidence, impossible creates challenge
SPEED_DIFFICULTIES = ["EASY", "MEDIUM", "HARD", "IMPOSSIBLE"]
SPEED_ROUNDS_PER_DIFFICULTY = 30       # 120 / 4 = 30 rounds per tier

# --- Speed quiz background colors ---
# Bright, saturated, kid-friendly — rotates every round for visual variety
# Directly observed from Quiz Blitz videos: amber, turquoise, blue, etc.
SPEED_BG_COLORS = [
    (41, 171, 226),    # sky blue (like Quiz Blitz intro)
    (255, 183, 27),    # golden amber (Quiz Blitz round 1)
    (0, 206, 186),     # turquoise mint (Quiz Blitz round 2)
    (255, 107, 107),   # coral red
    (142, 68, 173),    # purple
    (46, 204, 113),    # emerald green
    (255, 71, 87),     # hot pink
    (255, 165, 2),     # orange
    (52, 152, 219),    # ocean blue
    (241, 196, 15),    # bright yellow
    (231, 76, 60),     # warm red
    (26, 188, 156),    # teal
    (155, 89, 182),    # medium purple
    (243, 156, 18),    # amber
    (22, 160, 133),    # deep teal
]

# --- Speed quiz pattern types (per difficulty section) ---
# Subtle semi-transparent patterns behind content (observed in Quiz Blitz)
SPEED_PATTERNS = {
    "EASY": "clouds",        # soft, friendly (amber bg in Quiz Blitz)
    "MEDIUM": "stars",       # fun, energetic (turquoise bg in Quiz Blitz)
    "HARD": "question_marks", # mysterious, challenging
    "IMPOSSIBLE": "lightning", # intense, dramatic (like Quiz Blitz branding)
}

# --- Speed quiz difficulty sidebar colors ---
SPEED_DIFFICULTY_COLORS = {
    "EASY": (46, 204, 113),        # green badge (matches Quiz Blitz)
    "MEDIUM": (241, 196, 15),      # yellow
    "HARD": (231, 76, 60),         # red
    "IMPOSSIBLE": (142, 68, 173),  # purple
}

# --- Speed quiz round badge ---
SPEED_BADGE_COLOR = (233, 30, 99)  # pink/magenta circle (like Quiz Blitz)
SPEED_BADGE_RADIUS = 38            # badge circle radius in pixels

# --- Speed quiz typography ---
SPEED_TITLE_FONT_SIZE = 72         # "Guess The Animal" header
SPEED_ANSWER_FONT_SIZE = 68        # answer reveal text
SPEED_ROUND_NUM_FONT_SIZE = 42     # number inside badge
SPEED_DIFFICULTY_FONT_SIZE = 24    # sidebar difficulty labels
SPEED_TIMER_HEIGHT = 35            # timer bar height in pixels
SPEED_SECTION_FONT_SIZE = 110      # "EASY LEVEL" section card text
SPEED_BRANDING_FONT_SIZE = 22      # "LEO QUIZ" small branding

# --- Speed quiz photo card ---
SPEED_PHOTO_WIDTH = 700            # photo display width (fits naturally in 1920)
SPEED_PHOTO_HEIGHT = 480           # photo display height
SPEED_CARD_PADDING = 14            # white border around photo
SPEED_CARD_RADIUS = 18             # rounded corner radius
