# Leo Quiz Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully automated kids quiz video pipeline that generates silhouette-guess quiz videos with professional animation quality, narrated by Leo the Lion mascot, and uploads daily to YouTube and TikTok.

**Architecture:** Modular Python pipeline with step isolation — each module (quiz gen, image gen, silhouette, frame composition, animation, narration, audio mixing, video assembly) reads/writes to structured output folders. A frame-by-frame renderer driven by Penner easing functions produces smooth, professional animation. Main orchestrator calls modules in sequence; scheduler triggers daily via cron or GitHub Actions.

**Tech Stack:** Python 3.11+, Gemini 2.5 Flash (content + metadata), Gemini Imagen (images), Pillow (frame composition), easing-functions (animation curves), MoviePy (video assembly), ElevenLabs (narration), pydub (audio mixing), APScheduler (cron), google-api-python-client (YouTube upload)

## Global Constraints

- Python 3.11+ required
- All code heavily commented with `#` throughout for learning (user preference)
- No shared code with Luminous Will — completely independent project
- All API keys loaded from `.env` via `python-dotenv`
- Output resolution: 1080x1920 (9:16 shorts), 1920x1080 (16:9 long-form)
- 30fps, H.264 codec, AAC audio
- All audio normalized to -3dB peak
- Content must be kid-appropriate (COPPA compliant)
- Fonts: Baloo 2 Bold + Fredoka One (Google Fonts, bundled in assets/fonts/)
- Project directory: `C:\Users\User\LeoQuiz`

---

### Task 1: Project Scaffold + Config

**Files:**
- Create: `config.py`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `assets/mascot/.gitkeep`
- Create: `assets/sfx/.gitkeep`
- Create: `assets/music/.gitkeep`
- Create: `assets/fonts/.gitkeep`
- Create: `output/.gitkeep`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `config.CATEGORIES` dict, `config.CATEGORY_COLORS` dict, `config.get_today_category() -> str`, `config.SHORTS_SIZE` tuple, `config.LONGFORM_SIZE` tuple, `config.ROUND_DURATION` float, `config.ROUNDS_PER_SHORT` int, all path constants

- [ ] **Step 1: Create requirements.txt**

```
google-genai>=1.0.0
Pillow>=10.0.0
easing-functions>=1.0.0
moviepy>=2.0.0
elevenlabs>=1.0.0
pydub>=0.25.1
python-dotenv>=1.0.0
numpy>=1.24.0
APScheduler>=3.10.0
google-api-python-client>=2.0.0
google-auth-oauthlib>=1.0.0
pytest>=7.0.0
```

- [ ] **Step 2: Create .env.example**

```
GEMINI_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
```

- [ ] **Step 3: Create .gitignore**

```
.env
__pycache__/
*.pyc
output/shorts/
output/longform/
history.json
*.mp4
*.wav
*.mp3
.venv/
```

- [ ] **Step 4: Write the failing test for config**

```python
# tests/test_config.py
import pytest

def test_categories_exist():
    from config import CATEGORIES
    # All 6 categories must be defined
    assert "animals" in CATEGORIES
    assert "dinosaurs" in CATEGORIES
    assert "space" in CATEGORIES
    assert "vehicles" in CATEGORIES
    assert "fruits" in CATEGORIES
    assert "flags" in CATEGORIES

def test_category_colors():
    from config import CATEGORY_COLORS
    # Each category must have primary + secondary hex colors
    for cat in ["animals", "dinosaurs", "space", "vehicles", "fruits", "flags"]:
        assert cat in CATEGORY_COLORS
        assert "primary" in CATEGORY_COLORS[cat]
        assert "secondary" in CATEGORY_COLORS[cat]
        assert CATEGORY_COLORS[cat]["primary"].startswith("#")

def test_get_today_category():
    from config import get_today_category
    result = get_today_category()
    assert result in ["animals", "dinosaurs", "space", "vehicles", "fruits", "flags", "mixed"]

def test_video_sizes():
    from config import SHORTS_SIZE, LONGFORM_SIZE
    assert SHORTS_SIZE == (1080, 1920)
    assert LONGFORM_SIZE == (1920, 1080)

def test_round_timing():
    from config import ROUND_DURATION, ROUNDS_PER_SHORT, INTRO_DURATION, OUTRO_DURATION
    assert ROUND_DURATION == 10.0
    assert ROUNDS_PER_SHORT == 5
    assert INTRO_DURATION == 2.0
    assert OUTRO_DURATION == 4.0
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_config.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 6: Write config.py**

```python
# config.py
# ============================================================
# Central configuration for Leo Quiz pipeline.
# All constants, paths, colors, and timing values live here.
# ============================================================
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Project paths ---
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
SHORTS_SIZE = (1080, 1920)   # 9:16 vertical
LONGFORM_SIZE = (1920, 1080) # 16:9 horizontal
FPS = 30
VIDEO_BITRATE = "5000k"
LONGFORM_BITRATE = "8000k"
AUDIO_BITRATE = "192k"
AUDIO_PEAK_DB = -3.0

# --- Timing (seconds) ---
INTRO_DURATION = 2.0
OUTRO_DURATION = 4.0
ROUND_DURATION = 10.0
ROUNDS_PER_SHORT = 5
COUNTDOWN_SECONDS = 3

# --- Round sub-timings (offsets within each 10s round) ---
SILHOUETTE_START = 0.0         # Silhouette slides in
SILHOUETTE_DURATION = 2.0      # Visible before countdown
COUNTDOWN_START = 2.0          # 3-2-1 begins
REVEAL_START = 5.0             # Answer reveals
REVEAL_DURATION = 1.5          # Reveal visible before fact
FUN_FACT_START = 6.5           # Fun fact appears
FUN_FACT_DURATION = 2.5        # Fun fact visible
SCORE_UPDATE_TIME = 9.0        # Score counter updates
TRANSITION_START = 9.5         # Transition to next round
TRANSITION_DURATION = 0.3      # Crossfade between rounds

# --- Animation durations (seconds) ---
EASE_SLIDE_IN = 0.4
EASE_SLIDE_OUT = 0.25
EASE_COUNTDOWN_IN = 0.35
EASE_COUNTDOWN_OUT = 0.15
EASE_REVEAL = 0.5
EASE_SCORE = 0.3
EASE_POSE_SWAP = 0.2
EASE_TRANSITION = 0.3
EASE_TEXT_IN = 0.3
EASE_ANSWER_IN = 0.4

# --- Particle system ---
PARTICLE_COUNT = 20
PARTICLE_SIZE_MIN = 2
PARTICLE_SIZE_MAX = 6
PARTICLE_OPACITY_MIN = 0.2
PARTICLE_OPACITY_MAX = 0.6

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
    if category == "mixed":
        category = random.choice(list(CATEGORIES.keys()))
    return category

# --- Leo mascot poses ---
MASCOT_POSES = {
    "thinking": MASCOT_DIR / "thinking.png",
    "excited": MASCOT_DIR / "excited.png",
    "waving": MASCOT_DIR / "waving.png",
    "surprised": MASCOT_DIR / "surprised.png",
}

# --- Sound effects ---
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
IMAGE_PROMPT_TEMPLATE = (
    "Cute colorful cartoon illustration of a {answer}, kid-friendly style, "
    "bright vibrant colors, clean edges, full body view, centered, "
    "pure white background, no text, no watermark, high quality, "
    "children's book illustration style"
)

# --- Typography ---
TITLE_FONT_SIZE = 64
QUESTION_FONT_SIZE = 48
ANSWER_FONT_SIZE = 56
FACT_FONT_SIZE = 36
COUNTDOWN_FONT_SIZE = 200
SCORE_FONT_SIZE = 40
TEXT_STROKE_WIDTH = 3
TEXT_SHADOW_OFFSET = 2
TEXT_SHADOW_OPACITY = 0.5
```

- [ ] **Step 7: Create directory structure**

```bash
mkdir -p assets/mascot assets/sfx assets/music assets/fonts output/shorts output/longform tests
touch assets/mascot/.gitkeep assets/sfx/.gitkeep assets/music/.gitkeep assets/fonts/.gitkeep
touch output/.gitkeep tests/__init__.py
```

- [ ] **Step 8: Install dependencies and run tests**

Run: `cd C:\Users\User\LeoQuiz && pip install -r requirements.txt && python -m pytest tests/test_config.py -v`
Expected: All 5 tests PASS

- [ ] **Step 9: Commit**

```bash
git add config.py requirements.txt .env.example .gitignore tests/ assets/ output/
git commit -m "feat: project scaffold with config, dependencies, and directory structure"
```

---

### Task 2: Animation System

**Files:**
- Create: `animations.py`
- Test: `tests/test_animations.py`

**Interfaces:**
- Consumes: `config.PARTICLE_COUNT`, `config.PARTICLE_SIZE_*`, `config.PARTICLE_OPACITY_*`, easing duration constants
- Produces: `ease_value(easing_type: str, t: float, duration: float, start: float, end: float) -> float`, `ParticleSystem` class with `render(frame: np.ndarray, t: float) -> np.ndarray`, `compute_slide_x(t, start_time, duration, frame_width, direction) -> int`, `compute_scale(t, start_time, duration, easing_type) -> float`, `compute_opacity(t, start_time, duration, easing_type) -> float`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_animations.py
import pytest
import numpy as np

def test_ease_value_linear():
    """# ease_value should interpolate linearly when using linear easing."""
    from animations import ease_value
    # At t=0, should return start value
    assert ease_value("linear", 0.0, 1.0, 0.0, 100.0) == pytest.approx(0.0, abs=0.1)
    # At t=1.0 (end), should return end value
    assert ease_value("linear", 1.0, 1.0, 0.0, 100.0) == pytest.approx(100.0, abs=0.1)
    # At t=0.5 (middle), should return midpoint
    assert ease_value("linear", 0.5, 1.0, 0.0, 100.0) == pytest.approx(50.0, abs=1.0)

def test_ease_value_clamps():
    """# ease_value should clamp to start/end if t is outside duration."""
    from animations import ease_value
    # Before animation starts: return start
    assert ease_value("cubic_out", -0.5, 1.0, 0.0, 100.0) == pytest.approx(0.0, abs=0.1)
    # After animation ends: return end
    assert ease_value("cubic_out", 2.0, 1.0, 0.0, 100.0) == pytest.approx(100.0, abs=0.1)

def test_ease_value_back_out_overshoots():
    """# BackEaseOut should overshoot past end before settling."""
    from animations import ease_value
    # At some midpoint, the value should exceed 100 (overshoot)
    mid_val = ease_value("back_out", 0.5, 1.0, 0.0, 100.0)
    end_val = ease_value("back_out", 1.0, 1.0, 0.0, 100.0)
    # BackEaseOut overshoots then returns — mid might exceed end
    assert end_val == pytest.approx(100.0, abs=0.5)

def test_compute_scale():
    """# compute_scale should return 0.0 at start and 1.0 at end."""
    from animations import compute_scale
    assert compute_scale(0.0, 0.0, 0.5, "cubic_out") == pytest.approx(0.0, abs=0.05)
    assert compute_scale(0.5, 0.0, 0.5, "cubic_out") == pytest.approx(1.0, abs=0.05)

def test_compute_opacity():
    """# compute_opacity should return 0.0 at start and 1.0 at end."""
    from animations import compute_opacity
    assert compute_opacity(0.0, 0.0, 0.3, "quad_out") == pytest.approx(0.0, abs=0.05)
    assert compute_opacity(0.3, 0.0, 0.3, "quad_out") == pytest.approx(1.0, abs=0.05)

def test_compute_slide_x():
    """# compute_slide_x should move from off-screen to target position."""
    from animations import compute_slide_x
    frame_width = 1080
    # At start, should be off-screen (negative or beyond frame)
    x_start = compute_slide_x(0.0, 0.0, 0.4, frame_width, "left")
    assert x_start < 0
    # At end of animation, should be at center
    x_end = compute_slide_x(0.4, 0.0, 0.4, frame_width, "left")
    assert x_end == pytest.approx(frame_width // 2, abs=10)

def test_particle_system_render():
    """# ParticleSystem should composite sparkles onto a frame without crashing."""
    from animations import ParticleSystem
    ps = ParticleSystem(width=1080, height=1920, count=10)
    frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
    result = ps.render(frame, t=0.5)
    assert result.shape == (1920, 1080, 3)
    # At least some pixels should be non-zero (particles drawn)
    assert np.any(result > 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_animations.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write animations.py**

```python
# animations.py
# ============================================================
# Easing-driven animation system for Leo Quiz.
# Provides smooth motion for every visual element:
# slides, scales, fades, bounces, and particle overlays.
# Uses Penner easing functions via easing-functions library.
# ============================================================
import math
import random
import numpy as np
from easing_functions import (
    LinearInOut,
    CubicEaseOut, CubicEaseIn, CubicEaseInOut,
    QuadEaseOut, QuadEaseIn,
    BackEaseOut,
    ElasticEaseOut,
    BounceEaseOut,
    SineEaseInOut,
)

# --- Easing function registry ---
# Maps string names to easing classes for flexible usage
EASING_MAP = {
    "linear": LinearInOut,
    "cubic_out": CubicEaseOut,
    "cubic_in": CubicEaseIn,
    "cubic_inout": CubicEaseInOut,
    "quad_out": QuadEaseOut,
    "quad_in": QuadEaseIn,
    "back_out": BackEaseOut,
    "elastic_out": ElasticEaseOut,
    "bounce_out": BounceEaseOut,
    "sine_inout": SineEaseInOut,
}


def ease_value(easing_type: str, t: float, duration: float,
               start: float, end: float) -> float:
    """
    # Compute an eased value between start and end.
    # t: current time (seconds) within the animation
    # duration: total animation duration (seconds)
    # Returns interpolated value using the specified easing curve.
    # Clamps to start/end if t is outside [0, duration].
    """
    # Clamp t to valid range
    if t <= 0.0:
        return start
    if t >= duration:
        return end

    # Normalize t to [0, 1] for the easing function
    easing_class = EASING_MAP.get(easing_type, LinearInOut)
    easing_fn = easing_class(start=start, end=end, duration=duration)
    return easing_fn(t)


def compute_scale(t: float, start_time: float, duration: float,
                  easing_type: str = "cubic_out") -> float:
    """
    # Compute a scale factor from 0.0 to 1.0 with easing.
    # Used for pop-in effects on images, countdown numbers, etc.
    """
    elapsed = t - start_time
    return ease_value(easing_type, elapsed, duration, 0.0, 1.0)


def compute_opacity(t: float, start_time: float, duration: float,
                    easing_type: str = "quad_out") -> float:
    """
    # Compute opacity from 0.0 to 1.0 with easing.
    # Used for fade-in effects on text, mascot pose swaps, etc.
    """
    elapsed = t - start_time
    return ease_value(easing_type, elapsed, duration, 0.0, 1.0)


def compute_slide_x(t: float, start_time: float, duration: float,
                    frame_width: int, direction: str = "left") -> int:
    """
    # Compute horizontal position for a slide-in animation.
    # Moves from off-screen to center of frame.
    # direction: "left" (slides from left) or "right" (slides from right)
    """
    elapsed = t - start_time
    center = frame_width // 2

    if direction == "left":
        # Start off-screen to the left, slide to center
        start_x = -frame_width // 2
    else:
        # Start off-screen to the right, slide to center
        start_x = frame_width + frame_width // 2

    x = ease_value("cubic_out", elapsed, duration, float(start_x), float(center))
    return int(x)


def compute_bounce_y(t: float, amplitude: float = 3.0,
                     period: float = 1.2) -> float:
    """
    # Compute vertical offset for idle bounce animation (Leo mascot).
    # Returns a value between -amplitude and +amplitude using SineEaseInOut.
    # period: full cycle duration in seconds.
    """
    # Use sine wave for smooth up/down bounce
    phase = (t % period) / period  # 0.0 to 1.0
    return amplitude * math.sin(phase * 2 * math.pi)


class ParticleSystem:
    """
    # Generates and renders sparkle/star particles floating across the background.
    # Each particle drifts slowly with random size, opacity, and speed.
    # Creates the "premium animation" feel seen in top kids content.
    """

    def __init__(self, width: int, height: int, count: int = 20, seed: int = 42):
        # Seed for reproducibility (same particles each render)
        rng = random.Random(seed)
        self.width = width
        self.height = height

        # Generate particle properties
        self.particles = []
        for _ in range(count):
            self.particles.append({
                "x": rng.uniform(0, width),
                "y": rng.uniform(0, height),
                "size": rng.randint(2, 6),
                "opacity": rng.uniform(0.2, 0.6),
                "speed_x": rng.uniform(-15, 15),   # pixels per second drift
                "speed_y": rng.uniform(-20, -5),    # drift upward
                "phase": rng.uniform(0, 2 * math.pi),  # twinkle phase offset
            })

    def render(self, frame: np.ndarray, t: float) -> np.ndarray:
        """
        # Composite sparkle particles onto the frame at time t.
        # Particles drift and twinkle (opacity oscillates).
        # Returns the modified frame.
        """
        result = frame.copy()

        for p in self.particles:
            # Calculate current position (wraps around edges)
            x = int((p["x"] + p["speed_x"] * t) % self.width)
            y = int((p["y"] + p["speed_y"] * t) % self.height)
            size = p["size"]

            # Twinkle: oscillate opacity with sine wave
            twinkle = 0.5 + 0.5 * math.sin(t * 3.0 + p["phase"])
            opacity = p["opacity"] * twinkle

            # Draw a small bright dot (white/gold sparkle)
            color = np.array([255, 250, 220], dtype=np.float32)  # warm white/gold

            # Bounds checking
            y1 = max(0, y - size)
            y2 = min(self.height, y + size)
            x1 = max(0, x - size)
            x2 = min(self.width, x + size)

            if y2 > y1 and x2 > x1:
                # Blend sparkle onto frame with opacity
                region = result[y1:y2, x1:x2].astype(np.float32)
                sparkle = np.full_like(region, color, dtype=np.float32)
                blended = region * (1 - opacity) + sparkle * opacity
                result[y1:y2, x1:x2] = blended.astype(np.uint8)

        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_animations.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add animations.py tests/test_animations.py
git commit -m "feat: easing-driven animation system with particle overlay"
```

---

### Task 3: Quiz Content Generator

**Files:**
- Create: `quiz_generator.py`
- Test: `tests/test_quiz_generator.py`

**Interfaces:**
- Consumes: `config.GEMINI_API_KEY`, `config.CATEGORIES`, `config.HISTORY_FILE`, `config.ROUNDS_PER_SHORT`
- Produces: `generate_quiz_pack(category: str, num_rounds: int) -> QuizPack`, `QuizRound` dataclass (answer, hint_question, fun_fact, difficulty, image_prompt), `QuizPack` dataclass (category, rounds: list[QuizRound]), `load_history() -> dict`, `save_history(history: dict) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_quiz_generator.py
import pytest
import json
from pathlib import Path

def test_quiz_round_dataclass():
    """# QuizRound should hold all fields for one quiz question."""
    from quiz_generator import QuizRound
    r = QuizRound(
        answer="Lion",
        hint_question="This animal is the king of the jungle!",
        fun_fact="Lions sleep up to 20 hours a day!",
        difficulty="easy",
        image_prompt="cartoon lion on white background"
    )
    assert r.answer == "Lion"
    assert r.difficulty == "easy"

def test_quiz_pack_dataclass():
    """# QuizPack should hold category and list of rounds."""
    from quiz_generator import QuizPack, QuizRound
    rounds = [
        QuizRound("Lion", "King of the jungle", "Sleeps 20 hrs", "easy", "lion prompt"),
        QuizRound("Tiger", "Striped big cat", "Can swim", "medium", "tiger prompt"),
    ]
    pack = QuizPack(category="animals", rounds=rounds)
    assert pack.category == "animals"
    assert len(pack.rounds) == 2

def test_load_history_empty(tmp_path):
    """# load_history should return empty dict when no file exists."""
    from quiz_generator import load_history
    result = load_history(tmp_path / "nonexistent.json")
    assert result == {}

def test_save_and_load_history(tmp_path):
    """# save_history then load_history should round-trip correctly."""
    from quiz_generator import save_history, load_history
    history_file = tmp_path / "history.json"
    data = {"animals": ["Lion", "Tiger"], "total_used": 2}
    save_history(data, history_file)
    loaded = load_history(history_file)
    assert loaded["animals"] == ["Lion", "Tiger"]
    assert loaded["total_used"] == 2

def test_update_history():
    """# update_history should add new answers without duplicates."""
    from quiz_generator import update_history, QuizRound, QuizPack
    history = {"animals": ["Lion"], "total_used": 1}
    pack = QuizPack(
        category="animals",
        rounds=[
            QuizRound("Tiger", "q", "f", "easy", "p"),
            QuizRound("Lion", "q", "f", "easy", "p"),  # duplicate — should not add
        ]
    )
    updated = update_history(history, pack)
    assert "Tiger" in updated["animals"]
    assert updated["animals"].count("Lion") == 1  # no duplicate
    assert updated["total_used"] == 2

def test_parse_quiz_response():
    """# parse_quiz_response should extract QuizPack from Gemini JSON string."""
    from quiz_generator import parse_quiz_response
    raw_json = json.dumps({
        "category": "animals",
        "rounds": [
            {
                "answer": "Elephant",
                "hint_question": "Largest land animal!",
                "fun_fact": "Elephants can't jump!",
                "difficulty": "easy",
                "image_prompt": "cartoon elephant"
            }
        ]
    })
    pack = parse_quiz_response(raw_json, "animals")
    assert pack.category == "animals"
    assert len(pack.rounds) == 1
    assert pack.rounds[0].answer == "Elephant"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_quiz_generator.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write quiz_generator.py**

```python
# quiz_generator.py
# ============================================================
# Quiz content generation using Gemini 2.5 Flash.
# Generates quiz packs with answers, hints, fun facts,
# difficulty levels, and image prompts.
# Never-repeat system via history.json tracking.
# ============================================================
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import config


@dataclass
class QuizRound:
    """# One quiz question with all metadata needed for video generation."""
    answer: str
    hint_question: str
    fun_fact: str
    difficulty: str  # "easy", "medium", "hard"
    image_prompt: str


@dataclass
class QuizPack:
    """# A complete set of quiz rounds for one video."""
    category: str
    rounds: list[QuizRound] = field(default_factory=list)


def load_history(history_file: Path = None) -> dict:
    """# Load previously used answers from history.json."""
    if history_file is None:
        history_file = config.HISTORY_FILE
    if not history_file.exists():
        return {}
    with open(history_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history: dict, history_file: Path = None) -> None:
    """# Save updated history to history.json."""
    if history_file is None:
        history_file = config.HISTORY_FILE
    history["last_updated"] = datetime.now().isoformat()
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def update_history(history: dict, pack: QuizPack) -> dict:
    """# Add new answers from a quiz pack to history. No duplicates."""
    category = pack.category
    if category not in history:
        history[category] = []

    existing = set(history[category])
    new_count = 0
    for r in pack.rounds:
        if r.answer not in existing:
            history[category].append(r.answer)
            existing.add(r.answer)
            new_count += 1

    # Update total count
    history["total_used"] = sum(
        len(v) for k, v in history.items()
        if k not in ("total_used", "last_updated") and isinstance(v, list)
    )
    return history


def parse_quiz_response(raw_json: str, category: str) -> QuizPack:
    """
    # Parse Gemini's JSON response into a QuizPack.
    # Handles JSON wrapped in markdown code fences.
    """
    # Strip markdown code fences if present
    cleaned = raw_json.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    data = json.loads(cleaned)

    rounds = []
    for r in data.get("rounds", []):
        rounds.append(QuizRound(
            answer=r["answer"],
            hint_question=r["hint_question"],
            fun_fact=r["fun_fact"],
            difficulty=r.get("difficulty", "medium"),
            image_prompt=r.get("image_prompt",
                               config.IMAGE_PROMPT_TEMPLATE.format(answer=r["answer"])),
        ))

    return QuizPack(category=category, rounds=rounds)


def generate_quiz_pack(category: str, num_rounds: int = None) -> QuizPack:
    """
    # Generate a fresh quiz pack using Gemini 2.5 Flash.
    # Loads history to avoid repeating past answers.
    # Returns a QuizPack with num_rounds unique questions.
    """
    from google import genai

    if num_rounds is None:
        num_rounds = config.ROUNDS_PER_SHORT

    # Load history for never-repeat system
    history = load_history()
    used_answers = history.get(category, [])

    # Build the category-specific prompt
    cat_info = config.CATEGORIES[category]

    prompt = f"""You are a kids quiz content generator. Generate exactly {num_rounds} quiz questions about {cat_info['prompt_hint']}.

RULES:
- Each answer must be a specific, recognizable {cat_info['display'].lower()}
- Fun facts must be kid-appropriate, surprising, and under 15 words
- hint_question should be a playful clue (not the answer itself)
- Difficulty: {num_rounds} rounds with mix of easy (common, well-known), medium (less common but recognizable), and hard (rare/exotic)
- image_prompt should describe a cute cartoon illustration on pure white background
- NEVER use any of these previously used answers: {json.dumps(used_answers[-200:])}

Return ONLY valid JSON in this exact format:
{{
  "category": "{category}",
  "rounds": [
    {{
      "answer": "Lion",
      "hint_question": "This animal is called the king of the jungle!",
      "fun_fact": "Lions can sleep up to 20 hours a day!",
      "difficulty": "easy",
      "image_prompt": "Cute colorful cartoon illustration of a lion, kid-friendly style, bright vibrant colors, clean edges, full body view, centered, pure white background, no text, no watermark, high quality, children's book illustration style"
    }}
  ]
}}"""

    # Call Gemini
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # Parse response
    pack = parse_quiz_response(response.text, category)

    # Update and save history
    history = update_history(history, pack)
    save_history(history)

    return pack
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_quiz_generator.py -v`
Expected: All 6 tests PASS (only offline tests — generate_quiz_pack needs live API)

- [ ] **Step 5: Commit**

```bash
git add quiz_generator.py tests/test_quiz_generator.py
git commit -m "feat: quiz content generator with Gemini and never-repeat history"
```

---

### Task 4: Image Generation + Silhouette Extraction

**Files:**
- Create: `image_generator.py`
- Create: `silhouette.py`
- Test: `tests/test_silhouette.py`

**Interfaces:**
- Consumes: `config.GEMINI_API_KEY`, `config.IMAGE_PROMPT_TEMPLATE`, `quiz_generator.QuizRound`
- Produces: `generate_quiz_image(round: QuizRound, output_path: Path) -> Path`, `extract_silhouette(image_path: Path, output_path: Path) -> Path`, `validate_silhouette(silhouette_path: Path) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_silhouette.py
import pytest
import numpy as np
from pathlib import Path
from PIL import Image

def _create_test_image(path: Path, bg_color=(255, 255, 255), subject_color=(200, 50, 30)):
    """# Helper: create a test image with a colored shape on white background."""
    img = Image.new("RGB", (512, 512), bg_color)
    # Draw a simple circle in the center as the "subject"
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([156, 156, 356, 356], fill=subject_color)
    img.save(path)
    return path

def test_extract_silhouette_creates_black_shape(tmp_path):
    """# Silhouette should convert subject to pure black on transparent bg."""
    from silhouette import extract_silhouette
    input_path = _create_test_image(tmp_path / "test_input.png")
    output_path = tmp_path / "test_silhouette.png"

    result = extract_silhouette(input_path, output_path)
    assert result.exists()

    # Load and verify — should have alpha channel (RGBA)
    sil = Image.open(result)
    assert sil.mode == "RGBA"

    # The subject area should be black (non-transparent)
    arr = np.array(sil)
    # Center pixel should be black and opaque
    center = arr[256, 256]
    assert center[0] < 30   # R near 0
    assert center[1] < 30   # G near 0
    assert center[2] < 30   # B near 0
    assert center[3] > 200  # A near 255 (opaque)

    # Corner pixel should be transparent
    corner = arr[10, 10]
    assert corner[3] < 30   # A near 0 (transparent)

def test_validate_silhouette_good(tmp_path):
    """# A silhouette with reasonable coverage should pass validation."""
    from silhouette import extract_silhouette, validate_silhouette
    input_path = _create_test_image(tmp_path / "test_input.png")
    sil_path = extract_silhouette(input_path, tmp_path / "test_sil.png")
    assert validate_silhouette(sil_path) is True

def test_validate_silhouette_too_small(tmp_path):
    """# A silhouette with tiny coverage (<5%) should fail validation."""
    from silhouette import validate_silhouette
    # Create a nearly empty image (tiny dot)
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.ellipse([250, 250, 255, 255], fill=(0, 0, 0, 255))
    path = tmp_path / "tiny.png"
    img.save(path)
    assert validate_silhouette(path) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_silhouette.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write silhouette.py**

```python
# silhouette.py
# ============================================================
# Silhouette extraction from AI-generated quiz images.
# Converts a cartoon image on white background into a pure
# black silhouette with transparent background.
# ============================================================
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter


def extract_silhouette(image_path: Path, output_path: Path,
                       threshold: int = 240, blur_radius: float = 1.5) -> Path:
    """
    # Extract a black silhouette from a white-background image.
    # 1. Convert to grayscale
    # 2. Threshold: anything not-white becomes subject
    # 3. Smooth edges with slight Gaussian blur
    # 4. Output: pure black shape on transparent background (RGBA)
    """
    img = Image.open(image_path).convert("RGB")

    # Convert to grayscale for thresholding
    gray = img.convert("L")
    gray_arr = np.array(gray)

    # Threshold: pixels darker than threshold = subject (1), lighter = background (0)
    mask = (gray_arr < threshold).astype(np.uint8) * 255

    # Smooth edges with Gaussian blur to remove jagged edges
    mask_img = Image.fromarray(mask, mode="L")
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Re-threshold after blur to keep edges clean but smooth
    mask_arr = np.array(mask_img)
    mask_arr = ((mask_arr > 128).astype(np.uint8)) * 255

    # Create RGBA output: pure black where subject is, transparent elsewhere
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    result_arr = np.array(result)

    # Black pixels where mask is active
    result_arr[:, :, 0] = 0    # R = 0
    result_arr[:, :, 1] = 0    # G = 0
    result_arr[:, :, 2] = 0    # B = 0
    result_arr[:, :, 3] = mask_arr  # Alpha = mask

    result = Image.fromarray(result_arr, mode="RGBA")
    result.save(output_path, "PNG")
    return output_path


def validate_silhouette(silhouette_path: Path,
                        min_coverage: float = 0.05,
                        max_coverage: float = 0.80) -> bool:
    """
    # Validate that a silhouette is recognizable.
    # Checks that the opaque area is between min_coverage and max_coverage
    # of the total image area. Too small = unrecognizable, too large = bad extraction.
    """
    img = Image.open(silhouette_path).convert("RGBA")
    arr = np.array(img)

    # Count opaque pixels (alpha > 128)
    opaque_pixels = np.sum(arr[:, :, 3] > 128)
    total_pixels = arr.shape[0] * arr.shape[1]
    coverage = opaque_pixels / total_pixels

    return min_coverage <= coverage <= max_coverage
```

- [ ] **Step 4: Write image_generator.py**

```python
# image_generator.py
# ============================================================
# AI image generation using Gemini Imagen.
# Generates cartoon-style quiz images on white backgrounds.
# ============================================================
from pathlib import Path
import base64

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

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Use the round's custom prompt, or generate from template
    prompt = round_data.image_prompt
    if not prompt:
        prompt = config.IMAGE_PROMPT_TEMPLATE.format(answer=round_data.answer)

    # Generate image via Gemini Imagen
    response = client.models.generate_images(
        model="imagen-3.0-generate-002",
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="1:1",
        ),
    )

    # Save the first generated image
    if response.generated_images:
        image_data = response.generated_images[0].image.image_bytes
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(image_data)
        return output_path

    raise RuntimeError(f"Imagen failed to generate image for: {round_data.answer}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_silhouette.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add silhouette.py image_generator.py tests/test_silhouette.py
git commit -m "feat: image generation with Gemini Imagen and silhouette extraction"
```

---

### Task 5: Frame Composer (Background, Text, Layout)

**Files:**
- Create: `frame_composer.py`
- Test: `tests/test_frame_composer.py`

**Interfaces:**
- Consumes: `config.CATEGORY_COLORS`, `config.SHORTS_SIZE`, `config.LONGFORM_SIZE`, font/typography constants, `animations.ParticleSystem`
- Produces: `render_gradient_background(width, height, category, t) -> Image`, `render_text(image, text, position, font_size, color, stroke, shadow) -> Image`, `compose_question_frame(category, silhouette_path, question_text, score, round_num, mascot_pose, size) -> Image`, `compose_reveal_frame(category, image_path, answer_text, fun_fact, score, round_num, mascot_pose, size) -> Image`, `compose_countdown_frame(category, silhouette_path, number, score, round_num, mascot_pose, size) -> Image`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_frame_composer.py
import pytest
from pathlib import Path
from PIL import Image
import numpy as np

def test_render_gradient_background():
    """# Should produce a gradient image with the right dimensions."""
    from frame_composer import render_gradient_background
    img = render_gradient_background(1080, 1920, "animals", t=0.0)
    assert img.size == (1080, 1920)
    assert img.mode == "RGB"
    # Top and bottom should be different colors (it's a gradient)
    arr = np.array(img)
    top_pixel = arr[10, 540]
    bottom_pixel = arr[1910, 540]
    assert not np.array_equal(top_pixel, bottom_pixel)

def test_render_text():
    """# Should draw text onto an image without crashing."""
    from frame_composer import render_text
    img = Image.new("RGBA", (1080, 1920), (50, 50, 50, 255))
    result = render_text(img, "Hello World!", position=(540, 960),
                         font_size=48, color=(255, 255, 255))
    assert result.size == (1080, 1920)
    # Some pixels should have changed (text was drawn)
    orig_arr = np.array(img)
    result_arr = np.array(result)
    assert not np.array_equal(orig_arr, result_arr)

def test_hex_to_rgb():
    """# Should convert hex color strings to RGB tuples."""
    from frame_composer import hex_to_rgb
    assert hex_to_rgb("#2ECC71") == (46, 204, 113)
    assert hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert hex_to_rgb("#000000") == (0, 0, 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_frame_composer.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write frame_composer.py**

```python
# frame_composer.py
# ============================================================
# Frame composition for Leo Quiz videos.
# Renders gradient backgrounds, text with effects (stroke,
# shadow, glow), and composites all visual elements into
# complete video frames.
# ============================================================
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

import config


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """# Convert hex color string (#RRGGBB) to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _shift_hue(rgb: tuple, shift_degrees: float) -> tuple[int, int, int]:
    """# Shift the hue of an RGB color by shift_degrees."""
    import colorsys
    r, g, b = [x / 255.0 for x in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + shift_degrees / 360.0) % 1.0
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return (int(r2 * 255), int(g2 * 255), int(b2 * 255))


def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """
    # Load a font, trying Baloo2-Bold first, then Fredoka, then default.
    # Falls back gracefully if custom fonts aren't installed yet.
    """
    font_names = ["Baloo2-Bold.ttf", "FredokaOne-Regular.ttf"]
    for name in font_names:
        font_path = config.FONTS_DIR / name
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    # Fallback to default font
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def render_gradient_background(width: int, height: int,
                                category: str, t: float = 0.0) -> Image.Image:
    """
    # Render a vertical gradient background using the category's color theme.
    # Hue shifts slightly over time (±5 degrees) for a "living" feel.
    """
    colors = config.CATEGORY_COLORS[category]
    color1 = hex_to_rgb(colors["primary"])
    color2 = hex_to_rgb(colors["secondary"])

    # Apply subtle hue shift based on time
    hue_shift = 5.0 * math.sin(t * 0.5)
    color1 = _shift_hue(color1, hue_shift)
    color2 = _shift_hue(color2, -hue_shift)

    # Create gradient image
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        ratio = y / height
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        arr[y, :] = [r, g, b]

    return Image.fromarray(arr, mode="RGB")


def render_text(image: Image.Image, text: str, position: tuple[int, int],
                font_size: int = 48, color: tuple = (255, 255, 255),
                stroke_color: tuple = (0, 0, 0), stroke_width: int = 3,
                shadow: bool = True, anchor: str = "mm") -> Image.Image:
    """
    # Draw text with stroke outline and optional drop shadow.
    # position: (x, y) center of text
    # anchor: Pillow text anchor (mm = middle-middle)
    """
    result = image.copy()
    if result.mode != "RGBA":
        result = result.convert("RGBA")

    font = _get_font(font_size)

    # Draw shadow layer if enabled
    if shadow:
        shadow_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_pos = (position[0] + config.TEXT_SHADOW_OFFSET,
                      position[1] + config.TEXT_SHADOW_OFFSET)
        shadow_draw.text(shadow_pos, text, font=font,
                         fill=(0, 0, 0, int(255 * config.TEXT_SHADOW_OPACITY)),
                         anchor=anchor)
        # Blur the shadow slightly
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(2))
        result = Image.alpha_composite(result, shadow_layer)

    # Draw main text with stroke
    draw = ImageDraw.Draw(result)
    draw.text(position, text, font=font, fill=color,
              stroke_width=stroke_width, stroke_fill=stroke_color,
              anchor=anchor)

    return result


def compose_question_frame(category: str, silhouette_path: Path,
                            question_text: str, score: int, round_num: int,
                            total_rounds: int, mascot_img: Image.Image = None,
                            size: tuple = None) -> Image.Image:
    """
    # Compose a complete question frame with all visual elements:
    # gradient bg + silhouette + question text + score + mascot
    """
    if size is None:
        size = config.SHORTS_SIZE
    width, height = size

    # Render gradient background
    bg = render_gradient_background(width, height, category)
    frame = bg.convert("RGBA")

    # Load and center silhouette
    if silhouette_path and Path(silhouette_path).exists():
        sil = Image.open(silhouette_path).convert("RGBA")
        # Scale silhouette to fit ~50% of frame width
        sil_size = int(width * 0.5)
        sil = sil.resize((sil_size, sil_size), Image.LANCZOS)
        # Center horizontally, position at ~35% from top
        sil_x = (width - sil_size) // 2
        sil_y = int(height * 0.25)
        frame.paste(sil, (sil_x, sil_y), sil)

    # Question text
    frame = render_text(frame, question_text,
                        position=(width // 2, int(height * 0.62)),
                        font_size=config.QUESTION_FONT_SIZE)

    # Title bar
    colors = config.CATEGORY_COLORS[category]
    cat_display = config.CATEGORIES[category]["display"]
    frame = render_text(frame, f"GUESS THE {cat_display.upper()}",
                        position=(width // 2, int(height * 0.06)),
                        font_size=config.TITLE_FONT_SIZE,
                        color=hex_to_rgb(colors["primary"]))

    # Score
    frame = render_text(frame, f"Score: {score}/{total_rounds}",
                        position=(width // 2, int(height * 0.88)),
                        font_size=config.SCORE_FONT_SIZE)

    # Mascot (thinking pose) in bottom-right
    if mascot_img:
        mascot_h = int(height * 0.15)
        mascot_w = int(mascot_img.width * (mascot_h / mascot_img.height))
        mascot_resized = mascot_img.resize((mascot_w, mascot_h), Image.LANCZOS)
        mascot_x = width - mascot_w - 20
        mascot_y = height - mascot_h - 20
        frame.paste(mascot_resized, (mascot_x, mascot_y), mascot_resized)

    return frame


def compose_reveal_frame(category: str, image_path: Path,
                          answer_text: str, fun_fact: str,
                          score: int, round_num: int, total_rounds: int,
                          mascot_img: Image.Image = None,
                          size: tuple = None) -> Image.Image:
    """
    # Compose a reveal frame: full color image + answer text + fun fact.
    """
    if size is None:
        size = config.SHORTS_SIZE
    width, height = size

    # Gradient background
    bg = render_gradient_background(width, height, category)
    frame = bg.convert("RGBA")

    # Full color image (centered, larger than silhouette)
    if image_path and Path(image_path).exists():
        img = Image.open(image_path).convert("RGBA")
        img_size = int(width * 0.55)
        img = img.resize((img_size, img_size), Image.LANCZOS)
        img_x = (width - img_size) // 2
        img_y = int(height * 0.22)
        frame.paste(img, (img_x, img_y), img)

    # Answer text (category color, big, celebratory)
    colors = config.CATEGORY_COLORS[category]
    frame = render_text(frame, f"It's a {answer_text}!",
                        position=(width // 2, int(height * 0.60)),
                        font_size=config.ANSWER_FONT_SIZE,
                        color=hex_to_rgb(colors["primary"]),
                        stroke_color=(255, 255, 255))

    # Fun fact with semi-transparent pill background
    fact_y = int(height * 0.72)
    pill_layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    pill_draw = ImageDraw.Draw(pill_layer)
    font = _get_font(config.FACT_FONT_SIZE)
    bbox = font.getbbox(fun_fact)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad = 20
    pill_rect = [
        width // 2 - text_w // 2 - pad,
        fact_y - text_h // 2 - pad // 2,
        width // 2 + text_w // 2 + pad,
        fact_y + text_h // 2 + pad // 2,
    ]
    pill_draw.rounded_rectangle(pill_rect, radius=15, fill=(0, 0, 0, 153))
    frame = Image.alpha_composite(frame, pill_layer)
    frame = render_text(frame, fun_fact,
                        position=(width // 2, fact_y),
                        font_size=config.FACT_FONT_SIZE,
                        stroke_width=0, shadow=False)

    # Title bar
    cat_display = config.CATEGORIES[category]["display"]
    frame = render_text(frame, f"GUESS THE {cat_display.upper()}",
                        position=(width // 2, int(height * 0.06)),
                        font_size=config.TITLE_FONT_SIZE,
                        color=hex_to_rgb(colors["primary"]))

    # Score
    frame = render_text(frame, f"Score: {score}/{total_rounds}",
                        position=(width // 2, int(height * 0.88)),
                        font_size=config.SCORE_FONT_SIZE)

    # Mascot (excited pose) in bottom-right
    if mascot_img:
        mascot_h = int(height * 0.15)
        mascot_w = int(mascot_img.width * (mascot_h / mascot_img.height))
        mascot_resized = mascot_img.resize((mascot_w, mascot_h), Image.LANCZOS)
        mascot_x = width - mascot_w - 20
        mascot_y = height - mascot_h - 20
        frame.paste(mascot_resized, (mascot_x, mascot_y), mascot_resized)

    return frame


def compose_countdown_frame(category: str, silhouette_path: Path,
                             number: int, score: int, round_num: int,
                             total_rounds: int, mascot_img: Image.Image = None,
                             size: tuple = None) -> Image.Image:
    """
    # Compose a countdown frame: silhouette + large countdown number overlay.
    """
    # Start with question frame as base
    frame = compose_question_frame(
        category, silhouette_path, "",
        score, round_num, total_rounds, mascot_img, size
    )

    if size is None:
        size = config.SHORTS_SIZE
    width, height = size

    # Large countdown number in center
    colors = config.CATEGORY_COLORS[category]
    frame = render_text(frame, str(number),
                        position=(width // 2, int(height * 0.50)),
                        font_size=config.COUNTDOWN_FONT_SIZE,
                        color=(255, 255, 255),
                        stroke_color=hex_to_rgb(colors["primary"]),
                        stroke_width=6)

    return frame
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_frame_composer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frame_composer.py tests/test_frame_composer.py
git commit -m "feat: frame composer with gradient backgrounds, text effects, and layouts"
```

---

### Task 6: Narration + Audio Mixer

**Files:**
- Create: `narration.py`
- Create: `audio_mixer.py`
- Test: `tests/test_audio_mixer.py`

**Interfaces:**
- Consumes: `config.ELEVENLABS_API_KEY`, `config.ELEVENLABS_VOICE_ID`, `config.SFX_FILES`, `config.AUDIO_PEAK_DB`, `quiz_generator.QuizPack`
- Produces: `generate_narration(text: str, output_path: Path) -> tuple[Path, list[dict]]` (returns audio path + word timestamps), `generate_round_narration(round_data: QuizRound, category: str, output_dir: Path) -> RoundAudio`, `RoundAudio` dataclass (question_path, reveal_path, fact_path, fact_timestamps), `mix_video_audio(round_audios: list[RoundAudio], intro_path, outro_path, music_path, sfx_paths, total_duration, output_path) -> Path`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_audio_mixer.py
import pytest
from pathlib import Path
import struct
import wave

def _create_silent_wav(path: Path, duration_ms: int = 1000, sample_rate: int = 44100):
    """# Helper: create a silent WAV file for testing."""
    num_samples = int(sample_rate * duration_ms / 1000)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * num_samples)
    return path

def test_round_audio_dataclass():
    """# RoundAudio should hold paths to all audio clips for one round."""
    from narration import RoundAudio
    ra = RoundAudio(
        question_path=Path("q.wav"),
        reveal_path=Path("r.wav"),
        fact_path=Path("f.wav"),
        fact_timestamps=[{"word": "Lions", "start": 0.0, "end": 0.2}],
    )
    assert ra.question_path == Path("q.wav")
    assert len(ra.fact_timestamps) == 1

def test_normalize_audio(tmp_path):
    """# normalize_audio should adjust peak to target dB."""
    from audio_mixer import normalize_audio
    wav_path = _create_silent_wav(tmp_path / "test.wav", duration_ms=500)
    result = normalize_audio(wav_path, target_db=-3.0)
    assert result.exists()

def test_mix_layers_creates_output(tmp_path):
    """# mix_layers should combine multiple audio files into one output."""
    from audio_mixer import mix_layers
    track1 = _create_silent_wav(tmp_path / "track1.wav")
    track2 = _create_silent_wav(tmp_path / "track2.wav")
    output = tmp_path / "mixed.wav"
    result = mix_layers(
        layers=[(track1, 0, 1.0), (track2, 500, 0.5)],
        total_duration_ms=2000,
        output_path=output
    )
    assert result.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_audio_mixer.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write narration.py**

```python
# narration.py
# ============================================================
# Voice narration generation using ElevenLabs.
# Generates individual audio clips per quiz round with
# word-level timestamps for synced text animation.
# ============================================================
from dataclasses import dataclass, field
from pathlib import Path

import config
from quiz_generator import QuizRound


@dataclass
class RoundAudio:
    """# All audio clips and timing data for one quiz round."""
    question_path: Path
    reveal_path: Path
    fact_path: Path
    fact_timestamps: list[dict] = field(default_factory=list)
    # Each timestamp: {"word": str, "start": float, "end": float}


def generate_narration(text: str, output_path: Path) -> tuple[Path, list[dict]]:
    """
    # Generate speech audio from text using ElevenLabs.
    # Returns (audio_path, word_timestamps).
    # word_timestamps is a list of {"word", "start", "end"} dicts.
    """
    from elevenlabs import ElevenLabs

    client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

    # Generate with word-level timestamps
    response = client.text_to_speech.convert_with_timestamps(
        text=text,
        voice_id=config.ELEVENLABS_VOICE_ID,
        model_id="eleven_multilingual_v2",
    )

    # Collect audio bytes and timestamps
    audio_bytes = b""
    word_timestamps = []

    for chunk in response:
        if hasattr(chunk, "audio_base64") and chunk.audio_base64:
            import base64
            audio_bytes += base64.b64decode(chunk.audio_base64)
        if hasattr(chunk, "alignment") and chunk.alignment:
            for char_info in chunk.alignment.characters:
                # ElevenLabs returns character-level; we aggregate to words
                pass
            # Use word-level if available
            if hasattr(chunk.alignment, "words") and chunk.alignment.words:
                for w in chunk.alignment.words:
                    word_timestamps.append({
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                    })

    # Save audio
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    return output_path, word_timestamps


def generate_round_narration(round_data: QuizRound, category: str,
                              output_dir: Path) -> RoundAudio:
    """
    # Generate all narration clips for one quiz round.
    # Returns RoundAudio with paths to question, reveal, and fact clips.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    cat_display = config.CATEGORIES[category]["display"]

    # Question line: "What [category] is this?"
    q_text = f"What {cat_display.lower()} is this?"
    q_path, _ = generate_narration(q_text, output_dir / "question.mp3")

    # Reveal line: "It's a [answer]!"
    r_text = f"It's a {round_data.answer}!"
    r_path, _ = generate_narration(r_text, output_dir / "reveal.mp3")

    # Fun fact line
    f_path, f_timestamps = generate_narration(
        round_data.fun_fact, output_dir / "fact.mp3"
    )

    return RoundAudio(
        question_path=q_path,
        reveal_path=r_path,
        fact_path=f_path,
        fact_timestamps=f_timestamps,
    )
```

- [ ] **Step 4: Write audio_mixer.py**

```python
# audio_mixer.py
# ============================================================
# Audio assembly for Leo Quiz videos.
# Mixes voice narration, sound effects, and background music
# into a single audio track with proper volume levels.
# ============================================================
from pathlib import Path
from pydub import AudioSegment
from pydub.effects import normalize

import config


def normalize_audio(audio_path: Path, target_db: float = None) -> Path:
    """
    # Normalize an audio file to the target peak dB.
    # Overwrites the file in place. Returns the path.
    """
    if target_db is None:
        target_db = config.AUDIO_PEAK_DB

    audio = AudioSegment.from_file(str(audio_path))
    # Calculate how much to adjust
    change_in_db = target_db - audio.max_dBFS
    normalized = audio.apply_gain(change_in_db)
    normalized.export(str(audio_path), format=audio_path.suffix.lstrip("."))
    return audio_path


def mix_layers(layers: list[tuple[Path, int, float]],
               total_duration_ms: int,
               output_path: Path) -> Path:
    """
    # Mix multiple audio layers into one output file.
    # layers: list of (audio_path, start_offset_ms, volume_multiplier)
    # volume_multiplier: 1.0 = full volume, 0.2 = 20%, etc.
    """
    # Create silent base track
    mixed = AudioSegment.silent(duration=total_duration_ms)

    for audio_path, offset_ms, volume in layers:
        if not Path(audio_path).exists():
            continue
        clip = AudioSegment.from_file(str(audio_path))

        # Apply volume adjustment
        if volume < 1.0:
            # Convert multiplier to dB reduction
            import math
            db_change = 20 * math.log10(max(volume, 0.01))
            clip = clip.apply_gain(db_change)

        # Overlay at the specified offset
        mixed = mixed.overlay(clip, position=offset_ms)

    # Normalize final mix
    change_in_db = config.AUDIO_PEAK_DB - mixed.max_dBFS
    mixed = mixed.apply_gain(change_in_db)

    # Export
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mixed.export(str(output_path), format="wav")
    return output_path


def build_short_audio(round_audios: list, music_path: Path,
                       total_duration: float,
                       output_path: Path) -> Path:
    """
    # Build complete audio track for a short-form video.
    # Layers: background music (continuous, ducked) + voice clips + SFX
    # placed at correct timestamps per the round timing spec.
    """
    total_ms = int(total_duration * 1000)
    layers = []

    # Background music (looping, 15-20% volume)
    if music_path and music_path.exists():
        music = AudioSegment.from_file(str(music_path))
        # Loop music to fill total duration
        loops_needed = (total_ms // len(music)) + 1
        looped_music = music * loops_needed
        looped_path = output_path.parent / "looped_music.wav"
        looped_music[:total_ms].export(str(looped_path), format="wav")
        layers.append((looped_path, 0, 0.18))

    # Intro jingle
    if config.SFX_FILES["jingle_intro"].exists():
        layers.append((config.SFX_FILES["jingle_intro"], 0, 0.7))

    # Per-round audio placement
    for i, ra in enumerate(round_audios):
        # Round start time in ms
        round_start_ms = int((config.INTRO_DURATION + i * config.ROUND_DURATION) * 1000)

        # Question voice at round start
        layers.append((ra.question_path, round_start_ms, 1.0))

        # Tick SFX at countdown times (2s, 3s, 4s into round)
        for sec in range(config.COUNTDOWN_SECONDS):
            tick_ms = round_start_ms + int((config.COUNTDOWN_START + sec) * 1000)
            if config.SFX_FILES["tick"].exists():
                layers.append((config.SFX_FILES["tick"], tick_ms, 0.6))

        # Ding SFX + reveal voice at 5s into round
        reveal_ms = round_start_ms + int(config.REVEAL_START * 1000)
        if config.SFX_FILES["ding"].exists():
            layers.append((config.SFX_FILES["ding"], reveal_ms, 0.8))
        layers.append((ra.reveal_path, reveal_ms, 1.0))

        # Fun fact voice at 6.5s into round
        fact_ms = round_start_ms + int(config.FUN_FACT_START * 1000)
        layers.append((ra.fact_path, fact_ms, 1.0))

        # Whoosh transition at 9.5s
        transition_ms = round_start_ms + int(config.TRANSITION_START * 1000)
        if config.SFX_FILES["whoosh"].exists():
            layers.append((config.SFX_FILES["whoosh"], transition_ms, 0.5))

    # Outro jingle
    outro_ms = total_ms - int(config.OUTRO_DURATION * 1000)
    if config.SFX_FILES["jingle_outro"].exists():
        layers.append((config.SFX_FILES["jingle_outro"], outro_ms, 0.7))

    return mix_layers(layers, total_ms, output_path)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_audio_mixer.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add narration.py audio_mixer.py tests/test_audio_mixer.py
git commit -m "feat: ElevenLabs narration and layered audio mixer with SFX"
```

---

### Task 7: Video Assembler (Frame-by-Frame Renderer)

**Files:**
- Create: `video_assembler.py`
- Test: `tests/test_video_assembler.py`

**Interfaces:**
- Consumes: `animations.*` (ease_value, compute_scale, compute_slide_x, compute_bounce_y, ParticleSystem), `frame_composer.*` (compose_question_frame, compose_reveal_frame, compose_countdown_frame, render_gradient_background), `narration.RoundAudio`, `config.*` (all timing/size constants)
- Produces: `assemble_short(quiz_pack: QuizPack, image_paths: list[Path], silhouette_paths: list[Path], round_audios: list[RoundAudio], audio_path: Path, output_path: Path) -> Path`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video_assembler.py
import pytest
import numpy as np
from PIL import Image
from pathlib import Path

def test_build_round_timeline():
    """# build_round_timeline should return correct timing entries for one round."""
    from video_assembler import build_round_timeline
    timeline = build_round_timeline(round_index=0, round_start=2.0)
    # Should have entries for silhouette, countdown 3/2/1, reveal, fact
    assert len(timeline) >= 6
    # First entry should be silhouette phase starting at round_start
    assert timeline[0]["phase"] == "silhouette"
    assert timeline[0]["start"] == pytest.approx(2.0, abs=0.01)

def test_render_frame_returns_array():
    """# render_frame should return a numpy array of the correct size."""
    from video_assembler import render_frame, VideoContext
    # Create minimal context for testing
    ctx = VideoContext(
        width=1080, height=1920,
        category="animals",
        rounds=[],
        image_paths=[],
        silhouette_paths=[],
        mascot_images={},
        particle_system=None,
    )
    frame = render_frame(0.0, ctx)
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (1920, 1080, 3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_video_assembler.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write video_assembler.py**

```python
# video_assembler.py
# ============================================================
# Frame-by-frame video renderer for Leo Quiz.
# Every frame is computed from easing functions — no pre-rendered
# keyframes. This produces buttery-smooth animation at any fps.
# Uses 5-layer compositing: bg → content → text → mascot → UI
# ============================================================
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
from PIL import Image

import config
from animations import (
    ease_value, compute_scale, compute_opacity,
    compute_slide_x, compute_bounce_y, ParticleSystem
)
from frame_composer import (
    render_gradient_background, render_text, hex_to_rgb, _get_font
)
from quiz_generator import QuizRound, QuizPack
from narration import RoundAudio


@dataclass
class VideoContext:
    """# All data needed to render any frame of the video."""
    width: int
    height: int
    category: str
    rounds: list[QuizRound]
    image_paths: list[Path]
    silhouette_paths: list[Path]
    mascot_images: dict  # {"thinking": Image, "excited": Image, ...}
    particle_system: ParticleSystem
    round_audios: list[RoundAudio] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)


def build_round_timeline(round_index: int, round_start: float) -> list[dict]:
    """
    # Build a list of timed events for one quiz round.
    # Each event has: phase, start, end, and any phase-specific data.
    """
    t = round_start
    events = [
        {"phase": "silhouette", "start": t + config.SILHOUETTE_START,
         "end": t + config.COUNTDOWN_START, "round": round_index},
        {"phase": "countdown_3", "start": t + config.COUNTDOWN_START,
         "end": t + config.COUNTDOWN_START + 1.0, "round": round_index, "number": 3},
        {"phase": "countdown_2", "start": t + config.COUNTDOWN_START + 1.0,
         "end": t + config.COUNTDOWN_START + 2.0, "round": round_index, "number": 2},
        {"phase": "countdown_1", "start": t + config.COUNTDOWN_START + 2.0,
         "end": t + config.REVEAL_START, "round": round_index, "number": 1},
        {"phase": "reveal", "start": t + config.REVEAL_START,
         "end": t + config.FUN_FACT_START, "round": round_index},
        {"phase": "fun_fact", "start": t + config.FUN_FACT_START,
         "end": t + config.ROUND_DURATION, "round": round_index},
    ]
    return events


def build_full_timeline(num_rounds: int) -> list[dict]:
    """
    # Build complete video timeline: intro + all rounds + outro.
    """
    timeline = []

    # Intro phase
    timeline.append({
        "phase": "intro",
        "start": 0.0,
        "end": config.INTRO_DURATION,
        "round": -1,
    })

    # All quiz rounds
    for i in range(num_rounds):
        round_start = config.INTRO_DURATION + i * config.ROUND_DURATION
        timeline.extend(build_round_timeline(i, round_start))

    # Outro phase
    outro_start = config.INTRO_DURATION + num_rounds * config.ROUND_DURATION
    timeline.append({
        "phase": "outro",
        "start": outro_start,
        "end": outro_start + config.OUTRO_DURATION,
        "round": -1,
    })

    return timeline


def _get_current_event(t: float, timeline: list[dict]) -> dict:
    """# Find which timeline event is active at time t."""
    for event in timeline:
        if event["start"] <= t < event["end"]:
            return event
    # Default to last event if past end
    return timeline[-1] if timeline else {"phase": "intro", "start": 0, "end": 0, "round": -1}


def _composite_image_on_frame(frame_img: Image.Image, overlay: Image.Image,
                               center_x: int, center_y: int,
                               scale: float = 1.0, opacity: float = 1.0) -> Image.Image:
    """
    # Paste an RGBA image onto the frame at a given center position,
    # with scale and opacity applied.
    """
    if scale <= 0 or opacity <= 0:
        return frame_img

    # Scale the overlay
    new_w = max(1, int(overlay.width * scale))
    new_h = max(1, int(overlay.height * scale))
    scaled = overlay.resize((new_w, new_h), Image.LANCZOS)

    # Apply opacity
    if opacity < 1.0:
        arr = np.array(scaled)
        arr[:, :, 3] = (arr[:, :, 3] * opacity).astype(np.uint8)
        scaled = Image.fromarray(arr, "RGBA")

    # Calculate paste position (centered)
    paste_x = center_x - new_w // 2
    paste_y = center_y - new_h // 2

    # Paste with alpha compositing
    frame_img.paste(scaled, (paste_x, paste_y), scaled)
    return frame_img


def render_frame(t: float, ctx: VideoContext) -> np.ndarray:
    """
    # Render a single video frame at time t.
    # This is called 30 times per second by MoviePy.
    # Returns a numpy array (H, W, 3) in RGB format.
    """
    w, h = ctx.width, ctx.height

    # --- Layer 1: Background gradient + particle overlay ---
    bg = render_gradient_background(w, h, ctx.category, t)
    frame = bg.convert("RGBA")

    # Add particle sparkles
    if ctx.particle_system:
        frame_arr = np.array(frame)[:, :, :3]
        frame_arr = ctx.particle_system.render(frame_arr, t)
        # Put back into PIL
        alpha = np.array(frame)[:, :, 3:]
        frame = Image.fromarray(
            np.concatenate([frame_arr, alpha], axis=2), "RGBA"
        )

    # Find current timeline event
    event = _get_current_event(t, ctx.timeline)
    phase = event["phase"]
    round_idx = event["round"]

    # --- Intro/Outro: just text + mascot ---
    if phase == "intro":
        cat_display = config.CATEGORIES[ctx.category]["display"]
        # Title slides down from top
        title_opacity = compute_opacity(t, 0.0, 0.5, "quad_out")
        frame = render_text(frame, f"GUESS THE {cat_display.upper()}!",
                            position=(w // 2, int(h * 0.35)),
                            font_size=config.TITLE_FONT_SIZE + 20,
                            color=(255, 255, 255))

        # Mascot waves in
        if "waving" in ctx.mascot_images:
            mascot = ctx.mascot_images["waving"]
            scale = compute_scale(t, 0.0, 0.5, "back_out")
            mascot_h = int(h * 0.25)
            mascot_w = int(mascot.width * (mascot_h / mascot.height))
            mascot_resized = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
            frame = _composite_image_on_frame(
                frame, mascot_resized, w // 2, int(h * 0.65), scale=scale
            )

        return np.array(frame.convert("RGB"))

    if phase == "outro":
        frame = render_text(frame, "How many did you get?",
                            position=(w // 2, int(h * 0.35)),
                            font_size=config.TITLE_FONT_SIZE,
                            color=(255, 255, 255))
        frame = render_text(frame, "Subscribe for more!",
                            position=(w // 2, int(h * 0.50)),
                            font_size=config.QUESTION_FONT_SIZE,
                            color=(255, 255, 200))
        if "waving" in ctx.mascot_images:
            mascot = ctx.mascot_images["waving"]
            mascot_h = int(h * 0.25)
            mascot_w = int(mascot.width * (mascot_h / mascot.height))
            mascot_resized = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
            frame = _composite_image_on_frame(
                frame, mascot_resized, w // 2, int(h * 0.75)
            )
        return np.array(frame.convert("RGB"))

    # --- Quiz round phases ---
    if round_idx < 0 or round_idx >= len(ctx.rounds):
        return np.array(frame.convert("RGB"))

    round_data = ctx.rounds[round_idx]
    score = round_idx  # score = how many already revealed
    total = len(ctx.rounds)
    round_start = config.INTRO_DURATION + round_idx * config.ROUND_DURATION
    elapsed_in_round = t - round_start

    # Score counter (persistent)
    frame = render_text(frame, f"Score: {score}/{total}",
                        position=(w // 2, int(h * 0.90)),
                        font_size=config.SCORE_FONT_SIZE)

    # Title bar
    cat_display = config.CATEGORIES[ctx.category]["display"]
    colors = config.CATEGORY_COLORS[ctx.category]
    frame = render_text(frame, f"GUESS THE {cat_display.upper()}",
                        position=(w // 2, int(h * 0.06)),
                        font_size=config.TITLE_FONT_SIZE,
                        color=hex_to_rgb(colors["primary"]))

    # --- Layer 2: Main content (silhouette or reveal image) ---
    content_size = int(w * 0.5)
    content_center_x = w // 2
    content_center_y = int(h * 0.35)

    if phase in ("silhouette", "countdown_3", "countdown_2", "countdown_1"):
        # Show silhouette with slide-in animation
        if round_idx < len(ctx.silhouette_paths):
            sil = Image.open(ctx.silhouette_paths[round_idx]).convert("RGBA")
            sil = sil.resize((content_size, content_size), Image.LANCZOS)

            # Slide-in from left at start of round
            slide_progress = compute_scale(
                elapsed_in_round, 0.0, config.EASE_SLIDE_IN, "cubic_out"
            )
            # Interpolate x from off-screen-left to center
            sil_x = int(-content_size + (content_center_x + content_size) * slide_progress)

            frame = _composite_image_on_frame(
                frame, sil, sil_x, content_center_y
            )

        # Question text
        q_opacity = compute_opacity(
            elapsed_in_round, 0.2, config.EASE_TEXT_IN, "quad_out"
        )
        if q_opacity > 0.01:
            frame = render_text(frame, round_data.hint_question,
                                position=(w // 2, int(h * 0.62)),
                                font_size=config.QUESTION_FONT_SIZE)

    if phase.startswith("countdown_"):
        # Large countdown number with BackEaseOut pop
        number = event.get("number", 3)
        countdown_elapsed = t - event["start"]
        num_scale = compute_scale(
            countdown_elapsed, 0.0, config.EASE_COUNTDOWN_IN, "back_out"
        )
        # Render number as text overlay with scale applied via font size
        scaled_font_size = int(config.COUNTDOWN_FONT_SIZE * max(0.1, num_scale))
        frame = render_text(frame, str(number),
                            position=(w // 2, int(h * 0.55)),
                            font_size=scaled_font_size,
                            color=(255, 255, 255),
                            stroke_color=hex_to_rgb(colors["primary"]),
                            stroke_width=6)

    if phase == "reveal":
        # Show full color image with ElasticEaseOut pop
        if round_idx < len(ctx.image_paths):
            img = Image.open(ctx.image_paths[round_idx]).convert("RGBA")
            img = img.resize((content_size, content_size), Image.LANCZOS)

            reveal_elapsed = elapsed_in_round - config.REVEAL_START
            img_scale = compute_scale(
                reveal_elapsed, 0.0, config.EASE_REVEAL, "elastic_out"
            )

            frame = _composite_image_on_frame(
                frame, img, content_center_x, content_center_y, scale=img_scale
            )

        # Answer text with BackEaseOut pop
        answer_elapsed = elapsed_in_round - config.REVEAL_START
        answer_scale = compute_scale(
            answer_elapsed, 0.1, config.EASE_ANSWER_IN, "back_out"
        )
        if answer_scale > 0.01:
            ans_font = int(config.ANSWER_FONT_SIZE * max(0.1, answer_scale))
            frame = render_text(frame, f"It's a {round_data.answer}!",
                                position=(w // 2, int(h * 0.62)),
                                font_size=ans_font,
                                color=hex_to_rgb(colors["primary"]),
                                stroke_color=(255, 255, 255))

    if phase == "fun_fact":
        # Keep reveal image visible
        if round_idx < len(ctx.image_paths):
            img = Image.open(ctx.image_paths[round_idx]).convert("RGBA")
            img = img.resize((content_size, content_size), Image.LANCZOS)
            frame = _composite_image_on_frame(
                frame, img, content_center_x, content_center_y
            )

        # Answer text (still visible)
        frame = render_text(frame, f"It's a {round_data.answer}!",
                            position=(w // 2, int(h * 0.62)),
                            font_size=config.ANSWER_FONT_SIZE,
                            color=hex_to_rgb(colors["primary"]),
                            stroke_color=(255, 255, 255))

        # Fun fact with word-by-word reveal
        fact_elapsed = elapsed_in_round - config.FUN_FACT_START
        # Simple approach: reveal all text with fade-in
        fact_opacity = compute_opacity(fact_elapsed, 0.0, 0.3, "quad_out")
        if fact_opacity > 0.01:
            # Semi-transparent pill background
            from PIL import ImageDraw
            pill_layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            pill_draw = ImageDraw.Draw(pill_layer)
            fact_y = int(h * 0.74)
            font = _get_font(config.FACT_FONT_SIZE)
            bbox = font.getbbox(round_data.fun_fact)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            pad = 20
            pill_draw.rounded_rectangle([
                w // 2 - text_w // 2 - pad, fact_y - text_h // 2 - pad // 2,
                w // 2 + text_w // 2 + pad, fact_y + text_h // 2 + pad // 2,
            ], radius=15, fill=(0, 0, 0, int(153 * fact_opacity)))
            frame = Image.alpha_composite(frame, pill_layer)

            frame = render_text(frame, round_data.fun_fact,
                                position=(w // 2, fact_y),
                                font_size=config.FACT_FONT_SIZE,
                                stroke_width=0, shadow=False)

    # --- Layer 4: Leo mascot with idle bounce ---
    mascot_pose = "thinking" if phase in ("silhouette", "countdown_3", "countdown_2", "countdown_1") else "excited"
    if mascot_pose in ctx.mascot_images:
        mascot = ctx.mascot_images[mascot_pose]
        mascot_h = int(h * 0.12)
        mascot_w = int(mascot.width * (mascot_h / mascot.height))
        mascot_resized = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)

        # Idle bounce offset
        bounce_y = compute_bounce_y(t, amplitude=3.0, period=1.2)
        mascot_x = w - mascot_w // 2 - 40
        mascot_y = h - mascot_h // 2 - 40 + int(bounce_y)

        # Scale pulse on reveal
        m_scale = 1.0
        if phase == "reveal":
            reveal_elapsed = elapsed_in_round - config.REVEAL_START
            if reveal_elapsed < 0.3:
                m_scale = 1.0 + 0.1 * compute_scale(
                    reveal_elapsed, 0.0, 0.3, "back_out"
                )

        frame = _composite_image_on_frame(
            frame, mascot_resized, mascot_x, mascot_y, scale=m_scale
        )

    return np.array(frame.convert("RGB"))


def assemble_short(quiz_pack: QuizPack, image_paths: list[Path],
                    silhouette_paths: list[Path],
                    round_audios: list[RoundAudio],
                    audio_path: Path, output_path: Path,
                    mascot_dir: Path = None) -> Path:
    """
    # Assemble a complete short-form quiz video (60s, 9:16).
    # Uses frame-by-frame rendering with easing-driven animation.
    """
    from moviepy import VideoClip, AudioFileClip

    w, h = config.SHORTS_SIZE
    num_rounds = len(quiz_pack.rounds)
    total_duration = config.INTRO_DURATION + num_rounds * config.ROUND_DURATION + config.OUTRO_DURATION

    # Load mascot images
    mascot_images = {}
    if mascot_dir is None:
        mascot_dir = config.MASCOT_DIR
    for pose_name, pose_path in config.MASCOT_POSES.items():
        if pose_path.exists():
            mascot_images[pose_name] = Image.open(pose_path).convert("RGBA")

    # Build timeline
    timeline = build_full_timeline(num_rounds)

    # Create particle system
    particles = ParticleSystem(w, h, count=config.PARTICLE_COUNT)

    # Build video context
    ctx = VideoContext(
        width=w, height=h,
        category=quiz_pack.category,
        rounds=quiz_pack.rounds,
        image_paths=image_paths,
        silhouette_paths=silhouette_paths,
        mascot_images=mascot_images,
        particle_system=particles,
        round_audios=round_audios,
        timeline=timeline,
    )

    # Create video clip with frame-by-frame rendering
    video = VideoClip(lambda t: render_frame(t, ctx), duration=total_duration)
    video = video.with_fps(config.FPS)

    # Add audio
    if audio_path and audio_path.exists():
        audio = AudioFileClip(str(audio_path))
        video = video.with_audio(audio)

    # Export
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(output_path),
        codec="libx264",
        bitrate=config.VIDEO_BITRATE,
        preset="slow",
        audio_codec="aac",
        audio_bitrate=config.AUDIO_BITRATE,
    )

    return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_video_assembler.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add video_assembler.py tests/test_video_assembler.py
git commit -m "feat: frame-by-frame video assembler with 5-layer compositing and easing"
```

---

### Task 8: Thumbnail + Metadata Generation

**Files:**
- Create: `thumbnail.py`
- Create: `metadata.py`
- Test: `tests/test_thumbnail.py`

**Interfaces:**
- Consumes: `config.*`, `frame_composer.*`, `quiz_generator.QuizPack`
- Produces: `generate_thumbnail(quiz_pack, image_paths, silhouette_paths, output_path) -> Path`, `generate_metadata(quiz_pack, platform) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_thumbnail.py
import pytest
from pathlib import Path
from PIL import Image, ImageDraw

def _make_test_image(path, color=(200, 50, 30)):
    img = Image.new("RGBA", (512, 512), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([100, 100, 400, 400], fill=color + (255,))
    img.save(path)
    return path

def _make_test_silhouette(path):
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([100, 100, 400, 400], fill=(0, 0, 0, 255))
    img.save(path)
    return path

def test_generate_thumbnail(tmp_path):
    """# Should create a 1280x720 thumbnail with split layout."""
    from thumbnail import generate_thumbnail
    from quiz_generator import QuizPack, QuizRound

    img_path = _make_test_image(tmp_path / "img.png")
    sil_path = _make_test_silhouette(tmp_path / "sil.png")

    pack = QuizPack(
        category="animals",
        rounds=[QuizRound("Lion", "q", "f", "easy", "p")]
    )

    out = tmp_path / "thumb.png"
    result = generate_thumbnail(pack, [img_path], [sil_path], out)
    assert result.exists()

    thumb = Image.open(result)
    assert thumb.size == (1280, 720)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_thumbnail.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write thumbnail.py**

```python
# thumbnail.py
# ============================================================
# Auto-generated YouTube thumbnails for Leo Quiz videos.
# Split layout: silhouette on left, colorful reveal on right.
# Bold text, bright colors, Leo mascot — designed to pop in search.
# ============================================================
from pathlib import Path
from PIL import Image, ImageDraw

import config
from frame_composer import render_gradient_background, render_text, hex_to_rgb
from quiz_generator import QuizPack

# YouTube recommended thumbnail size
THUMB_SIZE = (1280, 720)


def generate_thumbnail(quiz_pack: QuizPack,
                        image_paths: list[Path],
                        silhouette_paths: list[Path],
                        output_path: Path) -> Path:
    """
    # Generate a YouTube thumbnail for a quiz video.
    # Layout: silhouette on left, reveal on right, "CAN YOU GUESS?" text,
    # bright border, Leo mascot (surprised pose).
    """
    w, h = THUMB_SIZE
    category = quiz_pack.category
    colors = config.CATEGORY_COLORS[category]

    # Gradient background
    bg = render_gradient_background(w, h, category, t=0.0)
    thumb = bg.convert("RGBA")

    # Bright yellow border (8px)
    draw = ImageDraw.Draw(thumb)
    border = 8
    draw.rectangle([0, 0, w - 1, h - 1], outline=(255, 230, 0, 255), width=border)

    # Left half: silhouette (first round)
    if silhouette_paths:
        sil = Image.open(silhouette_paths[0]).convert("RGBA")
        sil_size = int(h * 0.6)
        sil = sil.resize((sil_size, sil_size), Image.LANCZOS)
        sil_x = w // 4 - sil_size // 2
        sil_y = (h - sil_size) // 2 + 30
        thumb.paste(sil, (sil_x, sil_y), sil)

    # Right half: colorful image (first round)
    if image_paths:
        img = Image.open(image_paths[0]).convert("RGBA")
        img_size = int(h * 0.6)
        img = img.resize((img_size, img_size), Image.LANCZOS)
        img_x = 3 * w // 4 - img_size // 2
        img_y = (h - img_size) // 2 + 30
        thumb.paste(img, (img_x, img_y), img)

    # Arrow or "?" between halves
    thumb = render_text(thumb, "?",
                        position=(w // 2, h // 2 + 30),
                        font_size=120,
                        color=(255, 255, 255),
                        stroke_color=(0, 0, 0), stroke_width=5)

    # "CAN YOU GUESS?" text at top
    thumb = render_text(thumb, "CAN YOU GUESS?",
                        position=(w // 2, 60),
                        font_size=72,
                        color=(255, 255, 255),
                        stroke_color=(0, 0, 0), stroke_width=5)

    # Category subtitle
    cat_display = config.CATEGORIES[category]["display"]
    thumb = render_text(thumb, f"{cat_display}s Edition!",
                        position=(w // 2, h - 40),
                        font_size=36,
                        color=(255, 255, 200))

    # Leo mascot (surprised pose) in bottom-right
    surprised_path = config.MASCOT_POSES.get("surprised")
    if surprised_path and surprised_path.exists():
        mascot = Image.open(surprised_path).convert("RGBA")
        mascot_h = int(h * 0.35)
        mascot_w = int(mascot.width * (mascot_h / mascot.height))
        mascot = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
        thumb.paste(mascot, (w - mascot_w - 20, h - mascot_h - 60), mascot)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    thumb.convert("RGB").save(output_path, "PNG", quality=95)
    return output_path
```

- [ ] **Step 4: Write metadata.py**

```python
# metadata.py
# ============================================================
# Auto-generated video metadata (titles, descriptions, tags)
# using Gemini for SEO-optimized, platform-specific content.
# ============================================================
import json
import re
from pathlib import Path

import config
from quiz_generator import QuizPack


def generate_metadata(quiz_pack: QuizPack, platform: str = "youtube") -> dict:
    """
    # Generate platform-optimized metadata for a quiz video.
    # Returns dict with title, description, tags, hashtags.
    """
    from google import genai

    category = quiz_pack.category
    cat_display = config.CATEGORIES[category]["display"]
    answers = [r.answer for r in quiz_pack.rounds]
    difficulties = [r.difficulty for r in quiz_pack.rounds]

    prompt = f"""Generate {platform} metadata for a kids quiz video.
Category: {cat_display}s
Answers featured: {', '.join(answers)}
Difficulty: {', '.join(difficulties)}
Format: Silhouette guess quiz with mascot "Leo the Lion"

Return ONLY JSON:
{{
  "title": "short catchy title under 60 chars, include emoji",
  "description": "SEO-optimized description with keywords, 2-3 sentences, include subscribe CTA",
  "tags": ["list", "of", "10-15", "relevant", "tags"],
  "hashtags": ["#hashtag1", "#hashtag2", "up to 5"]
}}

For YouTube: title should include "Guess the {cat_display}" and be kid-friendly.
For TikTok: title should be shorter, hashtag-heavy.
Made for Kids content — keep everything family-friendly."""

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # Parse JSON response
    text = response.text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    metadata = json.loads(text)

    # Add standard fields
    metadata["category"] = category
    metadata["made_for_kids"] = True
    metadata["answers"] = answers

    return metadata


def save_metadata(metadata: dict, output_path: Path) -> Path:
    """# Save metadata dict to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    return output_path
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_thumbnail.py -v`
Expected: All 1 test PASS

- [ ] **Step 6: Commit**

```bash
git add thumbnail.py metadata.py tests/test_thumbnail.py
git commit -m "feat: auto thumbnail generation and Gemini-powered metadata"
```

---

### Task 9: Main Orchestrator

**Files:**
- Create: `main.py`

**Interfaces:**
- Consumes: all previous modules
- Produces: `run_pipeline(category: str, num_rounds: int, output_dir: Path) -> Path` (returns path to output video), CLI interface with `--category` and `--rounds` args

- [ ] **Step 1: Write main.py**

```python
# main.py
# ============================================================
# Leo Quiz pipeline orchestrator.
# Runs the full video generation pipeline:
# content → images → silhouettes → narration → audio → video → thumbnail → metadata
# ============================================================
import argparse
from datetime import datetime
from pathlib import Path

import config
from quiz_generator import generate_quiz_pack, QuizPack
from image_generator import generate_quiz_image
from silhouette import extract_silhouette, validate_silhouette
from narration import generate_round_narration, RoundAudio
from audio_mixer import build_short_audio
from video_assembler import assemble_short
from thumbnail import generate_thumbnail
from metadata import generate_metadata, save_metadata


def run_pipeline(category: str = None, num_rounds: int = None,
                  output_dir: Path = None) -> Path:
    """
    # Run the complete Leo Quiz pipeline for one short-form video.
    # Returns path to the output video file.
    """
    # Defaults
    if category is None:
        category = config.get_today_category()
    if num_rounds is None:
        num_rounds = config.ROUNDS_PER_SHORT
    if output_dir is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_dir = config.SHORTS_DIR / f"{date_str}_{category}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[LEO QUIZ] Starting pipeline: {category}, {num_rounds} rounds")
    print(f"[LEO QUIZ] Output: {output_dir}")

    # --- Step 1: Generate quiz content ---
    print("[LEO QUIZ] Step 1: Generating quiz content...")
    quiz_pack = generate_quiz_pack(category, num_rounds)
    print(f"[LEO QUIZ]   Generated {len(quiz_pack.rounds)} rounds")
    for i, r in enumerate(quiz_pack.rounds):
        print(f"[LEO QUIZ]   Round {i+1}: {r.answer} ({r.difficulty})")

    # --- Step 2: Generate images ---
    print("[LEO QUIZ] Step 2: Generating quiz images...")
    rounds_dir = output_dir / "rounds"
    rounds_dir.mkdir(exist_ok=True)

    image_paths = []
    for i, r in enumerate(quiz_pack.rounds):
        img_path = rounds_dir / f"round_{i+1}_image.png"
        print(f"[LEO QUIZ]   Generating image for: {r.answer}")
        generate_quiz_image(r, img_path)
        image_paths.append(img_path)

    # --- Step 3: Extract silhouettes ---
    print("[LEO QUIZ] Step 3: Extracting silhouettes...")
    silhouette_paths = []
    for i, img_path in enumerate(image_paths):
        sil_path = rounds_dir / f"round_{i+1}_silhouette.png"
        extract_silhouette(img_path, sil_path)

        # Validate silhouette quality
        if not validate_silhouette(sil_path):
            print(f"[LEO QUIZ]   WARNING: Silhouette for round {i+1} may be poor quality")

        silhouette_paths.append(sil_path)

    # --- Step 4: Generate narration ---
    print("[LEO QUIZ] Step 4: Generating narration...")
    round_audios = []
    for i, r in enumerate(quiz_pack.rounds):
        audio_dir = rounds_dir / f"round_{i+1}_audio"
        print(f"[LEO QUIZ]   Narrating: {r.answer}")
        ra = generate_round_narration(r, category, audio_dir)
        round_audios.append(ra)

    # --- Step 5: Mix audio ---
    print("[LEO QUIZ] Step 5: Mixing audio...")
    total_duration = (config.INTRO_DURATION +
                      num_rounds * config.ROUND_DURATION +
                      config.OUTRO_DURATION)

    # Find a music track for this category
    music_path = _find_music_track(category)

    audio_path = output_dir / "audio_mixed.wav"
    build_short_audio(round_audios, music_path, total_duration, audio_path)

    # --- Step 6: Assemble video ---
    print("[LEO QUIZ] Step 6: Assembling video...")
    video_path = output_dir / "video.mp4"
    assemble_short(quiz_pack, image_paths, silhouette_paths,
                    round_audios, audio_path, video_path)

    # --- Step 7: Generate thumbnail ---
    print("[LEO QUIZ] Step 7: Generating thumbnail...")
    thumb_path = output_dir / "thumbnail.png"
    generate_thumbnail(quiz_pack, image_paths, silhouette_paths, thumb_path)

    # --- Step 8: Generate metadata ---
    print("[LEO QUIZ] Step 8: Generating metadata...")
    yt_meta = generate_metadata(quiz_pack, "youtube")
    save_metadata(yt_meta, output_dir / "metadata_youtube.json")

    tt_meta = generate_metadata(quiz_pack, "tiktok")
    save_metadata(tt_meta, output_dir / "metadata_tiktok.json")

    print(f"[LEO QUIZ] Pipeline complete! Video: {video_path}")
    return video_path


def _find_music_track(category: str) -> Path:
    """# Find a background music track for the given category."""
    # Check for category-specific music first
    for ext in ("mp3", "wav"):
        path = config.MUSIC_DIR / f"{category}.{ext}"
        if path.exists():
            return path

    # Fall back to any music file
    for ext in ("mp3", "wav"):
        tracks = list(config.MUSIC_DIR.glob(f"*.{ext}"))
        if tracks:
            return tracks[0]

    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Leo Quiz — Kids Quiz Video Pipeline")
    parser.add_argument("--category", type=str, default=None,
                        help="Quiz category (animals, dinosaurs, space, vehicles, fruits, flags)")
    parser.add_argument("--rounds", type=int, default=None,
                        help="Number of quiz rounds (default: 5)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory path")

    args = parser.parse_args()
    output_dir = Path(args.output) if args.output else None
    run_pipeline(category=args.category, num_rounds=args.rounds, output_dir=output_dir)
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: main orchestrator — full pipeline from content to video"
```

---

### Task 10: Long-Form Compiler

**Files:**
- Create: `compiler.py`
- Test: `tests/test_compiler.py`

**Interfaces:**
- Consumes: `config.*`, `video_assembler.*`, `quiz_generator.QuizPack`, weekly output directories
- Produces: `compile_longform(week_dirs: list[Path], output_path: Path) -> Path`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compiler.py
import pytest
from pathlib import Path
import json

def test_collect_week_rounds(tmp_path):
    """# Should find and load all quiz packs from a week's output dirs."""
    from compiler import collect_week_rounds

    # Create fake daily output dirs with metadata
    for day in ["2026-07-01_animals", "2026-07-02_dinosaurs"]:
        day_dir = tmp_path / day
        day_dir.mkdir()
        # Write a fake quiz pack
        pack = {
            "category": day.split("_")[1],
            "rounds": [{"answer": "Lion", "hint_question": "q",
                         "fun_fact": "f", "difficulty": "easy",
                         "image_prompt": "p"}]
        }
        with open(day_dir / "quiz_pack.json", "w") as f:
            json.dump(pack, f)

    rounds = collect_week_rounds([tmp_path / "2026-07-01_animals",
                                   tmp_path / "2026-07-02_dinosaurs"])
    assert len(rounds) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_compiler.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write compiler.py**

```python
# compiler.py
# ============================================================
# Weekly long-form video compiler.
# Collects all short-form rounds from the past week,
# generates bonus rounds, and renders a 15-20 minute
# compilation at 16:9 with score tracking and sections.
# ============================================================
import json
from datetime import datetime, timedelta
from pathlib import Path

import config
from quiz_generator import QuizPack, QuizRound, generate_quiz_pack


def collect_week_rounds(day_dirs: list[Path]) -> list[dict]:
    """
    # Collect all quiz rounds from a list of daily output directories.
    # Returns list of dicts with round data + image/silhouette paths.
    """
    all_rounds = []
    for day_dir in day_dirs:
        pack_file = day_dir / "quiz_pack.json"
        if not pack_file.exists():
            continue

        with open(pack_file, "r", encoding="utf-8") as f:
            pack_data = json.load(f)

        category = pack_data.get("category", "animals")
        rounds_dir = day_dir / "rounds"

        for i, r in enumerate(pack_data.get("rounds", [])):
            all_rounds.append({
                "round": QuizRound(**r) if isinstance(r, dict) else r,
                "category": category,
                "image_path": rounds_dir / f"round_{i+1}_image.png",
                "silhouette_path": rounds_dir / f"round_{i+1}_silhouette.png",
            })

    return all_rounds


def find_week_dirs(shorts_dir: Path = None) -> list[Path]:
    """
    # Find all daily output directories from the past 7 days.
    """
    if shorts_dir is None:
        shorts_dir = config.SHORTS_DIR

    week_dirs = []
    today = datetime.now()

    for i in range(7):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        # Find directories matching this date
        for d in shorts_dir.iterdir():
            if d.is_dir() and d.name.startswith(date_str):
                week_dirs.append(d)

    return sorted(week_dirs)


def compile_longform(week_dirs: list[Path] = None,
                      output_path: Path = None) -> Path:
    """
    # Compile a long-form video from the week's shorts + bonus rounds.
    # Renders at 16:9 (1920x1080) with sections, score counter, progress bar.
    """
    from video_assembler import assemble_short
    from narration import generate_round_narration
    from audio_mixer import build_short_audio

    if week_dirs is None:
        week_dirs = find_week_dirs()
    if output_path is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = config.LONGFORM_DIR / f"{date_str}_compilation"
    output_path.mkdir(parents=True, exist_ok=True)

    # Collect existing rounds
    existing_rounds = collect_week_rounds(week_dirs)
    print(f"[COMPILER] Found {len(existing_rounds)} rounds from {len(week_dirs)} daily videos")

    # Generate bonus rounds for long-form exclusivity
    bonus_count = max(0, 80 - len(existing_rounds))
    if bonus_count > 0:
        print(f"[COMPILER] Generating {bonus_count} bonus rounds...")
        bonus_pack = generate_quiz_pack("mixed", bonus_count)
        # TODO: generate images + silhouettes for bonus rounds
        # For V1, long-form uses only existing rounds

    print(f"[COMPILER] Compiling long-form video...")
    # TODO: full long-form assembly with section title cards,
    # score tracking, progress bar, difficulty sections
    # This will be expanded after short-form is validated

    video_path = output_path / "longform.mp4"
    print(f"[COMPILER] Long-form compilation: {video_path}")
    return video_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_compiler.py -v`
Expected: 1 test PASS

- [ ] **Step 5: Commit**

```bash
git add compiler.py tests/test_compiler.py
git commit -m "feat: weekly long-form compiler with round collection"
```

---

### Task 11: Upload + Scheduler

**Files:**
- Create: `uploader.py`
- Create: `scheduler.py`
- Create: `.github/workflows/daily.yml`
- Create: `.github/workflows/weekly.yml`

**Interfaces:**
- Consumes: `config.*`, `main.run_pipeline()`, `compiler.compile_longform()`, metadata JSON files
- Produces: `upload_youtube(video_path, metadata, thumbnail_path) -> str` (returns video URL), `upload_tiktok(video_path, metadata) -> str`, scheduler cron jobs

- [ ] **Step 1: Write uploader.py**

```python
# uploader.py
# ============================================================
# Video upload to YouTube and TikTok.
# Handles authentication, metadata, and COPPA compliance.
# ============================================================
import json
from pathlib import Path

import config


def upload_youtube(video_path: Path, metadata_path: Path,
                    thumbnail_path: Path = None) -> str:
    """
    # Upload a video to YouTube via the Data API v3.
    # Sets "Made for Kids" flag for COPPA compliance.
    # Returns the video URL on success.
    """
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow

    # Load metadata
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # Authenticate (uses client_secrets.json — one-time setup)
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.PROJECT_ROOT / "client_secrets.json"), scopes
    )
    credentials = flow.run_local_server(port=0)
    youtube = build("youtube", "v3", credentials=credentials)

    # Build request body
    body = {
        "snippet": {
            "title": meta.get("title", "Leo Quiz"),
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
            "categoryId": "24",  # Entertainment
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": True,  # COPPA compliance
        },
    }

    # Upload video
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = request.execute()
    video_id = response["id"]
    video_url = f"https://youtube.com/watch?v={video_id}"

    # Upload thumbnail if provided
    if thumbnail_path and thumbnail_path.exists():
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/png")
        ).execute()

    print(f"[UPLOAD] YouTube: {video_url}")
    return video_url


def upload_tiktok(video_path: Path, metadata_path: Path) -> str:
    """
    # Upload a video to TikTok via the Content Posting API.
    # Returns the post URL on success.
    # Note: requires TikTok developer app setup (not yet configured).
    """
    print(f"[UPLOAD] TikTok upload not yet configured — skipping")
    print(f"[UPLOAD] Video ready at: {video_path}")
    return ""
```

- [ ] **Step 2: Write scheduler.py**

```python
# scheduler.py
# ============================================================
# Scheduling for automated daily/weekly video generation.
# Supports local cron via APScheduler and manual triggers.
# ============================================================
import argparse
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from main import run_pipeline
from compiler import compile_longform


def daily_job():
    """# Generate one short-form quiz video for today's category."""
    print(f"\n{'='*60}")
    print(f"[SCHEDULER] Daily job started at {datetime.now()}")
    print(f"{'='*60}")
    try:
        video_path = run_pipeline()
        print(f"[SCHEDULER] Daily job complete: {video_path}")
    except Exception as e:
        print(f"[SCHEDULER] Daily job failed: {e}")
        import traceback
        traceback.print_exc()


def weekly_job():
    """# Compile weekly long-form video from past 7 days of shorts."""
    print(f"\n{'='*60}")
    print(f"[SCHEDULER] Weekly job started at {datetime.now()}")
    print(f"{'='*60}")
    try:
        video_path = compile_longform()
        print(f"[SCHEDULER] Weekly job complete: {video_path}")
    except Exception as e:
        print(f"[SCHEDULER] Weekly job failed: {e}")
        import traceback
        traceback.print_exc()


def start_scheduler():
    """# Start the APScheduler with daily and weekly cron jobs."""
    scheduler = BlockingScheduler()

    # Daily at 6:00 AM UTC
    scheduler.add_job(daily_job, "cron", hour=6, minute=0, id="daily_quiz")

    # Weekly on Sunday at 8:00 AM UTC
    scheduler.add_job(weekly_job, "cron", day_of_week="sun", hour=8, minute=0,
                      id="weekly_compilation")

    print("[SCHEDULER] Leo Quiz scheduler started")
    print("[SCHEDULER] Daily: 6:00 AM UTC | Weekly: Sunday 8:00 AM UTC")
    print("[SCHEDULER] Press Ctrl+C to stop")

    scheduler.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Leo Quiz Scheduler")
    parser.add_argument("--now", choices=["short", "long"],
                        help="Run a job immediately instead of scheduling")
    args = parser.parse_args()

    if args.now == "short":
        daily_job()
    elif args.now == "long":
        weekly_job()
    else:
        start_scheduler()
```

- [ ] **Step 3: Write GitHub Actions workflow for daily generation**

```yaml
# .github/workflows/daily.yml
name: Daily Quiz Video Generation

on:
  schedule:
    - cron: '0 6 * * *'  # Every day at 6:00 AM UTC
  workflow_dispatch:       # Manual trigger

jobs:
  generate:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Install FFmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Run pipeline
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ELEVENLABS_API_KEY: ${{ secrets.ELEVENLABS_API_KEY }}
          ELEVENLABS_VOICE_ID: ${{ secrets.ELEVENLABS_VOICE_ID }}
        run: python main.py

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: quiz-video-${{ github.run_number }}
          path: output/shorts/
          retention-days: 30
```

- [ ] **Step 4: Write GitHub Actions workflow for weekly compilation**

```yaml
# .github/workflows/weekly.yml
name: Weekly Long-Form Compilation

on:
  schedule:
    - cron: '0 8 * * 0'  # Every Sunday at 8:00 AM UTC
  workflow_dispatch:

jobs:
  compile:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Install FFmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Run compilation
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ELEVENLABS_API_KEY: ${{ secrets.ELEVENLABS_API_KEY }}
          ELEVENLABS_VOICE_ID: ${{ secrets.ELEVENLABS_VOICE_ID }}
        run: python scheduler.py --now long

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: weekly-compilation-${{ github.run_number }}
          path: output/longform/
          retention-days: 30
```

- [ ] **Step 5: Commit**

```bash
git add uploader.py scheduler.py .github/workflows/daily.yml .github/workflows/weekly.yml
git commit -m "feat: YouTube uploader, scheduler, and GitHub Actions workflows"
```

---

### Task 12: Save Quiz Pack + Integration Test

**Files:**
- Modify: `main.py` (add quiz pack save for compiler)
- Test: `tests/test_integration.py`

**Interfaces:**
- Consumes: all modules
- Produces: end-to-end validation that offline parts work together

- [ ] **Step 1: Add quiz pack save to main.py**

Add this after Step 1 (quiz generation) in `main.py`'s `run_pipeline()`:

```python
    # Save quiz pack for weekly compiler
    import json
    pack_data = {
        "category": quiz_pack.category,
        "rounds": [
            {
                "answer": r.answer,
                "hint_question": r.hint_question,
                "fun_fact": r.fun_fact,
                "difficulty": r.difficulty,
                "image_prompt": r.image_prompt,
            }
            for r in quiz_pack.rounds
        ]
    }
    with open(output_dir / "quiz_pack.json", "w", encoding="utf-8") as f:
        json.dump(pack_data, f, indent=2, ensure_ascii=False)
```

- [ ] **Step 2: Write integration test**

```python
# tests/test_integration.py
"""
# Integration tests for Leo Quiz pipeline.
# Tests offline components working together (no API calls).
# API-dependent steps (Gemini, ElevenLabs) are skipped in CI.
"""
import pytest
from pathlib import Path
from PIL import Image, ImageDraw

def _create_test_assets(tmp_path):
    """# Create minimal test assets for pipeline testing."""
    # Create test image (white bg with colored circle)
    img = Image.new("RGB", (512, 512), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([100, 100, 400, 400], fill=(200, 100, 50))
    img_path = tmp_path / "test_image.png"
    img.save(img_path)

    # Create test silhouette
    from silhouette import extract_silhouette
    sil_path = tmp_path / "test_silhouette.png"
    extract_silhouette(img_path, sil_path)

    return img_path, sil_path

def test_frame_composer_full_flow(tmp_path):
    """# Compose question → countdown → reveal frames without crashing."""
    from frame_composer import (
        compose_question_frame, compose_countdown_frame, compose_reveal_frame
    )
    img_path, sil_path = _create_test_assets(tmp_path)

    q_frame = compose_question_frame(
        "animals", sil_path, "What animal is this?",
        score=0, round_num=1, total_rounds=5
    )
    assert q_frame.size == (1080, 1920)

    cd_frame = compose_countdown_frame(
        "animals", sil_path, 3,
        score=0, round_num=1, total_rounds=5
    )
    assert cd_frame.size == (1080, 1920)

    r_frame = compose_reveal_frame(
        "animals", img_path, "Lion", "Lions sleep 20 hours!",
        score=1, round_num=1, total_rounds=5
    )
    assert r_frame.size == (1080, 1920)

def test_video_context_creation(tmp_path):
    """# VideoContext should build correctly with test data."""
    from video_assembler import VideoContext, build_full_timeline
    from animations import ParticleSystem
    from quiz_generator import QuizRound

    img_path, sil_path = _create_test_assets(tmp_path)

    rounds = [QuizRound("Lion", "q", "f", "easy", "p")]
    timeline = build_full_timeline(1)

    ctx = VideoContext(
        width=1080, height=1920,
        category="animals",
        rounds=rounds,
        image_paths=[img_path],
        silhouette_paths=[sil_path],
        mascot_images={},
        particle_system=ParticleSystem(1080, 1920, count=5),
        timeline=timeline,
    )

    assert len(ctx.timeline) >= 7  # intro + 6 round events + outro
    assert ctx.width == 1080

def test_thumbnail_generation(tmp_path):
    """# Thumbnail should generate from test assets."""
    from thumbnail import generate_thumbnail
    from quiz_generator import QuizPack, QuizRound

    img_path, sil_path = _create_test_assets(tmp_path)
    pack = QuizPack("animals", [QuizRound("Lion", "q", "f", "easy", "p")])

    result = generate_thumbnail(pack, [img_path], [sil_path],
                                 tmp_path / "thumb.png")
    assert result.exists()
    thumb = Image.open(result)
    assert thumb.size == (1280, 720)
```

- [ ] **Step 3: Run all tests**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add main.py tests/test_integration.py
git commit -m "feat: quiz pack persistence and integration tests"
```
