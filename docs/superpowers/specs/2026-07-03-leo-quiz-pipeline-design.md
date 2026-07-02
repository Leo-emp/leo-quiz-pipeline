# Leo Quiz — Automated Kids Quiz Video Pipeline

**Date:** 2026-07-03
**Status:** Design
**Project:** Separate from Luminous Will — completely independent codebase

---

## Overview

Fully automated pipeline that generates high-production-quality kids quiz videos (silhouette/shadow guess format), uploads daily to YouTube and TikTok. Mascot: **Leo the Lion** — cute cartoon lion character that hosts every video.

Target: daily shorts (60s, 9:16) + weekly long-form compilations (15-20 min, 16:9). Content is unlimited — Gemini generates fresh quiz packs from an infinite pool of topics, never repeating.

---

## 1. Video Format & Structure

### 1.1 Short-Form (60s, 9:16 vertical, daily)

5 quiz rounds per video, ~10 seconds each:

```
[0.0s]  Intro (2s) — Leo waves in + upbeat jingle + "Can you guess the animal?"
[2.0s]  Round 1 begins
         → Silhouette slides in from side (0.5s ease-in)
         → "What animal is this?" (voice)
         → Pause (1.5s) — let kids think
         → Countdown 3-2-1 (3s) — numbers bounce-scale in, tick SFX each
         → REVEAL — image pops in from 80%→100% scale + "ding!" SFX
         → "It's a Lion!" (voice) + Leo celebrates
         → Fun fact types in word-by-word + voice reads it (2s)
         → Score counter updates + whoosh transition
[12.0s] Round 2 begins
         ... (same pattern)
[52.0s] Round 5 reveal + final score
[56.0s] Outro (4s) — "How many did you get? Subscribe for more!" + Leo waves
```

### 1.2 Long-Form (15-20 min, 16:9 horizontal, weekly)

80-100 rounds compiled from the week's content + bonus rounds:

```
[Intro - 10s]      Leo welcomes, explains rules, today's theme
[Section 1 - Easy]  25 rounds + category title card
[Transition]        "Getting harder!" — animated transition
[Section 2 - Medium] 25 rounds
[Transition]        "Expert level!" — animated transition
[Section 3 - Hard]  25 rounds
[Section 4 - Bonus] 5-10 extra tricky rounds
[Outro - 10s]       Final score reveal, "How did you do?", subscribe CTA
```

Long-form adds:
- Running score tracker in top-right corner
- Difficulty badge per round (star rating)
- Category title cards between sections
- Progress bar at bottom

---

## 2. Visual Design

### 2.1 Layout — Short (9:16)

```
┌─────────────────────┐
│   GUESS THE ANIMAL  │  ← Branded title bar (category color)
│                     │
│                     │
│    [SILHOUETTE]     │  ← Main content area (centered)
│     or [REVEAL]     │
│                     │
│                     │
│  "What is this?"    │  ← Question/answer text (bold, outlined)
│                     │
│     ⏱️ 3  2  1     │  ← Countdown (bounce-scale animation)
│                     │
│  ⭐ Score: 3/5      │  ← Score tracker
│  🦁 Leo    [logo]   │  ← Mascot + channel branding
└─────────────────────┘
```

### 2.2 Layout — Long-Form (16:9)

```
┌──────────────────────────────────────────┐
│ 🦁 LEO QUIZ          ⭐ Score: 12/25    │  ← Top bar (persistent)
│                                          │
│           [SILHOUETTE / REVEAL]          │  ← Center (large)
│                                          │
│       "What animal is this?"             │  ← Text below image
│           ⏱️  3  2  1                    │  ← Countdown
│                                          │
│   Fun fact: Lions sleep 20 hrs/day!      │  ← Bottom info bar
│ ████████████░░░░░░░░  Round 12/25        │  ← Progress bar
└──────────────────────────────────────────┘
```

### 2.3 Color System (per category)

Each category has its own gradient theme for backgrounds and UI elements:

| Category | Primary | Secondary | Background Gradient |
|----------|---------|-----------|-------------------|
| Animals | #2ECC71 (emerald) | #27AE60 | Green → Teal |
| Dinosaurs | #E67E22 (orange) | #D35400 | Orange → Dark Red |
| Space | #3498DB (blue) | #8E44AD (purple) | Deep Blue → Purple |
| Vehicles | #E74C3C (red) | #7F8C8D (steel) | Red → Dark Grey |
| Fruits | #F1C40F (yellow) | #E91E63 (pink) | Yellow → Pink |
| Flags | #9B59B6 (purple) | #1ABC9C (teal) | Multicolor gradient |

### 2.4 Motion & Animation

Nothing is static. Every element has motion:

- **Silhouette entrance:** slides in from left/right with ease-out curve (0.5s)
- **Countdown numbers:** scale up from 0%→100% with bounce overshoot, one per second
- **Reveal:** image scales from 80%→105%→100% (pop effect, 0.3s)
- **Fun fact text:** word-by-word type-in (synced to voice timing)
- **Score counter:** number ticks up with scale pulse
- **Leo mascot:** 2-3 frame idle bounce loop; switches to celebrate pose on reveal
- **Background:** slow-drifting particle/sparkle overlay (subtle, adds depth)
- **Transitions between rounds:** horizontal wipe or scale-out/scale-in (0.3s)

### 2.5 Typography

- **Title/headers:** Bold rounded sans-serif (Baloo 2 or Fredoka One) — playful, kid-friendly
- **Question text:** White with dark stroke outline — readable on any background
- **Answer text:** Category primary color, large, bold — celebratory feel
- **Fun fact:** Slightly smaller, white, gentle fade-in
- **Countdown numbers:** Extra bold, large (fills ~30% of frame), category color with white outline

---

## 3. Leo the Lion Mascot

### 3.1 Character Design

Cute cartoon lion — big eyes, friendly smile, fluffy mane. Kawaii/chibi proportions (large head, small body). Consistent across every video.

**Generated once** via AI image generation, then saved as static assets. Not generated per-video.

### 3.2 Poses (PNG assets with transparent background)

| Pose | When Used | Description |
|------|-----------|-------------|
| `thinking.png` | During silhouette/question phase | Leo with paw on chin, looking curious |
| `excited.png` | During reveal/answer phase | Leo jumping with arms up, big smile |
| `waving.png` | Intro and outro | Leo waving at camera |
| `surprised.png` | Hard questions / bonus rounds | Leo with wide eyes, mouth open |

### 3.3 Placement

- **Shorts:** Bottom-right corner, ~15% of frame height
- **Long-form:** Left side of top bar (small) + bottom-right during rounds (~10% of frame)
- Leo has a subtle idle bounce animation (2-3 frames looping, ~0.5s cycle)

---

## 4. Content Generation Engine

### 4.1 Quiz Pack Generation (Gemini)

Each pipeline run, Gemini generates a quiz pack:

```json
{
  "category": "animals",
  "difficulty_mix": ["easy", "easy", "medium", "medium", "hard"],
  "rounds": [
    {
      "answer": "Lion",
      "hint_question": "This animal is called the king of the jungle!",
      "fun_fact": "Lions can sleep up to 20 hours a day!",
      "difficulty": "easy",
      "image_prompt": "Cute cartoon illustration of a lion, colorful, kid-friendly style, white background, clean edges, full body, facing slightly left"
    }
  ]
}
```

**Prompt engineering:**
- Gemini receives the full `history.json` of previously used answers
- Instructed: "Never repeat any answer from the history. Generate completely new, interesting, surprising choices."
- Difficulty defined: easy = common animals kids know, medium = less common but recognizable, hard = rare/exotic
- Fun facts must be kid-appropriate, surprising, and under 15 words

### 4.2 Category Rotation

Daily auto-rotation through 6 categories:
- Monday: Animals
- Tuesday: Dinosaurs
- Wednesday: Space
- Thursday: Vehicles
- Friday: Fruits & Vegetables
- Saturday: Flags & Countries
- Sunday: Mixed (all categories)

### 4.3 Never-Repeat System

`history.json` tracks every answer used:

```json
{
  "animals": ["Lion", "Elephant", "Tiger", "Blue Whale"],
  "dinosaurs": ["T-Rex", "Triceratops"],
  "total_used": 156,
  "last_updated": "2026-07-15"
}
```

Gemini receives this as context. Even after 1000+ videos, content stays fresh:
- Animals: 8,000+ species available
- Dinosaurs: 1,000+ known species
- Space objects: thousands (planets, moons, stars, nebulae, spacecraft, astronauts)
- Vehicles: thousands (cars, planes, ships, trains, construction, military)
- Fruits & vegetables: hundreds
- Countries & flags: 195

---

## 5. Image Pipeline

### 5.1 Quiz Image Generation

**Provider:** Gemini Imagen (free tier, already have API key)

**Prompt template:**
```
Cute colorful cartoon illustration of a [ANSWER], kid-friendly style,
bright vibrant colors, clean edges, full body view, centered,
pure white background, no text, no watermark, high quality,
children's book illustration style
```

**Output:** 1024x1024 PNG, white background

**Consistency:** Same prompt template ensures consistent art style across all images. The "children's book illustration style" anchor keeps everything cohesive.

### 5.2 Silhouette Extraction

Pure image processing with Pillow (no AI needed):

1. Load AI-generated image (white background)
2. Convert to grayscale
3. Threshold: anything not-white becomes pure black
4. Apply slight Gaussian blur to smooth edges (1-2px)
5. Save as silhouette PNG with transparent background

This gives clean, recognizable silhouettes because the AI images have:
- Clean edges (prompted for)
- White backgrounds (easy to separate)
- Full body views (complete silhouette shape)

### 5.3 Frame Composition

For each round, generate these frames using Pillow:

1. **Question frame:** Category gradient background + silhouette (centered) + question text + Leo (thinking) + score
2. **Countdown frames:** Same as question frame + large "3", "2", "1" numbers (3 separate frames)
3. **Reveal frame:** Same background + full color image (scaled up) + answer text + Leo (excited)
4. **Fun fact frame:** Same as reveal + fun fact text overlay

All frames rendered at:
- 1080x1920 (9:16 shorts)
- 1920x1080 (16:9 long-form)

---

## 6. Audio Pipeline

### 6.1 Narration (ElevenLabs)

**Voice:** Warm, friendly, enthusiastic — selected once, used consistently. Leo's voice.

**Lines per round (generated as individual clips):**
1. "What [category] is this?" (question)
2. "It's a [answer]!" (reveal)
3. "[Fun fact]" (fact)

**Lines per video (intro/outro):**
1. "Hi friends! Can you guess the [category]?" (intro)
2. "How many did you get right? Subscribe for more!" (outro)

**Word-level timestamps** from ElevenLabs used to sync fun fact word-by-word animation.

### 6.2 Sound Effects (Bundled)

Pre-downloaded royalty-free SFX in `assets/sfx/`:

| File | When | Source |
|------|------|--------|
| `tick.wav` | Each countdown number | Pixabay/Freesound |
| `ding.wav` | Correct reveal | Pixabay/Freesound |
| `whoosh.wav` | Round transitions | Pixabay/Freesound |
| `applause.wav` | After hard question reveals | Pixabay/Freesound |
| `drumroll.wav` | Before bonus round reveals | Pixabay/Freesound |
| `jingle_intro.wav` | Video intro | Pixabay/Freesound |
| `jingle_outro.wav` | Video outro | Pixabay/Freesound |

### 6.3 Background Music

Upbeat, kid-friendly instrumental loop. One track per category mood:
- Animals/Fruits: playful, bouncy
- Dinosaurs/Vehicles: adventurous, energetic
- Space: wonder, magical
- Flags: world music feel

Mixed at ~15-20% volume. Dips to ~10% during voice narration. Back to 20% during countdown/transitions.

### 6.4 Audio Assembly

Final mix per video:
```
Layer 1: Background music (continuous, looping, ducked during voice)
Layer 2: Voice narration (per-round clips placed at correct timestamps)
Layer 3: Sound effects (tick, ding, whoosh at transition points)
```

Normalized to -3dB peak (same standard as Luminous Will).

---

## 7. Video Assembly (MoviePy)

### 7.1 Short-Form Assembly

```python
# Per round (~10s):
silhouette_clip    = ImageClip(question_frame, duration=2.0)     # slide-in effect
countdown_3        = ImageClip(countdown_3_frame, duration=1.0)  # bounce-scale
countdown_2        = ImageClip(countdown_2_frame, duration=1.0)  # bounce-scale
countdown_1        = ImageClip(countdown_1_frame, duration=1.0)  # bounce-scale
reveal_clip        = ImageClip(reveal_frame, duration=2.0)       # pop-scale effect
fun_fact_clip      = ImageClip(fact_frame, duration=2.5)         # word-by-word overlay
transition         = TransitionClip(duration=0.3)                # whoosh wipe

# Concatenate all rounds + intro + outro
# Add audio layers
# Export: 1080x1920, 30fps, H.264
```

### 7.2 Long-Form Compilation

Weekly job that:
1. Loads all completed short-form round assets from the week
2. Adds section title cards ("Easy Round!", "Getting Harder!", "Expert Level!")
3. Adds running score counter overlay
4. Adds progress bar overlay
5. Renders new intro/outro for compilation
6. Exports: 1920x1080, 30fps, H.264, higher bitrate (8000k)

### 7.3 Thumbnail Generation

Auto-generated for every video:
- **Layout:** Split — silhouette on left half, colorful reveal on right half
- **Text:** "CAN YOU GUESS?" in bold, large, white with dark stroke
- **Leo mascot:** Surprised pose, larger than in-video (~25% of frame)
- **Border:** Bright yellow/red — pops in YouTube search results
- **Category color:** Background uses category gradient

---

## 8. Automation & Scheduling

### 8.1 Daily Pipeline (Shorts)

```
Cron: Every day at 6:00 AM UTC

1. Select today's category (day-of-week rotation)
2. Generate quiz pack (Gemini) — 5 rounds
3. Generate 5 cartoon images (Gemini Imagen)
4. Create 5 silhouettes (Pillow)
5. Compose all frames (question, countdown, reveal, fact)
6. Generate narration clips (ElevenLabs)
7. Assemble video (MoviePy)
8. Generate thumbnail
9. Generate metadata (title, description, tags via Gemini)
10. Save to output/ with all assets
11. Upload to YouTube Shorts + TikTok
```

### 8.2 Weekly Pipeline (Long-form)

```
Cron: Every Sunday at 8:00 AM UTC

1. Collect all round assets from the past 7 days
2. Generate compilation intro/outro narration
3. Add section title cards + score counter + progress bar
4. Assemble long-form video
5. Generate long-form thumbnail
6. Generate long-form metadata
7. Upload to YouTube (regular video, not short)
```

### 8.3 Scheduler Options

- **Local cron** — `scheduler.py` with APScheduler (for local/VPS runs)
- **GitHub Actions** — `.github/workflows/daily.yml` (free, cloud-based, reliable)

---

## 9. Upload & Publishing

### 9.1 YouTube

- **Shorts:** Title format: "Guess the [Category]! 🦁 Can You Get 5/5? #shorts"
- **Long-form:** Title format: "100 [Category] Quiz Questions! 🦁 How Many Can You Guess?"
- **Description:** Auto-generated with quiz answers as chapters (timestamps), SEO keywords, subscribe CTA
- **Tags:** Category-specific + "kids quiz", "guess the animal", "fun quiz for kids"
- **Made for Kids:** Set to YES (COPPA compliant)
- **Playlist:** Auto-add to category playlist

### 9.2 TikTok

- Shorts only (9:16 format)
- Title: shorter, hashtag-heavy
- Hashtags: #guesstheanimal #kidsquiz #leoquiz #funforkids

### 9.3 Metadata Generation (Gemini)

Gemini generates platform-optimized titles, descriptions, and tags per video. Prompt includes:
- Video content (category, answers, difficulty)
- Platform constraints (YouTube title length, TikTok hashtag strategy)
- SEO keywords for kids content

---

## 10. Project Structure

```
LeoQuiz/
├── main.py                    # Orchestrator — runs full pipeline
├── config.py                  # All settings, paths, API keys, colors
├── quiz_generator.py          # Gemini quiz pack generation
├── image_generator.py         # Gemini Imagen image generation
├── silhouette.py              # Pillow silhouette extraction
├── frame_composer.py          # Pillow frame composition (layouts, text, mascot)
├── narration.py               # ElevenLabs voice generation
├── audio_mixer.py             # Audio assembly (voice + SFX + music)
├── video_assembler.py         # MoviePy video assembly with motion
├── thumbnail.py               # Auto thumbnail generation
├── metadata.py                # Gemini metadata generation
├── compiler.py                # Weekly long-form compilation
├── uploader.py                # YouTube + TikTok upload
├── scheduler.py               # Cron scheduler
├── history.json               # Never-repeat tracking
├── .env                       # API keys
├── requirements.txt           # Dependencies
├── assets/
│   ├── mascot/                # Leo poses (thinking, excited, waving, surprised)
│   ├── sfx/                   # Sound effects (tick, ding, whoosh, applause, jingles)
│   ├── music/                 # Background music per mood
│   └── fonts/                 # Baloo2-Bold, FredokaOne
├── output/
│   ├── shorts/                # Daily output
│   │   ├── 2026-07-03_animals/
│   │   │   ├── video.mp4
│   │   │   ├── thumbnail.png
│   │   │   ├── metadata.json
│   │   │   └── rounds/       # Individual round assets (for compilation)
│   │   └── ...
│   └── longform/              # Weekly compilations
├── .github/
│   └── workflows/
│       ├── daily.yml          # Daily short generation
│       └── weekly.yml         # Weekly compilation
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-07-03-leo-quiz-pipeline-design.md
```

---

## 11. Tech Stack

| Component | Technology | Cost |
|-----------|-----------|------|
| Quiz content | Gemini 2.5 Flash | Free tier |
| Image generation | Gemini Imagen | Free tier |
| Silhouette extraction | Pillow | Free |
| Frame composition | Pillow | Free |
| Voice narration | ElevenLabs | Free tier (10K chars/month — ~15-20 videos, upgrade if daily) |
| Video assembly | MoviePy | Free |
| Background music | Pixabay/Freesound downloads | Free |
| Sound effects | Pixabay/Freesound downloads | Free |
| Fonts | Google Fonts (Baloo 2, Fredoka) | Free |
| Scheduling | GitHub Actions / APScheduler | Free |
| YouTube upload | YouTube Data API v3 | Free |
| TikTok upload | TikTok Content Posting API | Free |

**Total monthly cost: $0** (all free tiers)

---

## 12. Quality Guardrails

- **Image quality check:** Verify Imagen output is not blurry/malformed before proceeding
- **Silhouette validation:** Ensure silhouette is recognizable (not too simple/complex) — check pixel coverage %
- **Audio normalization:** All output normalized to -3dB peak
- **Content safety:** Gemini prompted to generate only kid-appropriate content; no scary, violent, or inappropriate facts
- **COPPA compliance:** All uploads marked "Made for Kids", no data collection, no personalized content

---

## 13. Future Expansion (Not in V1)

These can be added later as new format modules without changing core pipeline:

- **Zoom-in reveal format:** extreme close-up → zoom out to reveal
- **Odd one out format:** grid of similar images, spot the different one
- **Emoji guess format:** guess the animal/movie/food from emoji combinations
- **Sound guess format:** play an animal sound, guess what it is
- **Multiple channels:** same pipeline, different category focus per channel
- **Additional platforms:** Instagram Reels, Facebook
