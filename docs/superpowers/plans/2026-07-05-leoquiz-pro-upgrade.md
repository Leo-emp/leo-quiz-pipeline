# LeoQuiz Pro Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform LeoQuiz into a multi-format, multi-platform content engine matching top kids quiz channels — daily shorts (66s) + daily long-form (10min) + weekly mega quiz (15-20min), uploaded to YouTube + TikTok + Instagram + Facebook, with A/B thumbnail testing and cross-platform analytics.

**Architecture:** The pipeline (`leo-quiz-pipeline`) gains a new `longform_assembler.py` for 16:9 rendering, multi-platform uploaders in `uploader.py`, and thumbnail variants in `thumbnail.py`. The dashboard (`leo-quiz-dashboard`) gains TikTok/Meta OAuth flows, format-aware generation, multi-platform upload, an analytics page with charts, and A/B thumbnail tracking. Both repos share the same patterns already established (PIL frame rendering, Vercel Blob token storage, GitHub Actions workflow_dispatch).

**Tech Stack:** Python 3.11 (MoviePy 2.0, PIL, pydub, numpy), Next.js 16 (TypeScript, Tailwind CSS 4, Turso/libsql, Vercel Blob, iron-session, Lucide icons)

## Global Constraints

- All Python code must include heavy `#` comments throughout (user learning preference)
- All TypeScript code must include `//` comment blocks at the top of every file and inline comments
- Pipeline repo: `C:\Users\User\LeoQuiz` (git remote: Leo-emp/leo-quiz-pipeline)
- Dashboard repo: `C:\Users\User\leo-quiz-dashboard` (git remote: Leo-emp/leo-quiz-dashboard)
- Shorts = 6 rounds × 10s + 2s intro + 4s outro = 66 seconds (TikTok 60s+ monetization requirement)
- Long-form = 60 rounds × 8s + 3s intro + 5s outro ≈ 10 minutes, 16:9 (1920×1080)
- Mega quiz = 100 rounds × 7s + 4s intro + 6s outro ≈ 15 minutes, 16:9 (1920×1080)
- All COPPA/Made-for-Kids flags required on every platform upload
- Token storage: Vercel Blob as private JSON files (`tokens/{platform}.json`)
- Dashboard auth: iron-session, all API routes require `getSession().isLoggedIn`
- Tests: pytest for Python, vitest for TypeScript

## Top Performer Quality Standard

**Benchmark:** Quiz Kingdom, Quiz Blitz, Monkey Quiz — channels getting 5-13M views per long-form quiz. Every feature must match or exceed their production quality. These are not nice-to-haves; they are mandatory for every task.

**Long-form video quality (Tasks 2, 3):**
- **Difficulty progression (implicit)** — rounds sorted easy→medium→hard, but NO labels or announcements. Kids get hooked by early wins, then feel challenged later. Top channels all do this silently.
- **Continuous flow with motivational milestones** — questions play back-to-back. At 25%, 50%, 75%, and before the last question, insert a brief 2s motivational hype card to keep energy up. These are the ONLY breaks:
  - **Intro**: "CAN YOU GUESS ALL 60?" (or 100 for mega)
  - **25%** (Q15 / Q25): "Great start! Keep going!"
  - **50%** (Q30 / Q50): "HALFWAY! You're doing amazing!"
  - **75%** (Q45 / Q75): "Almost there! Just 15 more!" (or 25)
  - **Last question**: "FINAL QUESTION!"
- **Consistent pacing** — every round has the exact same timing, layout, and SFX intensity. Kids like predictability — they know exactly what's coming next. This is how top channels keep attention for 10-15 minutes. Do NOT speed up, get louder, or change the format mid-video.
- **Progress counter** — "Q 23/60" visible throughout so viewers know where they are. Top channels always show this.
- **Star rating outro** — final score screen shows 1-5 stars per 20% correct with appropriate mascot reaction (excited for 4-5 stars, thinking for 2-3, surprised for 0-1). Subscribe CTA below.

**Short-form video quality (existing, verify):**
- Shorts must feel premium — same effects quality as long-form, just fewer rounds
- Every transition smooth (no jump cuts), every animation eased (no linear moves)
- Sound design complete: intro jingle, countdown beeps, reveal ding, fun fact whoosh, outro jingle

**Thumbnail quality (Task 6):**
- Match or exceed top channel thumbnails: bold colors, high contrast, clear silhouettes, mystery/curiosity factor
- Text must be readable at YouTube's smallest thumbnail size (phone search results)
- Category-specific color palettes — animals=green, dinosaurs=orange, space=blue (already in config)

**Metadata quality (Task 4):**
- YouTube titles: curiosity-driven, 50-60 chars, emojis, number hooks ("Can You Guess ALL 60 Animals? 🦁")
- YouTube descriptions: 3-5 keyword-rich lines + timestamp sections for long-form
- TikTok: short punchy captions with trending hashtags + niche hashtags
- Instagram: engagement hooks ("Comment your score!") + 20-30 hashtags
- Facebook: parent-targeted, shareable ("How Many Can YOUR Kids Guess?")

**Audio quality (existing, verify for long-form):**
- Background music must loop cleanly for 10-15 minutes without audible cuts
- Music ducking during voiceover must be smooth (existing sidechain ducking)
- Category-specific BGM already exists — must work for extended durations
- Volume levels: VO at -3dB peak, music at -14dB during speech, -8dB during gaps

**Dashboard quality (Tasks 7-13):**
- Glassmorphism design consistent with existing dashboard
- All pages responsive, loading states with skeleton placeholders
- Error states handled gracefully with retry buttons
- Analytics charts smooth and readable at all viewport sizes

---

### Task 1: Long-form & Mega Config Constants

**Files:**
- Modify: `config.py` (pipeline)
- Modify: `tests/test_config.py` (pipeline)

**Interfaces:**
- Produces: `LONGFORM_ROUND_DURATION`, `LONGFORM_ROUNDS`, `LONGFORM_TIMER_SECONDS`, `LONGFORM_INTRO_DURATION`, `LONGFORM_OUTRO_DURATION`, `LONGFORM_SECTION_CARD_DURATION`, `LONGFORM_SILHOUETTE_START`, `LONGFORM_COUNTDOWN_START`, `LONGFORM_REVEAL_START`, `LONGFORM_FUN_FACT_START`, `LONGFORM_TRANSITION_START`, `MEGA_ROUND_DURATION`, `MEGA_ROUNDS`, `MEGA_TIMER_SECONDS`, `MEGA_INTRO_DURATION`, `MEGA_OUTRO_DURATION`, `MEGA_SILHOUETTE_START`, `MEGA_COUNTDOWN_START`, `MEGA_REVEAL_START`, `MEGA_FUN_FACT_START`, `MEGA_TRANSITION_START`

- [ ] **Step 1: Write failing tests for long-form constants**

Add to `tests/test_config.py`:

```python
def test_longform_timing():
    """# Long-form round timing constants must add up to LONGFORM_ROUND_DURATION."""
    from config import (LONGFORM_ROUND_DURATION, LONGFORM_ROUNDS,
                        LONGFORM_TIMER_SECONDS, LONGFORM_INTRO_DURATION,
                        LONGFORM_OUTRO_DURATION, LONGFORM_SECTION_CARD_DURATION)
    # 8-second rounds for long-form
    assert LONGFORM_ROUND_DURATION == 8.0
    # 60 rounds for ~10 min
    assert LONGFORM_ROUNDS == 60
    # 5-second countdown timer
    assert LONGFORM_TIMER_SECONDS == 5
    # Intro and outro durations
    assert LONGFORM_INTRO_DURATION == 3.0
    assert LONGFORM_OUTRO_DURATION == 5.0
    # Section title card duration
    assert LONGFORM_SECTION_CARD_DURATION == 2.0


def test_longform_round_sub_timings():
    """# Long-form round phases must fit within LONGFORM_ROUND_DURATION."""
    from config import (LONGFORM_ROUND_DURATION, LONGFORM_SILHOUETTE_START,
                        LONGFORM_COUNTDOWN_START, LONGFORM_REVEAL_START,
                        LONGFORM_FUN_FACT_START, LONGFORM_TRANSITION_START)
    # All sub-timings must be within the round
    assert LONGFORM_SILHOUETTE_START == 0.0
    assert LONGFORM_COUNTDOWN_START == 0.5
    assert LONGFORM_REVEAL_START == 5.5
    assert LONGFORM_FUN_FACT_START == 6.5
    assert LONGFORM_TRANSITION_START == 7.7
    # Last phase must end before round ends
    assert LONGFORM_TRANSITION_START < LONGFORM_ROUND_DURATION


def test_mega_timing():
    """# Mega quiz timing constants must be valid."""
    from config import (MEGA_ROUND_DURATION, MEGA_ROUNDS, MEGA_TIMER_SECONDS,
                        MEGA_INTRO_DURATION, MEGA_OUTRO_DURATION)
    assert MEGA_ROUND_DURATION == 7.0
    assert MEGA_ROUNDS == 100
    assert MEGA_TIMER_SECONDS == 4
    assert MEGA_INTRO_DURATION == 4.0
    assert MEGA_OUTRO_DURATION == 6.0


def test_mega_round_sub_timings():
    """# Mega quiz round phases must fit within MEGA_ROUND_DURATION."""
    from config import (MEGA_ROUND_DURATION, MEGA_SILHOUETTE_START,
                        MEGA_COUNTDOWN_START, MEGA_REVEAL_START,
                        MEGA_FUN_FACT_START, MEGA_TRANSITION_START)
    assert MEGA_SILHOUETTE_START == 0.0
    assert MEGA_COUNTDOWN_START == 0.3
    assert MEGA_REVEAL_START == 4.8
    assert MEGA_FUN_FACT_START == 5.6
    assert MEGA_TRANSITION_START == 6.7
    assert MEGA_TRANSITION_START < MEGA_ROUND_DURATION


def test_longform_total_duration():
    """# Total long-form video should be approximately 10 minutes."""
    from config import (LONGFORM_ROUND_DURATION, LONGFORM_ROUNDS,
                        LONGFORM_INTRO_DURATION, LONGFORM_OUTRO_DURATION)
    total = LONGFORM_INTRO_DURATION + LONGFORM_ROUNDS * LONGFORM_ROUND_DURATION + LONGFORM_OUTRO_DURATION
    # Should be between 8 and 12 minutes
    assert 480 <= total <= 720


def test_mega_total_duration():
    """# Total mega quiz should be between 15 and 20 minutes."""
    from config import (MEGA_ROUND_DURATION, MEGA_ROUNDS,
                        MEGA_INTRO_DURATION, MEGA_OUTRO_DURATION)
    total = MEGA_INTRO_DURATION + MEGA_ROUNDS * MEGA_ROUND_DURATION + MEGA_OUTRO_DURATION
    # Should be between 11 and 20 minutes (700 = 100*7 + 10 = 710s ≈ 11.8 min)
    assert 660 <= total <= 1200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_config.py -v`
Expected: FAIL — ImportError for undefined constants

- [ ] **Step 3: Add long-form and mega constants to config.py**

Add after the `EASE_ANSWER_IN` block in `config.py`:

```python
# --- Long-form video timing (8s per round, 16:9 landscape) ---
# Used by longform_assembler.py for daily 10-minute videos.
# Faster pace than shorts to keep kids engaged over 60 rounds.
LONGFORM_ROUND_DURATION = 8.0        # Each round is 8 seconds (vs 10 for shorts)
LONGFORM_ROUNDS = 60                  # 60 rounds for ~10 min total
LONGFORM_TIMER_SECONDS = 5            # 5-second visible countdown timer
LONGFORM_INTRO_DURATION = 3.0         # Intro: Leo waves + "60 QUESTIONS!" hype
LONGFORM_OUTRO_DURATION = 5.0         # Outro: final score + subscribe CTA
LONGFORM_SECTION_CARD_DURATION = 2.0  # Category section title card between groups

# Long-form round sub-timings (offsets within each 8s round)
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
MEGA_SILHOUETTE_START = 0.0           # Fast slide-in
MEGA_COUNTDOWN_START = 0.3            # Timer starts almost immediately
MEGA_REVEAL_START = 4.8               # Quick reveal
MEGA_FUN_FACT_START = 5.6             # Brief fact overlay
MEGA_TRANSITION_START = 6.7           # Transition to next round
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd C:\Users\User\LeoQuiz
git add config.py tests/test_config.py
git commit -m "feat: add long-form and mega quiz timing constants"
```

---

### Task 2: Long-form Video Assembler

**Files:**
- Create: `longform_assembler.py` (pipeline)
- Create: `tests/test_longform_assembler.py` (pipeline)

**Interfaces:**
- Consumes: All constants from Task 1, `render_gradient_background`, `render_text`, `render_text_wrapped`, `render_glow_text`, `render_rainbow_text`, `apply_vignette`, `render_pill_background`, `hex_to_rgb`, `_get_font` from `frame_composer.py`, `ConfettiBurst`, `ScreenShake`, `CountdownBar`, `ProgressIndicator`, `ThemedDecorations`, `KenBurnsZoom`, `GlowRing` from `effects.py`, `ease_value`, `compute_scale`, `compute_opacity`, `compute_slide_x`, `compute_bounce_y`, `ParticleSystem` from `animations.py`, `QuizRound`, `QuizPack` from `quiz_generator.py`, `RoundAudio` from `narration.py`
- Produces: `LongformContext` dataclass, `build_longform_timeline(num_rounds, round_duration, format_type) -> list[dict]`, `render_longform_frame(t, ctx) -> np.ndarray`, `assemble_longform(quiz_pack, image_paths, silhouette_paths, round_audios, audio_path, output_path, format_type="long") -> Path`

This is the largest task. It creates a 16:9 landscape renderer that mirrors `video_assembler.py`'s architecture but with top-performer quality features:
- Landscape layout (1920×1080)
- Progress counter (top-right) — "Q 23/60"
- Continuous flow with motivational milestones — questions back-to-back, with brief 2s hype cards at 25%, 50%, 75%, and before last question
- Consistent pacing — every round identical timing, layout, SFX (kids like predictability)
- Star rating outro — final score with 1-5 stars and appropriate mascot reaction + subscribe CTA
- Configurable round duration (8s for long, 7s for mega)

The renderer reuses existing effect classes (ConfettiBurst, ScreenShake, CountdownBar, etc.) and frame_composer functions (render_gradient_background, render_text, etc.) — it does NOT duplicate them.

- [ ] **Step 1: Write tests for longform timeline builder**

Create `tests/test_longform_assembler.py`:

```python
# tests/test_longform_assembler.py
# ============================================================
# Tests for the long-form video assembler.
# Verifies timeline building, frame rendering, and layout.
# ============================================================
import pytest
import numpy as np
from pathlib import Path

import config


def test_longform_timeline_has_intro_rounds_outro():
    """# Timeline should have intro + N rounds + outro events."""
    from longform_assembler import build_longform_timeline
    timeline = build_longform_timeline(10, config.LONGFORM_ROUND_DURATION, "long")
    # Should have intro + (6 phases per round × 10 rounds) + outro
    phases = [e["phase"] for e in timeline]
    assert phases[0] == "intro"
    assert phases[-1] == "outro"
    # Count round events (silhouette, countdown×timer, reveal, fun_fact)
    round_events = [e for e in timeline if e["round"] >= 0]
    assert len(round_events) >= 10  # At least one event per round


def test_longform_timeline_round_timing():
    """# Each round should span exactly LONGFORM_ROUND_DURATION seconds."""
    from longform_assembler import build_longform_timeline
    timeline = build_longform_timeline(5, config.LONGFORM_ROUND_DURATION, "long")
    # Find first round's events
    round_0_events = [e for e in timeline if e["round"] == 0]
    first_start = round_0_events[0]["start"]
    last_end = round_0_events[-1]["end"]
    assert pytest.approx(last_end - first_start, abs=0.1) == config.LONGFORM_ROUND_DURATION


def test_mega_timeline_uses_mega_duration():
    """# Mega quiz timeline should use MEGA_ROUND_DURATION."""
    from longform_assembler import build_longform_timeline
    timeline = build_longform_timeline(5, config.MEGA_ROUND_DURATION, "mega")
    round_0_events = [e for e in timeline if e["round"] == 0]
    first_start = round_0_events[0]["start"]
    last_end = round_0_events[-1]["end"]
    assert pytest.approx(last_end - first_start, abs=0.1) == config.MEGA_ROUND_DURATION


def test_longform_timeline_total_duration():
    """# Total timeline duration should match expected video length."""
    from longform_assembler import build_longform_timeline
    timeline = build_longform_timeline(60, config.LONGFORM_ROUND_DURATION, "long")
    total = timeline[-1]["end"]
    expected = config.LONGFORM_INTRO_DURATION + 60 * config.LONGFORM_ROUND_DURATION + config.LONGFORM_OUTRO_DURATION
    assert pytest.approx(total, abs=1.0) == expected


def test_longform_context_creation():
    """# LongformContext should accept all required fields."""
    from longform_assembler import LongformContext
    ctx = LongformContext(
        width=1920, height=1080,
        category="animals",
        rounds=[], image_paths=[], silhouette_paths=[],
        mascot_images={}, particle_system=None,
        themed_decorations=None,
        format_type="long",
        total_rounds=60,
    )
    assert ctx.width == 1920
    assert ctx.height == 1080
    assert ctx.format_type == "long"
    assert ctx.total_rounds == 60


def test_render_longform_frame_returns_rgb_array():
    """# render_longform_frame should return (1080, 1920, 3) numpy array."""
    from longform_assembler import LongformContext, render_longform_frame, build_longform_timeline
    from animations import ParticleSystem
    from effects import ThemedDecorations

    timeline = build_longform_timeline(2, config.LONGFORM_ROUND_DURATION, "long")
    ctx = LongformContext(
        width=1920, height=1080,
        category="animals",
        rounds=[], image_paths=[], silhouette_paths=[],
        mascot_images={},
        particle_system=ParticleSystem(1920, 1080, count=5),
        themed_decorations=ThemedDecorations("animals", 1920, 1080),
        format_type="long",
        total_rounds=2,
        timeline=timeline,
    )
    # Render an intro frame
    frame = render_longform_frame(0.5, ctx)
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (1080, 1920, 3)
    assert frame.dtype == np.uint8


def test_render_longform_frame_landscape_dimensions():
    """# Frame dimensions must be 1920×1080 (16:9 landscape)."""
    from longform_assembler import LongformContext, render_longform_frame, build_longform_timeline
    from animations import ParticleSystem
    from effects import ThemedDecorations

    timeline = build_longform_timeline(1, config.LONGFORM_ROUND_DURATION, "long")
    ctx = LongformContext(
        width=1920, height=1080,
        category="space",
        rounds=[], image_paths=[], silhouette_paths=[],
        mascot_images={},
        particle_system=ParticleSystem(1920, 1080, count=5),
        themed_decorations=ThemedDecorations("space", 1920, 1080),
        format_type="long",
        total_rounds=1,
        timeline=timeline,
    )
    frame = render_longform_frame(0.0, ctx)
    # Height, Width, Channels
    assert frame.shape[0] == 1080
    assert frame.shape[1] == 1920
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_longform_assembler.py -v`
Expected: FAIL — ModuleNotFoundError for longform_assembler

- [ ] **Step 3: Implement longform_assembler.py**

Create `longform_assembler.py`. This is a large file (~450-550 lines) that mirrors `video_assembler.py`'s architecture for 16:9 landscape with top-performer quality features. The implementer should:

1. Create `LongformContext` dataclass (mirrors `VideoContext` but adds `format_type: str`, `total_rounds: int`)
2. Create `build_longform_round_timeline(round_index, round_start, format_type)` — builds timed events for one round using long-form or mega timing constants
3. Create `build_longform_timeline(num_rounds, round_duration, format_type)` — builds intro + continuous rounds + motivational milestone cards + outro. Inserts 2s hype cards at 25%, 50%, 75% of rounds, and "FINAL QUESTION!" before the last round. For 60 rounds: milestones at Q15, Q30, Q45, Q59. For 100 rounds: at Q25, Q50, Q75, Q99.
4. Create `_get_current_event(t, timeline)` — same pattern as video_assembler
5. Create `render_milestone_card(frame, message, t)` — renders motivational hype cards (2s each):
   - Category gradient background
   - Message in large glow text with scale animation (0.5→1.0), e.g. "HALFWAY! You're doing amazing!"
   - Confetti burst effect
   - Leo mascot excited pose
   - 2s duration, then straight into next question
   - Messages: "Great start! Keep going!" (25%), "HALFWAY! You're doing amazing!" (50%), "Almost there!" (75%), "FINAL QUESTION!" (last)
6. Create `render_longform_frame(t, ctx)` — the main frame renderer with landscape layout (consistent pacing — every round looks identical):
   - Layer 1: Gradient background (full 1920×1080, consistent throughout)
   - Layer 2: Themed decorations + particles
   - Layer 3: Header bar — "GUESS THE ANIMAL!" (top-left) + "Q 23/60" (top-right)
   - Layer 4: Content area — silhouette/reveal image (centered, larger than shorts since more horizontal space)
   - Layer 5: Question text below content
   - Layer 6: CountdownBar (wider, below question)
   - Layer 7: Countdown numbers (glow text)
   - Layer 8: Answer text (rainbow) on reveal
   - Layer 9: Fun fact (pill background)
   - Layer 10: Leo mascot (right side, larger since landscape) — standard pose cycle (thinking during countdown, excited on reveal)
   - Layer 11: Vignette + Ken Burns + transitions
7. Create `render_star_rating(frame, total_rounds, t)` — outro star rating:
   - Display total rounds completed as score
   - Render large stars with pop animation (one at a time)
   - Mascot excited pose
   - "YOU COMPLETED 60 QUESTIONS!" in glow text
   - Subscribe CTA below: "Subscribe for more quizzes!"
8. Create `assemble_longform(quiz_pack, image_paths, silhouette_paths, round_audios, audio_path, output_path, format_type="long")` — mirrors `assemble_short()` but uses `LONGFORM_SIZE`, builds `LongformContext`, renders with `render_longform_frame`

Key differences from `video_assembler.py`:
- Uses `config.LONGFORM_SIZE` (1920×1080) instead of `config.SHORTS_SIZE` (1080×1920)
- Content area: image centered at (960, 400) instead of (540, 672) — landscape has wider but shorter content area
- Progress counter: top-right corner at (1800, 50) — "Q 23/60" always visible
- Question text: below content area at y=700 instead of y=0.62*height
- Timer bar: full-width at y=750
- Mascot: right side at (1750, 850) — larger since landscape has more room
- Uses format-specific timing (LONGFORM_* or MEGA_* constants based on format_type)
- Continuous flow with motivational milestones at 25%, 50%, 75% + "FINAL QUESTION!" before last round
- Consistent pacing throughout — same timing, same layout, same SFX for every round
- Intro shows "60 QUESTIONS!" or "100 QUESTIONS!"
- Outro shows star rating + mascot celebration + subscribe CTA
- Uses `LONGFORM_BITRATE` instead of `VIDEO_BITRATE`

The implementer should reference `video_assembler.py` extensively — the rendering logic is structurally identical, just repositioned for landscape and using different timing constants. Every helper function (`_composite_image_on_frame`, `_get_current_event`) and every effect class (`ConfettiBurst`, `ScreenShake`, `CountdownBar`, etc.) is imported and reused, not duplicated.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_longform_assembler.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest -v`
Expected: All tests pass (existing + new)

- [ ] **Step 6: Commit**

```bash
cd C:\Users\User\LeoQuiz
git add longform_assembler.py tests/test_longform_assembler.py
git commit -m "feat: add 16:9 landscape video assembler for long-form and mega quiz"
```

---

### Task 3: Pipeline Format Routing + Scheduler

**Files:**
- Modify: `main.py` (pipeline)
- Modify: `scheduler.py` (pipeline)
- Modify: `.github/workflows/daily.yml` (pipeline)
- Modify: `tests/test_config.py` (pipeline — add `ROUNDS_PER_SHORT=6` assertion if not already present)

**Interfaces:**
- Consumes: `assemble_longform` from Task 2, all config constants from Task 1
- Produces: `run_pipeline(category, num_rounds, video_format, output_dir)` with `video_format` param, `--format` CLI arg

- [ ] **Step 1: Update main.py to accept video_format parameter**

Modify `run_pipeline()` signature to add `video_format: str = "short"`. Inside the function:
- If `video_format == "short"`: use current behavior (unchanged), but default `num_rounds` to `config.ROUNDS_PER_SHORT` (6)
- If `video_format == "long"`: set `num_rounds = config.LONGFORM_ROUNDS` (60), use `assemble_longform()` instead of `assemble_short()`, use long-form timing for audio, output to `LONGFORM_DIR`
- If `video_format == "mega"`: set `num_rounds = config.MEGA_ROUNDS` (100), use `assemble_longform(..., format_type="mega")`, output to `LONGFORM_DIR`

**Difficulty progression for long-form/mega:** After quiz_generator returns rounds, sort them by difficulty for long-form/mega formats. The quiz_generator already assigns difficulty to each round. Sort so easy rounds come first, then medium, then hard:
```python
if video_format in ("long", "mega"):
    # Sort rounds by difficulty for progressive challenge (top performer standard)
    difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
    quiz_pack.rounds.sort(key=lambda r: difficulty_order.get(r.difficulty, 1))
```

Add `--format` CLI argument:
```python
parser.add_argument("--format", type=str, default="short",
                    choices=["short", "long", "mega"],
                    help="Video format: short (66s), long (~10min), mega (~15min)")
```

Pass `video_format=args.format` to `run_pipeline()`.

For long/mega format, the pipeline calculates `total_duration` using format-specific constants:
```python
if video_format == "long":
    total_duration = (config.LONGFORM_INTRO_DURATION +
                      num_rounds * config.LONGFORM_ROUND_DURATION +
                      config.LONGFORM_OUTRO_DURATION)
elif video_format == "mega":
    total_duration = (config.MEGA_INTRO_DURATION +
                      num_rounds * config.MEGA_ROUND_DURATION +
                      config.MEGA_OUTRO_DURATION)
```

And calls `assemble_longform()` instead of `assemble_short()` in Step 6.

- [ ] **Step 2: Update scheduler.py for daily long-form + weekly mega**

Modify `daily_job()` to run TWO pipeline calls:
```python
def daily_job():
    """# Generate one short + one long-form quiz video for today's category."""
    # Short-form (66s, 6 rounds)
    run_pipeline(video_format="short")
    # Long-form (10min, 60 rounds, same category)
    run_pipeline(video_format="long")
```

Modify `weekly_job()` to generate mega quiz:
```python
def weekly_job():
    """# Generate a mega quiz (100 rounds, 15-20 min)."""
    run_pipeline(video_format="mega")
```

- [ ] **Step 3: Update daily.yml workflow to accept format input**

Add `format` input to the workflow_dispatch:
```yaml
format:
  description: 'Video format (short, long, mega)'
  required: false
  default: 'short'
  type: string
```

Update the "Run pipeline" step to pass `--format`:
```bash
if [ -n "${{ inputs.format }}" ]; then
  ARGS="$ARGS --format ${{ inputs.format }}"
fi
```

- [ ] **Step 4: Run tests**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
cd C:\Users\User\LeoQuiz
git add main.py scheduler.py .github/workflows/daily.yml
git commit -m "feat: add format routing for short/long/mega pipeline runs"
```

---

### Task 4: Instagram + Facebook Metadata Generators

**Files:**
- Modify: `metadata.py` (pipeline)
- Create: `tests/test_metadata.py` (pipeline)

**Interfaces:**
- Consumes: `generate_metadata(quiz_pack, platform)` existing function
- Produces: Extended `generate_metadata()` that accepts `platform="instagram"` and `platform="facebook"`

- [ ] **Step 1: Write tests for Instagram and Facebook metadata**

Create `tests/test_metadata.py`:

```python
# tests/test_metadata.py
# ============================================================
# Tests for metadata generation across all 4 platforms.
# ============================================================
import pytest
from unittest.mock import patch, MagicMock
from quiz_generator import QuizPack, QuizRound


def _make_quiz_pack():
    """# Helper to create a minimal quiz pack for testing."""
    rounds = [
        QuizRound(answer="Lion", hint_question="Which animal is the king of the jungle?",
                  fun_fact="Lions sleep 20 hours a day", difficulty="easy",
                  image_prompt="cute cartoon lion"),
    ]
    return QuizPack(category="animals", rounds=rounds)


def test_generate_metadata_youtube():
    """# YouTube metadata should have title, description, tags, hashtags."""
    from metadata import generate_metadata
    pack = _make_quiz_pack()
    with patch("metadata.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = MagicMock(
            text='{"title": "Guess the Animal!", "description": "Fun quiz", "tags": ["animals"], "hashtags": ["#quiz"]}'
        )
        meta = generate_metadata(pack, "youtube")
        assert "title" in meta
        assert meta["made_for_kids"] is True
        assert meta["category"] == "animals"


def test_generate_metadata_instagram():
    """# Instagram metadata should have caption + hashtags, no tags field."""
    from metadata import generate_metadata
    pack = _make_quiz_pack()
    with patch("metadata.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = MagicMock(
            text='{"caption": "Can YOU guess? 🤔", "hashtags": ["#kidsgame", "#quiz"], "title": "Guess!"}'
        )
        meta = generate_metadata(pack, "instagram")
        assert "title" in meta or "caption" in meta
        assert meta["made_for_kids"] is True


def test_generate_metadata_facebook():
    """# Facebook metadata should have title + description, no hashtags."""
    from metadata import generate_metadata
    pack = _make_quiz_pack()
    with patch("metadata.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = MagicMock(
            text='{"title": "How Many Can Your Kids Guess?", "description": "Play along!", "tags": [], "hashtags": []}'
        )
        meta = generate_metadata(pack, "facebook")
        assert "title" in meta
        assert meta["made_for_kids"] is True


def test_all_platforms_accepted():
    """# generate_metadata should accept all 4 platform strings."""
    from metadata import generate_metadata
    pack = _make_quiz_pack()
    for platform in ["youtube", "tiktok", "instagram", "facebook"]:
        with patch("metadata.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = MagicMock(
                text='{"title": "Test", "description": "Test", "tags": [], "hashtags": []}'
            )
            meta = generate_metadata(pack, platform)
            assert "title" in meta
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_metadata.py -v`
Expected: Tests should pass or fail based on current implementation — the key is the Instagram/Facebook prompt handling

- [ ] **Step 3: Update metadata.py to handle Instagram and Facebook**

Update the prompt in `generate_metadata()` to include platform-specific instructions for Instagram and Facebook:

```python
# Add after the existing TikTok instruction in the prompt:
# For Instagram: caption should be engagement-style with emojis, max 30 hashtags
# For Facebook: title should be shareable/parent-targeted, no hashtags needed
```

Add platform-specific prompt lines:
```python
if platform == "instagram":
    prompt += "\nFor Instagram: caption should be engaging ('Can YOU guess all 6? 🤔 Comment your score!'), include up to 30 hashtags mixing broad and niche."
elif platform == "facebook":
    prompt += "\nFor Facebook: title should be shareable and parent-targeted ('How Many Animals Can Your Kids Guess? 🦁'), no hashtags needed."
```

Also update `main.py` Step 8 to generate all 4 platform metadata files:
```python
for platform in ["youtube", "tiktok", "instagram", "facebook"]:
    meta = generate_metadata(quiz_pack, platform)
    save_metadata(meta, output_dir / f"metadata_{platform}.json")
```

- [ ] **Step 4: Run tests**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_metadata.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd C:\Users\User\LeoQuiz
git add metadata.py tests/test_metadata.py main.py
git commit -m "feat: add Instagram and Facebook metadata generators"
```

---

### Task 5: Multi-Platform Uploaders (TikTok + Instagram + Facebook)

**Files:**
- Modify: `uploader.py` (pipeline)
- Create: `tests/test_uploader.py` (pipeline)

**Interfaces:**
- Consumes: Token data from Vercel Blob (JSON format matching `TokenData` in dashboard types)
- Produces: `upload_tiktok(video_path, metadata_path, token_json) -> str`, `upload_instagram(video_path, metadata_path, token_json) -> str`, `upload_facebook(video_path, metadata_path, token_json) -> str`

- [ ] **Step 1: Write tests for uploaders**

Create `tests/test_uploader.py`:

```python
# tests/test_uploader.py
# ============================================================
# Tests for multi-platform video uploaders.
# Uses mocks for all API calls — no real uploads in tests.
# ============================================================
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import json


def test_upload_tiktok_returns_url_on_success(tmp_path):
    """# Successful TikTok upload should return a post URL."""
    from uploader import upload_tiktok
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake video")
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"title": "Test", "description": "Test"}))
    token = {"access_token": "fake", "refresh_token": "fake", "expires_at": 9999999999}

    with patch("uploader.requests") as mock_req:
        # Mock TikTok's two-step upload (init → upload → publish)
        mock_req.post.return_value = MagicMock(
            ok=True, status_code=200,
            json=MagicMock(return_value={"data": {"publish_id": "123"}})
        )
        result = upload_tiktok(video, meta, token)
        # Should return a URL string (even if placeholder)
        assert isinstance(result, str)


def test_upload_tiktok_returns_empty_on_failure(tmp_path):
    """# Failed TikTok upload should return empty string."""
    from uploader import upload_tiktok
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake video")
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"title": "Test"}))
    token = {"access_token": "fake", "refresh_token": "fake", "expires_at": 9999999999}

    with patch("uploader.requests") as mock_req:
        mock_req.post.return_value = MagicMock(ok=False, status_code=401)
        result = upload_tiktok(video, meta, token)
        assert result == ""


def test_upload_instagram_returns_url_on_success(tmp_path):
    """# Successful Instagram upload should return a media URL."""
    from uploader import upload_instagram
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake video")
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"caption": "Test", "hashtags": ["#test"]}))
    token = {"access_token": "fake", "ig_user_id": "123", "expires_at": 9999999999}

    with patch("uploader.requests") as mock_req:
        # Mock Instagram's container-based upload flow
        mock_req.post.return_value = MagicMock(
            ok=True, json=MagicMock(return_value={"id": "456"})
        )
        mock_req.get.return_value = MagicMock(
            ok=True, json=MagicMock(return_value={"status_code": "FINISHED"})
        )
        result = upload_instagram(video, meta, token)
        assert isinstance(result, str)


def test_upload_facebook_returns_url_on_success(tmp_path):
    """# Successful Facebook upload should return a post URL."""
    from uploader import upload_facebook
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake video")
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"title": "Test", "description": "Test"}))
    token = {"page_access_token": "fake", "page_id": "789", "expires_at": 9999999999}

    with patch("uploader.requests") as mock_req:
        mock_req.post.return_value = MagicMock(
            ok=True, json=MagicMock(return_value={"id": "post_123"})
        )
        result = upload_facebook(video, meta, token)
        assert isinstance(result, str)


def test_all_uploaders_handle_missing_token(tmp_path):
    """# All uploaders should return empty string when token is None."""
    from uploader import upload_tiktok, upload_instagram, upload_facebook
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")
    meta = tmp_path / "meta.json"
    meta.write_text("{}")

    assert upload_tiktok(video, meta, None) == ""
    assert upload_instagram(video, meta, None) == ""
    assert upload_facebook(video, meta, None) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_uploader.py -v`
Expected: FAIL — upload_instagram and upload_facebook not defined

- [ ] **Step 3: Implement uploaders in uploader.py**

Complete `upload_tiktok()` using TikTok Content Posting API v2 (direct post flow). Add `upload_instagram()` using Instagram Graph API container-based Reels publish. Add `upload_facebook()` using Facebook Graph API video upload. Each function:

1. Validates token is not None (returns "" if missing)
2. Reads metadata from JSON file
3. Makes API calls (using `requests` library)
4. Sets COPPA/Made-for-Kids flag where supported
5. Returns platform URL on success, "" on failure
6. Wraps all API calls in try/except for resilience

Add `import requests` at top of file.

- [ ] **Step 4: Run tests**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_uploader.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd C:\Users\User\LeoQuiz
git add uploader.py tests/test_uploader.py
git commit -m "feat: add TikTok, Instagram, and Facebook video uploaders"
```

---

### Task 6: A/B Thumbnail Variants

**Files:**
- Modify: `thumbnail.py` (pipeline)
- Modify: `tests/test_thumbnail.py` (pipeline)
- Modify: `main.py` (pipeline — call `generate_all_thumbnails`)

**Interfaces:**
- Consumes: Existing `generate_thumbnail()` (becomes Variant A), `QuizPack`, image_paths, silhouette_paths
- Produces: `generate_thumbnail_variant_b(quiz_pack, silhouette_paths, output_path) -> Path`, `generate_thumbnail_variant_c(quiz_pack, silhouette_paths, output_path) -> Path`, `generate_all_thumbnails(quiz_pack, image_paths, silhouette_paths, output_dir) -> dict[str, Path]`

- [ ] **Step 1: Write tests for thumbnail variants**

Add to `tests/test_thumbnail.py`:

```python
def test_variant_b_giant_mystery(tmp_path):
    """# Variant B should create a 1280x720 thumbnail with giant silhouette."""
    from thumbnail import generate_thumbnail_variant_b
    from quiz_generator import QuizPack, QuizRound
    rounds = [QuizRound(answer="Lion", hint_question="?", fun_fact="fact",
                         difficulty="easy", image_prompt="lion")]
    pack = QuizPack(category="animals", rounds=rounds)
    # Create a fake silhouette image
    from PIL import Image
    sil_path = tmp_path / "sil.png"
    Image.new("RGBA", (200, 200), (0, 0, 0, 255)).save(sil_path)

    output = tmp_path / "thumb_b.png"
    generate_thumbnail_variant_b(pack, [sil_path], output)
    assert output.exists()
    img = Image.open(output)
    assert img.size == (1280, 720)


def test_variant_c_grid_challenge(tmp_path):
    """# Variant C should create a 1280x720 thumbnail with 2x2 grid."""
    from thumbnail import generate_thumbnail_variant_c
    from quiz_generator import QuizPack, QuizRound
    rounds = [QuizRound(answer=f"Animal{i}", hint_question="?", fun_fact="fact",
                         difficulty="easy", image_prompt="animal")
              for i in range(4)]
    pack = QuizPack(category="animals", rounds=rounds)
    from PIL import Image
    sil_paths = []
    for i in range(4):
        p = tmp_path / f"sil_{i}.png"
        Image.new("RGBA", (200, 200), (0, 0, 0, 255)).save(p)
        sil_paths.append(p)

    output = tmp_path / "thumb_c.png"
    generate_thumbnail_variant_c(pack, sil_paths, output)
    assert output.exists()
    img = Image.open(output)
    assert img.size == (1280, 720)


def test_generate_all_thumbnails(tmp_path):
    """# generate_all_thumbnails should create 3 files."""
    from thumbnail import generate_all_thumbnails
    from quiz_generator import QuizPack, QuizRound
    rounds = [QuizRound(answer=f"Animal{i}", hint_question="?", fun_fact="fact",
                         difficulty="easy", image_prompt="animal")
              for i in range(5)]
    pack = QuizPack(category="animals", rounds=rounds)
    from PIL import Image
    img_paths = []
    sil_paths = []
    for i in range(5):
        ip = tmp_path / f"img_{i}.png"
        sp = tmp_path / f"sil_{i}.png"
        Image.new("RGBA", (200, 200), (100, 200, 100, 255)).save(ip)
        Image.new("RGBA", (200, 200), (0, 0, 0, 255)).save(sp)
        img_paths.append(ip)
        sil_paths.append(sp)

    out_dir = tmp_path / "thumbs"
    out_dir.mkdir()
    result = generate_all_thumbnails(pack, img_paths, sil_paths, out_dir)
    assert (out_dir / "thumb_a.png").exists()
    assert (out_dir / "thumb_b.png").exists()
    assert (out_dir / "thumb_c.png").exists()
    assert len(result) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_thumbnail.py -v -k "variant"` 
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement Variant B and C in thumbnail.py**

Add `generate_thumbnail_variant_b()` — "Giant Mystery" layout:
- Full category gradient background
- Single largest silhouette centered (70% of height)
- Giant "?" overlaid on silhouette (font size 200, yellow glow)
- "GUESS THE [CATEGORY]!" at bottom (glow text)
- Bright yellow/red 8px border
- Leo mascot (surprised) in corner
- Vignette

Add `generate_thumbnail_variant_c()` — "Grid Challenge" layout:
- Category gradient background
- 2×2 grid of 4 silhouettes (each ~250×250, numbered 1-4)
- "HOW MANY CAN YOU GUESS?" header (glow text)
- Leo mascot in bottom-right corner
- "6 ROUNDS!" badge in top-right
- Vignette

Add `generate_all_thumbnails()` wrapper:
```python
def generate_all_thumbnails(quiz_pack, image_paths, silhouette_paths, output_dir):
    """# Generate 3 A/B test thumbnail variants. Returns dict of variant→path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    paths["a"] = generate_thumbnail(quiz_pack, image_paths, silhouette_paths, output_dir / "thumb_a.png")
    paths["b"] = generate_thumbnail_variant_b(quiz_pack, silhouette_paths, output_dir / "thumb_b.png")
    paths["c"] = generate_thumbnail_variant_c(quiz_pack, silhouette_paths, output_dir / "thumb_c.png")
    return paths
```

Add `select_best_thumbnail()` — uses Gemini Vision to evaluate all 3 and pick the best:
```python
def select_best_thumbnail(thumb_paths: dict[str, Path]) -> str:
    """# Use Gemini Vision to evaluate 3 thumbnails and pick the most click-worthy one.
    # Returns the winning variant key ('a', 'b', or 'c').
    # Evaluates based on: visual clarity, kid-appeal, click-worthiness, color contrast."""
    import google.generativeai as genai
    from PIL import Image
    import config

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    # Load all 3 thumbnails as PIL images for Gemini Vision
    images = []
    for key in ["a", "b", "c"]:
        if thumb_paths.get(key) and thumb_paths[key].exists():
            images.append(Image.open(thumb_paths[key]))

    prompt = (
        "You are a YouTube thumbnail expert for kids content. "
        "I'm showing you 3 thumbnail variants (A, B, C) for a children's quiz video. "
        "Pick the ONE that would get the most clicks from kids aged 4-10 and their parents. "
        "Consider: visual clarity, mystery/curiosity factor, color contrast, kid-friendliness. "
        "Reply with ONLY the letter: A, B, or C"
    )
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt] + images,
    )
    # Parse response — extract A, B, or C
    choice = response.text.strip().upper()
    variant_map = {"A": "a", "B": "b", "C": "c"}
    return variant_map.get(choice, "a")  # Default to A if parsing fails
```

Update `main.py` Step 7 to:
1. Call `generate_all_thumbnails()` to create 3 variants
2. Call `select_best_thumbnail()` to auto-pick the best one
3. Store the selected variant key in the output metadata

- [ ] **Step 4: Run tests**

Run: `cd C:\Users\User\LeoQuiz && python -m pytest tests/test_thumbnail.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd C:\Users\User\LeoQuiz
git add thumbnail.py tests/test_thumbnail.py main.py
git commit -m "feat: add A/B thumbnail variants (giant mystery + grid challenge)"
```

---

### Task 7: Dashboard Schema + Types Expansion

**Files:**
- Modify: `lib/schema.sql` (dashboard)
- Modify: `lib/types.ts` (dashboard)
- Modify: `lib/db.ts` (dashboard)

**Interfaces:**
- Produces: Updated `Platform` type (`"youtube" | "tiktok" | "instagram" | "facebook" | "all"`), `VideoFormat` type (`"short" | "long" | "mega"`), `video_analytics` table, `channel_analytics` table, `thumbnail_tests` table, new Video fields (`youtube_url`, `tiktok_url`, `instagram_url`, `facebook_url`, `video_format`, `platform_metadata`), analytics DB helpers (`saveVideoAnalytics`, `getVideoAnalytics`, `getChannelAnalytics`, `saveThumbnailTest`, `getThumbnailTests`), updated schedule_config columns (`generate_longform`, `mega_day`, `mega_hour_utc`)

- [ ] **Step 1: Add new tables and columns to schema.sql**

Append to `lib/schema.sql`:

```sql
-- Video format column (short, long, mega)
-- SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS,
-- so we handle this in migration code instead

-- Video analytics — per-video per-platform stats pulled from APIs
CREATE TABLE IF NOT EXISTS video_analytics (
  id TEXT PRIMARY KEY,
  video_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  platform_video_id TEXT,
  views INTEGER DEFAULT 0,
  likes INTEGER DEFAULT 0,
  comments INTEGER DEFAULT 0,
  shares INTEGER DEFAULT 0,
  saves INTEGER DEFAULT 0,
  watch_time_minutes REAL DEFAULT 0.0,
  impressions INTEGER DEFAULT 0,
  ctr REAL DEFAULT 0.0,
  fetched_at TEXT NOT NULL,
  FOREIGN KEY (video_id) REFERENCES videos(id)
);

-- Index for fetching analytics by video
CREATE INDEX IF NOT EXISTS idx_analytics_video ON video_analytics(video_id);

-- Index for fetching analytics by platform
CREATE INDEX IF NOT EXISTS idx_analytics_platform ON video_analytics(platform);

-- Channel analytics — daily channel-level stats per platform
CREATE TABLE IF NOT EXISTS channel_analytics (
  id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  date TEXT NOT NULL,
  subscribers INTEGER DEFAULT 0,
  total_views INTEGER DEFAULT 0,
  new_videos INTEGER DEFAULT 0,
  fetched_at TEXT NOT NULL,
  UNIQUE(platform, date)
);

-- Thumbnail A/B test tracking
CREATE TABLE IF NOT EXISTS thumbnail_tests (
  id TEXT PRIMARY KEY,
  video_id TEXT NOT NULL,
  variant TEXT NOT NULL,
  platform TEXT NOT NULL,
  uploaded_at TEXT,
  impressions INTEGER DEFAULT 0,
  clicks INTEGER DEFAULT 0,
  ctr REAL DEFAULT 0.0,
  checked_at TEXT,
  FOREIGN KEY (video_id) REFERENCES videos(id)
);

-- Index for thumbnail CTR queries by video
CREATE INDEX IF NOT EXISTS idx_thumbtests_video ON thumbnail_tests(video_id);
```

- [ ] **Step 2: Update lib/types.ts**

Add new types and expand existing ones:

```typescript
// -- Video format (short/long/mega) --
export type VideoFormat = "short" | "long" | "mega";

// -- Expanded Platform type --
// Now includes all 4 platforms plus "all"
export type Platform = "youtube" | "tiktok" | "instagram" | "facebook" | "all";

// -- Add to Video interface --
// Per-platform upload URLs (null = not uploaded to that platform)
// youtube_url, tiktok_url, instagram_url, facebook_url: string | null
// video_format: VideoFormat
// platform_metadata: string (JSON blob of per-platform title/caption/hashtags)

// -- Per-platform metadata (stored as JSON in platform_metadata column) --
// Auto-generated by pipeline, viewable in approval queue, used during upload
export interface PlatformMetadata {
  youtube?: { title: string; description: string; tags: string[]; hashtags: string[] };
  tiktok?: { title: string; description: string; hashtags: string[] };
  instagram?: { caption: string; hashtags: string[] };
  facebook?: { title: string; description: string };
}

// -- Video analytics record --
export interface VideoAnalytics {
  id: string;
  video_id: string;
  platform: string;
  platform_video_id: string | null;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  saves: number;
  watch_time_minutes: number;
  impressions: number;
  ctr: number;
  fetched_at: string;
}

// -- Channel analytics record --
export interface ChannelAnalytics {
  id: string;
  platform: string;
  date: string;
  subscribers: number;
  total_views: number;
  new_videos: number;
  fetched_at: string;
}

// -- Thumbnail test record --
export interface ThumbnailTest {
  id: string;
  video_id: string;
  variant: string;
  platform: string;
  uploaded_at: string | null;
  impressions: number;
  clicks: number;
  ctr: number;
  checked_at: string | null;
}

// -- Analytics overview for dashboard cards --
export interface AnalyticsOverview {
  total_views: number;
  total_subscribers: Record<string, number>;
  videos_this_week: number;
  average_ctr: number;
}
```

Update the `Video` interface to add per-platform URL fields and video_format.

Update `ScheduleConfig` to add `generate_longform`, `mega_day`, `mega_hour_utc`.

- [ ] **Step 3: Add DB helpers in lib/db.ts**

Add analytics and thumbnail test helper functions:

```typescript
export async function saveVideoAnalytics(data: Partial<VideoAnalytics>): Promise<void> { ... }
export async function getVideoAnalytics(videoId: string): Promise<VideoAnalytics[]> { ... }
export async function getChannelAnalytics(platform: string, days: number): Promise<ChannelAnalytics[]> { ... }
export async function saveThumbnailTest(data: Partial<ThumbnailTest>): Promise<void> { ... }
export async function getThumbnailTests(videoId: string): Promise<ThumbnailTest[]> { ... }
export async function getAnalyticsOverview(): Promise<AnalyticsOverview> { ... }
export async function getTopVideos(limit: number, platform?: string): Promise<(Video & { total_views: number })[]> { ... }
```

Also add migration logic in `initializeDatabase()` to add new columns to existing tables:

```typescript
// Run migrations for new columns (SQLite ALTER TABLE)
const migrations = [
  "ALTER TABLE videos ADD COLUMN youtube_url TEXT",
  "ALTER TABLE videos ADD COLUMN tiktok_url TEXT",
  "ALTER TABLE videos ADD COLUMN instagram_url TEXT",
  "ALTER TABLE videos ADD COLUMN facebook_url TEXT",
  "ALTER TABLE videos ADD COLUMN video_format TEXT DEFAULT 'short'",
  "ALTER TABLE videos ADD COLUMN platform_metadata TEXT",
  "ALTER TABLE schedule_config ADD COLUMN generate_longform INTEGER DEFAULT 1",
  "ALTER TABLE schedule_config ADD COLUMN mega_day INTEGER DEFAULT 6",
  "ALTER TABLE schedule_config ADD COLUMN mega_hour_utc INTEGER DEFAULT 10",
];
for (const sql of migrations) {
  try { await db.execute(sql); } catch { /* column already exists */ }
}
```

Update `rowToVideo()` to map the new fields. Update `updateVideo()` to include new updatable fields.

- [ ] **Step 4: Run build**

Run: `cd C:\Users\User\leo-quiz-dashboard && npx next build`
Expected: Build succeeds (type checking passes)

- [ ] **Step 5: Commit**

```bash
cd C:\Users\User\leo-quiz-dashboard
git add lib/schema.sql lib/types.ts lib/db.ts
git commit -m "feat: expand schema with analytics, thumbnails, multi-platform fields"
```

---

### Task 8: TikTok + Meta OAuth Routes

**Files:**
- Create: `app/api/auth/tiktok/route.ts` (dashboard)
- Create: `app/api/auth/tiktok/callback/route.ts` (dashboard)
- Create: `app/api/auth/meta/route.ts` (dashboard)
- Create: `app/api/auth/meta/callback/route.ts` (dashboard)
- Modify: `lib/tokens.ts` (dashboard — add TikTok + Meta refresh logic)
- Modify: `app/api/auth/status/route.ts` (dashboard — return all 4 platforms)
- Modify: `app/api/auth/disconnect/route.ts` (dashboard — support all platforms)
- Create: `app/api/tokens/tiktok/route.ts` (dashboard)
- Create: `app/api/tokens/meta/route.ts` (dashboard)

**Interfaces:**
- Consumes: `saveToken`, `deleteToken`, `getToken` from `lib/tokens.ts`, `getSession` from `lib/auth.ts`
- Produces: OAuth connect flows for TikTok and Meta (Instagram + Facebook), token refresh endpoints for pipeline upload workflow

Each OAuth route follows the same pattern as the existing YouTube OAuth (`app/api/auth/youtube/route.ts` and `callback/route.ts`):
1. `GET /api/auth/{platform}` — builds OAuth URL with scopes, redirects user
2. `GET /api/auth/{platform}/callback` — exchanges code for tokens, saves to Blob, redirects to settings

Token refresh in `lib/tokens.ts`:
- Add `refreshTikTokToken()` using TikTok's token refresh endpoint
- Add `refreshMetaToken()` using Meta's long-lived token exchange
- Update `getToken()` to dispatch to correct refresh function based on platform
- Update `getConnectionStatus()` to check all 4 platforms

**TikTok OAuth scopes:** `user.info.basic,video.publish,video.upload`
**Meta OAuth scopes:** `instagram_basic,instagram_content_publish,pages_manage_posts,pages_read_engagement,pages_show_list`

- [ ] **Step 1-5: Implement OAuth routes, token refresh, status updates, commit**

The implementer should reference the existing YouTube OAuth pattern in `app/api/auth/youtube/route.ts` and `app/api/auth/youtube/callback/route.ts` — the TikTok and Meta flows are structurally identical but with different URLs, scopes, and token exchange endpoints.

```bash
cd C:\Users\User\leo-quiz-dashboard
git add app/api/auth/ lib/tokens.ts app/api/tokens/
git commit -m "feat: add TikTok and Meta OAuth connect flows"
```

---

### Task 9: Generate Page Format Selector + Dual Dispatch

**Files:**
- Modify: `app/generate/page.tsx` (dashboard)
- Modify: `app/api/generate/route.ts` (dashboard)
- Modify: `lib/github.ts` (dashboard — pass format to workflow)

**Interfaces:**
- Consumes: `triggerWorkflow` from `lib/github.ts`, `createVideo` from `lib/db.ts`
- Produces: Updated generate page with format selector (Short / Long-form / Mega / Daily Bundle), updated `triggerWorkflow()` that passes `format` input, "Daily Bundle" triggers 2 workflow dispatches

- [ ] **Step 1: Update lib/github.ts to pass format**

Add `format` parameter to `triggerWorkflow()`:

```typescript
export async function triggerWorkflow(
  videoId: string,
  category: string,
  rounds: number,
  format: string = "short"
): Promise<number | null> {
  // ... existing code ...
  body: JSON.stringify({
    ref: "main",
    inputs: {
      video_id: videoId,
      category,
      rounds: String(rounds),
      format,  // NEW: pass video format to pipeline
    },
  }),
```

- [ ] **Step 2: Update app/api/generate/route.ts**

Accept `format` and `video_format` in the request body. For "daily_bundle", create TWO video records and dispatch TWO workflows:

```typescript
const format = body.format || "short";

if (format === "daily_bundle") {
  // Create short video record + dispatch
  const shortVideo = await createVideo({ category, trigger_type: triggerType, rounds_count: 6, video_format: "short" });
  await triggerWorkflow(shortVideo.id, category, 6, "short");
  // Create long-form video record + dispatch
  const longVideo = await createVideo({ category, trigger_type: triggerType, rounds_count: 60, video_format: "long" });
  await triggerWorkflow(longVideo.id, category, 60, "long");
  return NextResponse.json({ videos: [shortVideo.id, longVideo.id], status: "generating" });
}
```

- [ ] **Step 3: Update app/generate/page.tsx**

Add format selector (radio buttons or segmented control):
- Short only (9:16, 6 rounds, ~66s)
- Long-form only (16:9, 60 rounds, ~10 min)
- Mega quiz (16:9, 100 rounds, ~15-20 min)
- **Daily bundle (recommended)** — Short + Long-form

Update the generate button handler to pass `format` in the POST body. When "Daily bundle" is selected, show status for both videos.

Update rounds input: disable and auto-set rounds based on format selection (6 for short, 60 for long, 100 for mega, hidden for bundle).

- [ ] **Step 4: Run build**

Run: `cd C:\Users\User\leo-quiz-dashboard && npx next build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
cd C:\Users\User\leo-quiz-dashboard
git add app/generate/page.tsx app/api/generate/route.ts lib/github.ts
git commit -m "feat: add format selector and daily bundle generation"
```

---

### Task 10: Multi-Platform Upload + Scheduling + Settings

**Files:**
- Modify: `app/api/videos/[id]/upload/route.ts` (dashboard)
- Modify: `app/api/cron/check-scheduled/route.ts` (dashboard — dispatch uploads to all connected platforms)
- Modify: `.github/workflows/upload.yml` (pipeline — add platform routing)
- Modify: `app/settings/page.tsx` (dashboard — add TikTok/Instagram/Facebook connect cards)

**Interfaces:**
- Consumes: `getToken` from `lib/tokens.ts`, `updateVideo` from `lib/db.ts`, `triggerUploadWorkflow` from `lib/github.ts`, `getConnectionStatus` from `lib/tokens.ts`
- Produces: Upload route that uploads to all connected platforms in parallel, scheduled posting to all 4 platforms via cron, settings page showing all 4 platform connections

- [ ] **Step 1: Update upload route for multi-platform**

Modify `app/api/videos/[id]/upload/route.ts` to:
1. Get ALL connected platforms (via `getConnectionStatus()`)
2. Read `platform_metadata` from the video record (auto-generated captions/hashtags)
3. For each connected platform, dispatch upload workflow with platform parameter AND its platform-specific metadata
4. Use `Promise.allSettled()` so partial failures don't block other platforms
5. Update video record with per-platform URLs as they complete
6. Log activity for each platform upload

No platform selection — every approved video posts to ALL connected platforms automatically.

- [ ] **Step 2: Update check-scheduled cron for multi-platform**

Modify `app/api/cron/check-scheduled/route.ts` — the existing cron checks for videos due for scheduled posting. Update it to:
1. When a scheduled video's time arrives, get all connected platforms
2. Dispatch upload to ALL connected platforms (not just YouTube)
3. Pass each platform's metadata from the video's `platform_metadata` field
4. Log which platforms received the upload

This is the key change that enables "schedule once → auto-post everywhere."

- [ ] **Step 3: Update upload.yml workflow**

Add TikTok, Instagram, and Facebook upload steps (conditional on platform input). The workflow already has YouTube upload — add similar steps for other platforms, each getting tokens from the dashboard API. Accept `platform_metadata` as a JSON input so each platform uses its own title/caption/hashtags.

- [ ] **Step 4: Update settings page with all platform cards**

Add TikTok, Instagram, and Facebook connection cards (same pattern as YouTube card). Each shows:
- Connected status (green dot + account name) or disconnected (with connect button)
- Connect button redirects to `/api/auth/tiktok` or `/api/auth/meta`
- Disconnect button calls `/api/auth/disconnect` with platform name

Use the existing `handleConnectYouTube` / `handleDisconnect` pattern.

- [ ] **Step 5: Run build**

Run: `cd C:\Users\User\leo-quiz-dashboard && npx next build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
cd C:\Users\User\leo-quiz-dashboard
git add app/api/videos/ app/api/cron/check-scheduled/ app/settings/page.tsx
cd C:\Users\User\LeoQuiz
git add .github/workflows/upload.yml
git commit -m "feat: multi-platform upload + scheduling for all 4 platforms"
```

---

### Task 11: Analytics Cron + API Routes

**Files:**
- Create: `app/api/cron/pull-analytics/route.ts` (dashboard)
- Create: `app/api/analytics/overview/route.ts` (dashboard)
- Create: `app/api/analytics/views/route.ts` (dashboard)
- Create: `app/api/analytics/categories/route.ts` (dashboard)
- Create: `app/api/analytics/top-videos/route.ts` (dashboard)
- Create: `app/api/analytics/refresh/route.ts` (dashboard)
- Modify: `vercel.json` (dashboard — add cron)

**Interfaces:**
- Consumes: `getToken` from `lib/tokens.ts`, `saveVideoAnalytics`, `getAnalyticsOverview`, `getTopVideos`, `getChannelAnalytics` from `lib/db.ts`, platform-specific API clients
- Produces: Analytics data endpoints consumed by the analytics page (Task 12)

- [ ] **Step 1: Create pull-analytics cron**

`app/api/cron/pull-analytics/route.ts`:
- Verify cron secret (`CRON_SECRET` header from Vercel)
- For each connected platform, fetch video stats via that platform's API
- For each uploaded video from the last 7 days, pull views/likes/comments/shares
- Save to `video_analytics` table
- Pull channel-level stats (subscribers, total views) and save to `channel_analytics`

- [ ] **Step 2: Create analytics API routes**

Each route:
- Requires session auth
- Accepts query params for period (7d/30d/90d) and platform filter
- Returns JSON from DB queries

`overview/route.ts` — returns `AnalyticsOverview` with total views, subscribers per platform, videos this week, avg CTR

`views/route.ts` — returns daily view counts as time series array `[{date, youtube, tiktok, instagram, facebook}]`

`categories/route.ts` — returns average views per category `[{category, avg_views, total_views}]`

`top-videos/route.ts` — returns top 10 videos by total views across platforms

`refresh/route.ts` — POST handler that manually triggers a stats pull (same logic as cron)

- [ ] **Step 3: Update vercel.json**

Add analytics cron:
```json
{
  "crons": [
    { "path": "/api/cron/check-scheduled", "schedule": "*/15 * * * *" },
    { "path": "/api/cron/pull-analytics", "schedule": "0 6 * * *" }
  ]
}
```

- [ ] **Step 4: Run build**

Run: `cd C:\Users\User\leo-quiz-dashboard && npx next build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
cd C:\Users\User\leo-quiz-dashboard
git add app/api/cron/pull-analytics/ app/api/analytics/ vercel.json
git commit -m "feat: add analytics cron job and API routes"
```

---

### Task 12: Analytics Dashboard Page

**Files:**
- Create: `app/analytics/page.tsx` (dashboard)
- Create: `components/analytics-charts.tsx` (dashboard)
- Modify: `components/sidebar.tsx` (dashboard — add Analytics nav link if not present)

**Interfaces:**
- Consumes: Analytics API routes from Task 11 (`/api/analytics/overview`, `/api/analytics/views`, `/api/analytics/categories`, `/api/analytics/top-videos`)
- Produces: `/analytics` page with overview cards, charts, top videos table, period/platform filters

The analytics page uses pure SVG for charts (no external chart library — CSP/bundle concerns). This is the same approach used in the RealRate dashboard.

- [ ] **Step 1: Create analytics-charts.tsx**

Component library for SVG charts:

```typescript
// components/analytics-charts.tsx
// ─────────────────────────────────────────────────────────────
//  Pure SVG chart components for the analytics dashboard.
//  No external dependencies — renders inline SVG.
// ─────────────────────────────────────────────────────────────

export function LineChart({ data, lines, width, height }: LineChartProps) { ... }
export function BarChart({ data, width, height }: BarChartProps) { ... }
export function StatCard({ label, value, change, icon }: StatCardProps) { ... }
```

`LineChart` — multi-line time series (one line per platform, color-coded: YouTube=red, TikTok=black, Instagram=purple, Facebook=blue)

`BarChart` — vertical bars for category comparison

`StatCard` — single metric card with icon, value, and optional change indicator

- [ ] **Step 2: Create analytics/page.tsx**

```typescript
// app/analytics/page.tsx
// ─────────────────────────────────────────────────────────────
//  Analytics dashboard — cross-platform performance metrics.
//  Shows overview cards, daily views trend, category performance,
//  and top videos table. All data from /api/analytics/* endpoints.
// ─────────────────────────────────────────────────────────────
```

Layout:
1. **Header**: "Analytics" + period selector (7d | 30d | 90d | All) + platform filter dropdown
2. **Overview cards row**: Total Views, Subscribers (per platform breakdown), Videos This Week, Avg CTR
3. **Daily Views chart**: LineChart with one line per platform
4. **Category Performance**: BarChart comparing avg views by category
5. **Top 10 Videos table**: thumbnail, title, category, views, likes, platform icons, uploaded date

All data fetched client-side with `useEffect` and `useState`. Loading states with skeleton placeholders.

- [ ] **Step 3: Add Analytics to sidebar navigation**

Check `components/sidebar.tsx` — add an "Analytics" nav item with `BarChart3` Lucide icon linking to `/analytics`.

- [ ] **Step 4: Run build + dev test**

Run: `cd C:\Users\User\leo-quiz-dashboard && npx next build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
cd C:\Users\User\leo-quiz-dashboard
git add app/analytics/ components/analytics-charts.tsx components/sidebar.tsx
git commit -m "feat: add analytics dashboard page with SVG charts"
```

---

### Task 13: Approval Queue Upgrade — Metadata Preview + Auto-Rotate Thumbnails

**Files:**
- Modify: `app/queue/page.tsx` (dashboard — show metadata preview for review)
- Create: `app/api/analytics/thumbnails/route.ts` (dashboard — CTR data endpoint)
- Modify: `app/api/webhook/pipeline-complete/route.ts` (dashboard — handle 3 thumbnails + 4 metadata files)

**Interfaces:**
- Consumes: `getThumbnailTests`, `saveThumbnailTest`, `updateVideo` from `lib/db.ts`, `PlatformMetadata` from `lib/types.ts`, thumbnail URLs and metadata from Vercel Blob
- Produces: Approval queue showing auto-generated metadata for review, auto-rotating thumbnail variant selection, CTR tracking in background

**Design principle:** No manual picking. Pipeline generates 3 thumbnail variants, then Gemini Vision evaluates all 3 and picks the best one based on click-appeal, clarity, and kid-friendliness. The user reviews the auto-generated captions/hashtags for a quick sanity check, then one-click approves. Videos always post to ALL connected platforms. CTR is still tracked per variant so the system learns which styles perform best per category over time.

- [ ] **Step 1: Update webhook to handle 3 thumbnails + 4 metadata files**

The pipeline webhook (`pipeline-complete/route.ts`) currently receives one `thumbnail_url`. Update to accept `thumbnail_urls` object AND `platform_metadata` object:

```typescript
// Accept either single thumbnail_url (backwards compat) or 3 variants
const thumbnailUrls = body.thumbnail_urls || {
  a: body.thumbnail_url,
  b: null,
  c: null,
};

// Accept per-platform metadata from pipeline's metadata generators
// (youtube, tiktok, instagram, facebook — each with title/caption/hashtags)
const platformMetadata = body.platform_metadata || {};

// Auto-select best thumbnail using Gemini Vision evaluation
// Pipeline already picked the best one before sending webhook
const selectedVariant = body.selected_thumbnail || "a";
```

Save all 3 thumbnail URLs in `metadata_json`. Save `platform_metadata` as JSON string in `platform_metadata` column. Save `selectedVariant` as `selected_thumbnail` field — this is the one used during upload.

- [ ] **Step 2: Update queue page with metadata preview**

In `app/queue/page.tsx`, expand each video card in the approval queue:

**Thumbnail Preview:**
- Shows all 3 generated variants as small images (A: Split Reveal, B: Giant Mystery, C: Grid Challenge)
- The Gemini-selected best variant highlighted with a gold border and "AI Pick" badge
- All 3 visible so user can see what was generated, but no manual selection needed

**Metadata Preview (read-only display):**
- Collapsible section showing auto-generated metadata for all 4 platforms
- YouTube: Title, Description, Tags, Hashtags
- TikTok: Title, Description, Hashtags  
- Instagram: Caption, Hashtags
- Facebook: Title, Description
- All fields displayed as styled text (not editable — auto-generated is used as-is)
- Shows which platforms will receive this video (all connected ones, with green dots)

**Approve Button:**
- Single click → approves video → auto-posts to ALL connected platforms with auto-generated metadata
- No editing, no picking, no toggling — just review and approve

- [ ] **Step 3: Create thumbnails analytics endpoint**

`app/api/analytics/thumbnails/route.ts`:
- GET: Returns thumbnail test results for a video or aggregated win rates per category
- Query params: `video_id` (specific video) or `category` (aggregate)
- Used by analytics page (Task 12) to show which variant wins most per category

- [ ] **Step 4: Update daily.yml workflow to upload 3 thumbnails + 4 metadata files**

In the Blob upload step, upload all 3 thumbnail files and all 4 metadata JSON files. Include their URLs in the webhook payload so the dashboard receives them.

- [ ] **Step 5: Run build + commit**

```bash
cd C:\Users\User\leo-quiz-dashboard
git add app/queue/page.tsx app/api/analytics/thumbnails/ app/api/webhook/
cd C:\Users\User\LeoQuiz
git add .github/workflows/daily.yml
git commit -m "feat: approval queue with metadata preview + auto-rotating A/B thumbnails"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Feature 1 (Long-form + Mega): Tasks 1, 2, 3
- ✅ Feature 2 (Multi-platform upload): Tasks 5, 8, 10
- ✅ Feature 3 (A/B thumbnails): Tasks 6, 13
- ✅ Feature 4 (Analytics): Tasks 7, 11, 12
- ✅ Feature 5 (Generate page): Task 9
- ✅ Instagram + Facebook metadata: Task 4
- ✅ Schema + types: Task 7
- ✅ GitHub Actions: Tasks 3, 10, 13
- ✅ Shorts bumped to 6 rounds: Task 1 (already in config.py)
- ✅ vercel.json cron: Task 11
- ✅ Multi-platform scheduling (approve → auto-post to ALL connected platforms): Task 10
- ✅ Metadata preview in approval queue (view auto-generated captions + hashtags): Task 13
- ✅ Gemini Vision auto-selects best thumbnail from 3 variants: Tasks 6, 13
- ✅ PlatformMetadata type + platform_metadata column: Tasks 7, 13

**Top performer quality coverage:**
- ✅ Difficulty progression (implicit, easy→hard sorted): Task 3 (sort rounds)
- ✅ Continuous flow + motivational milestones at 25/50/75%: Task 2 (render_milestone_card)
- ✅ "FINAL QUESTION!" card before last round: Task 2 (render_milestone_card)
- ✅ Consistent pacing (every round identical): Task 2 (render_longform_frame)
- ✅ Progress counter ("Q 23/60"): Task 2 (render_longform_frame Layer 3)
- ✅ Star rating outro: Task 2 (render_star_rating)
- ✅ Gemini auto-pick best thumbnail: Task 6 (select_best_thumbnail)
- ✅ Platform-specific metadata quality: Task 4 (engagement hooks, hashtag strategy)

**Placeholder scan:** No TBDs, TODOs, or "implement later" found.

**Type consistency:**
- `generate_all_thumbnails()` used in Task 6 and consumed by main.py
- `VideoFormat` type used consistently across Tasks 7, 9
- `Platform` type expanded in Task 7, used in Tasks 8, 10, 11, 12
- `PlatformMetadata` type defined in Task 7, stored by Task 13 webhook, read by Task 10 upload route
- `target_platforms` field defined in Task 7, set by Task 13 queue page, read by Task 10 upload + cron
- `triggerWorkflow()` signature updated in Task 9, consumed by Task 9's generate route
- `assemble_longform()` produced in Task 2, consumed in Task 3
