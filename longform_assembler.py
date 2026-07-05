# longform_assembler.py
# ============================================================
# Frame-by-frame 16:9 landscape video renderer for long-form
# and mega quiz videos. Mirrors video_assembler.py's architecture
# but repositioned for horizontal layout.
#
# Long-form: 60 rounds × 8s = ~10 minutes
# Mega quiz: 100 rounds × 7s = ~15 minutes
#
# Top performer quality standard:
# - Continuous flow (questions back-to-back)
# - Motivational milestone cards at 25%, 50%, 75% + FINAL QUESTION
# - Consistent pacing (every round identical)
# - Star rating outro with subscribe CTA
# - Progress counter visible throughout
# ============================================================
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

import config
from animations import (
    ease_value, compute_scale, compute_opacity,
    compute_slide_x, compute_bounce_y, ParticleSystem
)
from frame_composer import (
    render_gradient_background, render_text, render_text_wrapped,
    render_pill_background, hex_to_rgb, _get_font
)
from effects import (
    ConfettiBurst, ScreenShake, KenBurnsZoom, GlowRing,
    ProgressIndicator, ThemedDecorations, CountdownBar,
    render_glow_text, render_rainbow_text, apply_vignette
)
from quiz_generator import QuizRound, QuizPack
from narration import RoundAudio


@dataclass
class LongformContext:
    """# All data needed to render any frame of a long-form video.
    # Same pattern as VideoContext but for 16:9 landscape layout."""
    width: int                     # Frame width (1920)
    height: int                    # Frame height (1080)
    category: str                  # Quiz category for colors/labels
    rounds: list[QuizRound]        # All quiz round data
    image_paths: list[Path]        # Paths to full-color images
    silhouette_paths: list[Path]   # Paths to silhouette images
    mascot_images: dict            # {"thinking": Image, "excited": Image, ...}
    particle_system: ParticleSystem  # Sparkle overlay system
    themed_decorations: ThemedDecorations  # Category-themed floating shapes
    format_type: str = "long"      # "long" or "mega"
    total_rounds: int = 60         # Total number of rounds
    confetti_bursts: list[ConfettiBurst] = field(default_factory=list)
    round_audios: list[RoundAudio] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)


def _get_timing(format_type: str) -> dict:
    """# Return the correct timing constants based on format type.
    # Long-form uses 8s rounds, mega uses 7s rounds."""
    if format_type == "mega":
        return {
            "round_duration": config.MEGA_ROUND_DURATION,
            "timer_seconds": config.MEGA_TIMER_SECONDS,
            "intro_duration": config.MEGA_INTRO_DURATION,
            "outro_duration": config.MEGA_OUTRO_DURATION,
            "silhouette_start": config.MEGA_SILHOUETTE_START,
            "countdown_start": config.MEGA_COUNTDOWN_START,
            "reveal_start": config.MEGA_REVEAL_START,
            "fun_fact_start": config.MEGA_FUN_FACT_START,
            "transition_start": config.MEGA_TRANSITION_START,
        }
    else:
        return {
            "round_duration": config.LONGFORM_ROUND_DURATION,
            "timer_seconds": config.LONGFORM_TIMER_SECONDS,
            "intro_duration": config.LONGFORM_INTRO_DURATION,
            "outro_duration": config.LONGFORM_OUTRO_DURATION,
            "silhouette_start": config.LONGFORM_SILHOUETTE_START,
            "countdown_start": config.LONGFORM_COUNTDOWN_START,
            "reveal_start": config.LONGFORM_REVEAL_START,
            "fun_fact_start": config.LONGFORM_FUN_FACT_START,
            "transition_start": config.LONGFORM_TRANSITION_START,
        }


def _get_milestone_rounds(num_rounds: int) -> dict[int, str]:
    """# Calculate which rounds get motivational milestone cards.
    # Cards appear at 25%, 50%, 75% and before the final question.
    # Returns dict of {round_index: message}."""
    milestones = {}
    # 25% milestone
    q25 = num_rounds // 4
    milestones[q25] = "Great start! Keep going!"
    # 50% milestone
    q50 = num_rounds // 2
    milestones[q50] = "HALFWAY! You're doing amazing!"
    # 75% milestone
    q75 = (num_rounds * 3) // 4
    remaining = num_rounds - q75
    milestones[q75] = f"Almost there! Just {remaining} more!"
    # Final question card (before last round)
    milestones[num_rounds - 1] = "FINAL QUESTION!"
    return milestones


def build_longform_round_timeline(round_index: int, round_start: float,
                                   format_type: str) -> list[dict]:
    """# Build timed events for one long-form quiz round.
    # Uses format-specific timing constants (long vs mega).
    # Same phase structure as shorts: silhouette → countdown → reveal → fun_fact."""
    timing = _get_timing(format_type)
    t = round_start
    timer_secs = timing["timer_seconds"]

    # Calculate countdown phase boundaries
    countdown_start = t + timing["countdown_start"]
    countdown_per_sec = (timing["reveal_start"] - timing["countdown_start"]) / timer_secs

    events = [
        # Silhouette slides in
        {"phase": "silhouette", "start": t + timing["silhouette_start"],
         "end": countdown_start, "round": round_index},
    ]

    # Individual countdown number events (5, 4, 3, 2, 1 for long-form)
    for i in range(timer_secs):
        number = timer_secs - i
        events.append({
            "phase": f"countdown_{number}",
            "start": countdown_start + i * countdown_per_sec,
            "end": countdown_start + (i + 1) * countdown_per_sec,
            "round": round_index,
            "number": number,
        })

    # Reveal and fun fact phases
    events.extend([
        {"phase": "reveal", "start": t + timing["reveal_start"],
         "end": t + timing["fun_fact_start"], "round": round_index},
        {"phase": "fun_fact", "start": t + timing["fun_fact_start"],
         "end": t + timing["round_duration"], "round": round_index},
    ])

    return events


def build_longform_timeline(num_rounds: int, round_duration: float,
                             format_type: str) -> list[dict]:
    """# Build complete long-form video timeline.
    # Structure: intro → rounds (with milestone cards at 25/50/75%) → outro.
    # Milestone cards are 2s motivational hype messages inserted between rounds."""
    timing = _get_timing(format_type)
    timeline = []

    # Intro phase — "CAN YOU GUESS ALL 60?" hype
    timeline.append({
        "phase": "intro",
        "start": 0.0,
        "end": timing["intro_duration"],
        "round": -1,
    })

    # Get milestone positions (which rounds get hype cards)
    milestones = _get_milestone_rounds(num_rounds)
    card_duration = config.LONGFORM_SECTION_CARD_DURATION

    # Track current time position (intro end)
    current_time = timing["intro_duration"]

    # Build all rounds with milestone cards inserted before key rounds
    for i in range(num_rounds):
        # Insert milestone card BEFORE this round if it's a milestone position
        if i in milestones:
            timeline.append({
                "phase": "milestone",
                "start": current_time,
                "end": current_time + card_duration,
                "round": -1,
                "message": milestones[i],
            })
            current_time += card_duration

        # Add this round's events
        round_events = build_longform_round_timeline(i, current_time, format_type)
        timeline.extend(round_events)
        current_time += timing["round_duration"]

    # Outro phase — star rating + subscribe CTA
    timeline.append({
        "phase": "outro",
        "start": current_time,
        "end": current_time + timing["outro_duration"],
        "round": -1,
    })

    return timeline


def _get_current_event(t: float, timeline: list[dict]) -> dict:
    """# Find which timeline event is active at time t.
    # Same pattern as video_assembler._get_current_event."""
    for event in timeline:
        if event["start"] <= t < event["end"]:
            return event
    # Default to last event if past end
    return timeline[-1] if timeline else {"phase": "intro", "start": 0, "end": 0, "round": -1}


def _composite_image_on_frame(frame_img: Image.Image, overlay: Image.Image,
                               center_x: int, center_y: int,
                               scale: float = 1.0, opacity: float = 1.0) -> Image.Image:
    """# Paste an RGBA image onto the frame at a given center position.
    # Same helper as video_assembler — reused for landscape layout."""
    if scale <= 0 or opacity <= 0:
        return frame_img

    new_w = max(1, int(overlay.width * scale))
    new_h = max(1, int(overlay.height * scale))
    scaled = overlay.resize((new_w, new_h), Image.LANCZOS)

    if opacity < 1.0:
        arr = np.array(scaled)
        arr[:, :, 3] = (arr[:, :, 3] * opacity).astype(np.uint8)
        scaled = Image.fromarray(arr)

    paste_x = center_x - new_w // 2
    paste_y = center_y - new_h // 2
    frame_img.paste(scaled, (paste_x, paste_y), scaled)
    return frame_img


def render_milestone_card(frame: Image.Image, message: str, t: float,
                           event: dict, category: str) -> Image.Image:
    """# Render a 2s motivational hype card between rounds.
    # Zoom-in animation with glow text + confetti + excited mascot.
    # Messages: "Great start!", "HALFWAY!", "Almost there!", "FINAL QUESTION!" """
    w, h = frame.size
    elapsed = t - event["start"]
    duration = event["end"] - event["start"]

    # Category colors for the glow
    colors = config.CATEGORY_COLORS.get(category, config.CATEGORY_COLORS["animals"])
    primary_rgb = hex_to_rgb(colors["primary"])

    # Message text pops in with elastic bounce
    text_scale = compute_scale(elapsed, 0.0, 0.6, "elastic_out")
    font_size = int(80 * max(0.1, text_scale))

    # Glow text centered on screen
    frame = render_glow_text(frame, message,
                              position=(w // 2, int(h * 0.45)),
                              font_size=font_size,
                              glow_color=primary_rgb,
                              glow_radius=15)

    return frame


def render_star_rating(frame: Image.Image, total_rounds: int,
                        t: float, event: dict) -> Image.Image:
    """# Render the outro star rating screen.
    # Shows total rounds completed + stars + subscribe CTA.
    # Stars pop in one at a time with scale animation."""
    w, h = frame.size
    elapsed = t - event["start"]

    # "YOU COMPLETED X QUESTIONS!" bounces in
    title_scale = compute_scale(elapsed, 0.0, 0.5, "back_out")
    if title_scale > 0.01:
        frame = render_glow_text(frame, f"YOU COMPLETED {total_rounds} QUESTIONS!",
                                  position=(w // 2, int(h * 0.25)),
                                  font_size=int(60 * max(0.1, title_scale)),
                                  glow_color=(255, 200, 50))

    # Star rating — 5 stars, all filled (viewer counts their own score)
    star_text = "⭐⭐⭐⭐⭐"
    star_scale = compute_scale(elapsed, 0.3, 0.5, "elastic_out")
    if star_scale > 0.01:
        frame = render_glow_text(frame, star_text,
                                  position=(w // 2, int(h * 0.42)),
                                  font_size=int(70 * max(0.1, star_scale)),
                                  glow_color=(255, 215, 0))

    # "How many did YOU get right?" text
    score_opacity = compute_opacity(elapsed, 0.8, 0.4, "quad_out")
    if score_opacity > 0.01:
        frame = render_text(frame, "How many did YOU get right?",
                            position=(w // 2, int(h * 0.56)),
                            font_size=config.CTA_FONT_SIZE,
                            color=(255, 255, 200))

    # Subscribe CTA fades in
    cta_opacity = compute_opacity(elapsed, 1.2, 0.5, "quad_out")
    if cta_opacity > 0.01:
        frame = render_text(frame, "SUBSCRIBE for more quizzes!",
                            position=(w // 2, int(h * 0.68)),
                            font_size=config.CTA_FONT_SIZE,
                            color=(255, 255, 100))
        frame = render_text(frame, "Like & Comment your score!",
                            position=(w // 2, int(h * 0.76)),
                            font_size=config.ROUND_LABEL_FONT_SIZE,
                            color=(255, 255, 255))

    return frame


def render_longform_frame(t: float, ctx: LongformContext) -> np.ndarray:
    """# Render a single 16:9 landscape frame at time t.
    # Called 30 times per second by MoviePy.
    # Returns numpy array (1080, 1920, 3) in RGB format.
    #
    # Landscape layout (1920×1080):
    # - Header: category title (left) + progress counter (right)
    # - Content: silhouette/reveal image (centered, large)
    # - Question text below content
    # - Timer bar below question
    # - Mascot on right side
    # - Every round has identical layout (consistent pacing)
    """
    w, h = ctx.width, ctx.height

    # --- Layer 1: Background gradient (consistent throughout) ---
    bg = render_gradient_background(w, h, ctx.category, t)
    frame = bg.convert("RGBA")

    # --- Layer 2: Themed decorations (floating shapes behind content) ---
    if ctx.themed_decorations:
        frame = ctx.themed_decorations.render(frame, t)

    # --- Layer 3: Sparkle particles ---
    if ctx.particle_system:
        frame_arr = np.array(frame)[:, :, :3]
        frame_arr = ctx.particle_system.render(frame_arr, t)
        alpha = np.array(frame)[:, :, 3:]
        frame = Image.fromarray(
            np.concatenate([frame_arr, alpha], axis=2)
        )

    # Find current timeline event
    event = _get_current_event(t, ctx.timeline)
    phase = event["phase"]
    round_idx = event["round"]

    # Get timing constants for this format
    timing = _get_timing(ctx.format_type)

    # ===================================================================
    # INTRO: "CAN YOU GUESS ALL 60?" + mascot + category showcase
    # ===================================================================
    if phase == "intro":
        intro_elapsed = t - event["start"]

        # Title text pops in with elastic bounce
        title_scale = compute_scale(intro_elapsed, 0.0, 0.6, "elastic_out")
        cat_display = config.CATEGORIES[ctx.category]["display"]
        title_text = f"GUESS THE {cat_display.upper()}!"
        title_size = int((config.TITLE_FONT_SIZE + 20) * max(0.1, title_scale))

        # Title with glow effect — centered in landscape
        frame = render_glow_text(frame, title_text,
                                  position=(w // 2, int(h * 0.30)),
                                  font_size=title_size,
                                  glow_color=hex_to_rgb(
                                      config.CATEGORY_COLORS[ctx.category]["primary"]
                                  ))

        # "CAN YOU GUESS ALL 60?" subtitle hype
        sub_opacity = compute_opacity(intro_elapsed, 0.4, 0.4, "quad_out")
        if sub_opacity > 0.01:
            frame = render_text(frame, f"CAN YOU GUESS ALL {ctx.total_rounds}?",
                                position=(w // 2, int(h * 0.45)),
                                font_size=config.CTA_FONT_SIZE,
                                color=(255, 255, 200))

        # Mascot waves in from bottom
        if "waving" in ctx.mascot_images:
            mascot = ctx.mascot_images["waving"]
            mascot_scale = compute_scale(intro_elapsed, 0.2, 0.5, "back_out")
            mascot_h = int(h * 0.35)
            mascot_w = int(mascot.width * (mascot_h / mascot.height))
            mascot_resized = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
            mascot_y = int(h * 0.70 + (1 - mascot_scale) * h * 0.3)
            frame = _composite_image_on_frame(
                frame, mascot_resized, w // 2, mascot_y, scale=min(1.0, mascot_scale)
            )

        frame = apply_vignette(frame, config.VIGNETTE_INTENSITY)
        return np.array(frame.convert("RGB"))

    # ===================================================================
    # MILESTONE CARD: motivational hype messages between rounds
    # ===================================================================
    if phase == "milestone":
        message = event.get("message", "Keep going!")
        frame = render_milestone_card(frame, message, t, event, ctx.category)

        # Confetti during milestone cards
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)

        frame = apply_vignette(frame, config.VIGNETTE_INTENSITY)
        return np.array(frame.convert("RGB"))

    # ===================================================================
    # OUTRO: star rating + subscribe CTA + mascot celebration
    # ===================================================================
    if phase == "outro":
        frame = render_star_rating(frame, ctx.total_rounds, t, event)

        # Mascot celebration with bounce
        if "excited" in ctx.mascot_images:
            mascot = ctx.mascot_images["excited"]
            mascot_h = int(h * 0.28)
            mascot_w = int(mascot.width * (mascot_h / mascot.height))
            mascot_resized = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
            bounce = compute_bounce_y(t, amplitude=8.0, period=0.6)
            frame = _composite_image_on_frame(
                frame, mascot_resized, w // 2, int(h * 0.88) + int(bounce)
            )

        # Confetti during outro
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)

        frame = apply_vignette(frame, config.VIGNETTE_INTENSITY)
        return np.array(frame.convert("RGB"))

    # ===================================================================
    # QUIZ ROUND PHASES — landscape layout (1920×1080)
    # Every round has identical layout — consistent pacing
    # ===================================================================
    if round_idx < 0 or round_idx >= len(ctx.rounds):
        return np.array(frame.convert("RGB"))

    round_data = ctx.rounds[round_idx]
    total = ctx.total_rounds

    # Calculate round start time (accounting for milestone cards)
    # Find the first event for this round to get its start time
    round_events = [e for e in ctx.timeline if e["round"] == round_idx]
    round_start = round_events[0]["start"] if round_events else 0
    elapsed_in_round = t - round_start

    # Get category colors
    cat_display = config.CATEGORIES[ctx.category]["display"]
    colors = config.CATEGORY_COLORS[ctx.category]
    primary_rgb = hex_to_rgb(colors["primary"])

    # --- LANDSCAPE HEADER: category title (left) + progress (right) ---
    # Category title — top left
    frame = render_text(frame, f"GUESS THE {cat_display.upper()}!",
                        position=(int(w * 0.25), int(h * 0.06)),
                        font_size=config.TITLE_FONT_SIZE,
                        color=primary_rgb)

    # Progress counter — top right ("Q 23/60")
    frame = render_text(frame, f"Q {round_idx + 1}/{total}",
                        position=(int(w * 0.85), int(h * 0.06)),
                        font_size=config.ROUND_LABEL_FONT_SIZE + 4,
                        color=(255, 255, 255), stroke_width=2)

    # --- CONTENT AREA: centered image (landscape has more horizontal room) ---
    content_size = int(h * 0.45)  # Image sized relative to height in landscape
    content_center_x = w // 2
    content_center_y = int(h * 0.38)

    # ---------------------------------------------------------------
    # SILHOUETTE + COUNTDOWN PHASES
    # ---------------------------------------------------------------
    if phase in ("silhouette",) or phase.startswith("countdown_"):
        # Glow ring behind silhouette
        frame = GlowRing.render(frame, content_center_x, content_center_y,
                                int(content_size * 0.6), primary_rgb, t)

        # Show silhouette with slide-in animation
        if round_idx < len(ctx.silhouette_paths):
            sil = Image.open(ctx.silhouette_paths[round_idx]).convert("RGBA")
            sil = sil.resize((content_size, content_size), Image.LANCZOS)

            # Slide in from left
            slide_progress = compute_scale(
                elapsed_in_round, 0.0, config.EASE_SLIDE_IN, "cubic_out"
            )
            sil_x = int(-content_size + (content_center_x + content_size) * slide_progress)
            frame = _composite_image_on_frame(frame, sil, sil_x, content_center_y)

        # Question hint text — below content area in landscape
        q_opacity = compute_opacity(
            elapsed_in_round, 0.2, config.EASE_TEXT_IN, "quad_out"
        )
        if q_opacity > 0.01:
            q_y = int(h * 0.68)
            frame = render_pill_background(
                frame, round_data.hint_question,
                (w // 2, q_y), config.QUESTION_FONT_SIZE,
                bg_opacity=120
            )
            frame = render_text_wrapped(frame, round_data.hint_question,
                                         position=(w // 2, q_y),
                                         font_size=config.QUESTION_FONT_SIZE)

    # ---------------------------------------------------------------
    # TIMER BAR — wider in landscape, below question
    # ---------------------------------------------------------------
    if phase in ("silhouette",) or phase.startswith("countdown_"):
        guess_start = round_start + timing["silhouette_start"]
        guess_end = round_start + timing["reveal_start"]
        guess_progress = (t - guess_start) / (guess_end - guess_start)
        frame = CountdownBar.render(frame, guess_progress, primary_rgb)

    # ---------------------------------------------------------------
    # COUNTDOWN NUMBER POP — glow text centered
    # ---------------------------------------------------------------
    if phase.startswith("countdown_"):
        number = event.get("number", 3)
        countdown_elapsed = t - event["start"]
        num_scale = compute_scale(
            countdown_elapsed, 0.0, config.EASE_COUNTDOWN_IN, "back_out"
        )
        scaled_font_size = int(config.COUNTDOWN_FONT_SIZE * max(0.1, num_scale))

        # Red glow on "1" for tension
        glow_color = primary_rgb
        if number == 1:
            glow_color = (255, 50, 50)

        frame = render_glow_text(frame, str(number),
                                  position=(w // 2, int(h * 0.55)),
                                  font_size=scaled_font_size,
                                  glow_color=glow_color,
                                  glow_radius=config.GLOW_RADIUS)

        # Screen shake on "1"
        if number == 1 and countdown_elapsed > 0.3:
            frame = ScreenShake.apply(frame, t, event["start"] + 0.3,
                                       duration=0.2, intensity=6.0)

    # ---------------------------------------------------------------
    # REVEAL PHASE — rainbow answer text + confetti
    # ---------------------------------------------------------------
    if phase == "reveal":
        reveal_elapsed = elapsed_in_round - (timing["reveal_start"] - timing["silhouette_start"])

        # Full color image pops in with elastic bounce
        if round_idx < len(ctx.image_paths):
            img = Image.open(ctx.image_paths[round_idx]).convert("RGBA")
            img = img.resize((content_size, content_size), Image.LANCZOS)
            img_scale = compute_scale(
                reveal_elapsed, 0.0, config.EASE_REVEAL, "elastic_out"
            )
            frame = _composite_image_on_frame(
                frame, img, content_center_x, content_center_y, scale=img_scale
            )

        # Rainbow answer text
        answer_scale = compute_scale(
            reveal_elapsed, 0.1, config.EASE_ANSWER_IN, "back_out"
        )
        if answer_scale > 0.01:
            ans_font = int(config.ANSWER_FONT_SIZE * max(0.1, answer_scale))
            frame = render_rainbow_text(
                frame, f"It's a {round_data.answer}!",
                position=(w // 2, int(h * 0.68)),
                font_size=ans_font, t=t
            )

        # Confetti bursts
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)

        # Screen shake on reveal
        reveal_trigger = round_start + (timing["reveal_start"] - timing["silhouette_start"])
        frame = ScreenShake.apply(frame, t, reveal_trigger,
                                   duration=config.SHAKE_DURATION,
                                   intensity=config.SHAKE_INTENSITY)

    # ---------------------------------------------------------------
    # FUN FACT PHASE — keep image + answer, add fact below
    # ---------------------------------------------------------------
    if phase == "fun_fact":
        # Keep reveal image visible
        if round_idx < len(ctx.image_paths):
            img = Image.open(ctx.image_paths[round_idx]).convert("RGBA")
            img = img.resize((content_size, content_size), Image.LANCZOS)
            frame = _composite_image_on_frame(
                frame, img, content_center_x, content_center_y
            )

        # Answer text stays visible
        frame = render_text(frame, f"It's a {round_data.answer}!",
                            position=(w // 2, int(h * 0.66)),
                            font_size=config.ANSWER_FONT_SIZE,
                            color=primary_rgb,
                            stroke_color=(255, 255, 255))

        # Fun fact fades in with pill background
        fact_elapsed = elapsed_in_round - (timing["fun_fact_start"] - timing["silhouette_start"])
        fact_opacity = compute_opacity(fact_elapsed, 0.0, 0.3, "quad_out")
        if fact_opacity > 0.01:
            fact_y = int(h * 0.80)
            frame = render_pill_background(
                frame, round_data.fun_fact,
                (w // 2, fact_y), config.FACT_FONT_SIZE,
                bg_opacity=int(170 * fact_opacity)
            )
            frame = render_text_wrapped(frame, round_data.fun_fact,
                                         position=(w // 2, fact_y),
                                         font_size=config.FACT_FONT_SIZE,
                                         stroke_width=0, shadow=False)

        # Confetti continues during fun fact
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)

    # ---------------------------------------------------------------
    # PERSISTENT LAYER: Leo mascot — right side in landscape
    # ---------------------------------------------------------------
    mascot_pose = "thinking" if (phase in ("silhouette",) or phase.startswith("countdown_")) else "excited"
    if mascot_pose in ctx.mascot_images:
        mascot = ctx.mascot_images[mascot_pose]
        mascot_h = int(h * 0.18)
        mascot_w = int(mascot.width * (mascot_h / mascot.height))
        mascot_resized = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)

        # Right side positioning for landscape layout
        bounce_y = compute_bounce_y(t, amplitude=4.0, period=1.0)
        mascot_x = w - mascot_w // 2 - 60
        mascot_y = h - mascot_h // 2 - 50 + int(bounce_y)

        # Scale pulse on reveal
        m_scale = 1.0
        if phase == "reveal":
            reveal_elapsed = elapsed_in_round - (timing["reveal_start"] - timing["silhouette_start"])
            if reveal_elapsed < 0.4:
                m_scale = 1.0 + 0.15 * compute_scale(
                    reveal_elapsed, 0.0, 0.4, "back_out"
                )

        frame = _composite_image_on_frame(
            frame, mascot_resized, mascot_x, mascot_y, scale=m_scale
        )

    # ---------------------------------------------------------------
    # POST-PROCESSING: Vignette + Ken Burns + transitions
    # ---------------------------------------------------------------
    frame = apply_vignette(frame, config.VIGNETTE_INTENSITY)

    # Ken Burns zoom during silhouette phase
    if phase == "silhouette":
        frame = KenBurnsZoom.apply(frame, t, round_start,
                                    timing["countdown_start"] + timing["silhouette_start"],
                                    config.ZOOM_MAX)

    # Smooth transition at end of round (last 0.3s)
    transition_start = round_start + timing["transition_start"]
    if t >= transition_start and phase == "fun_fact":
        trans_progress = (t - transition_start) / 0.3
        trans_progress = min(1.0, max(0.0, trans_progress))
        if trans_progress > 0.01:
            zoom_out = 1.0 + 0.08 * trans_progress
            frame = KenBurnsZoom.apply(frame, trans_progress, 0, 1.0, zoom_out)
            arr = np.array(frame).astype(np.float32)
            arr *= (1.0 - 0.4 * trans_progress)
            frame = Image.fromarray(arr.astype(np.uint8))

    return np.array(frame.convert("RGB"))


def assemble_longform(quiz_pack: QuizPack, image_paths: list[Path],
                       silhouette_paths: list[Path],
                       round_audios: list[RoundAudio],
                       audio_path: Path, output_path: Path,
                       format_type: str = "long",
                       mascot_dir: Path = None) -> Path:
    """# Assemble a complete long-form quiz video (16:9 landscape).
    # Mirrors assemble_short() but for 1920×1080 layout.
    # format_type: "long" for daily 10-min, "mega" for weekly 15-min."""
    from moviepy import VideoClip, AudioFileClip

    w, h = config.LONGFORM_SIZE
    num_rounds = len(quiz_pack.rounds)
    timing = _get_timing(format_type)

    # Load mascot images
    mascot_images = {}
    if mascot_dir is None:
        mascot_dir = config.MASCOT_DIR
    for pose_name, pose_path in config.MASCOT_POSES.items():
        if pose_path.exists():
            mascot_images[pose_name] = Image.open(pose_path).convert("RGBA")

    # Build complete timeline with milestone cards
    timeline = build_longform_timeline(num_rounds, timing["round_duration"], format_type)
    total_duration = timeline[-1]["end"]

    # Create particle system (more particles for wider landscape)
    particles = ParticleSystem(w, h, count=config.PARTICLE_COUNT + 10)

    # Create themed decorations
    decorations = ThemedDecorations(quiz_pack.category, w, h)

    # Pre-create confetti bursts for each reveal + milestones + outro
    confetti_bursts = []
    for event in timeline:
        if event["phase"] == "reveal" or event["phase"] == "milestone":
            burst = ConfettiBurst(
                center_x=w // 2, center_y=int(h * 0.35),
                trigger_time=event["start"],
                count=config.CONFETTI_COUNT,
                seed=int(event["start"] * 100)
            )
            confetti_bursts.append(burst)

    # Outro confetti
    outro_events = [e for e in timeline if e["phase"] == "outro"]
    if outro_events:
        confetti_bursts.append(ConfettiBurst(
            center_x=w // 2, center_y=int(h * 0.30),
            trigger_time=outro_events[0]["start"] + 0.3,
            count=80, seed=999
        ))

    # Build video context
    ctx = LongformContext(
        width=w, height=h,
        category=quiz_pack.category,
        rounds=quiz_pack.rounds,
        image_paths=image_paths,
        silhouette_paths=silhouette_paths,
        mascot_images=mascot_images,
        particle_system=particles,
        themed_decorations=decorations,
        format_type=format_type,
        total_rounds=num_rounds,
        confetti_bursts=confetti_bursts,
        round_audios=round_audios,
        timeline=timeline,
    )

    # Create video clip with frame-by-frame rendering
    video = VideoClip(lambda t: render_longform_frame(t, ctx), duration=total_duration)
    video = video.with_fps(config.FPS)

    # Attach mixed audio track
    if audio_path and audio_path.exists():
        audio = AudioFileClip(str(audio_path))
        video = video.with_audio(audio)

    # Export — higher bitrate for landscape
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(output_path),
        codec="libx264",
        bitrate=config.LONGFORM_BITRATE,
        preset="slow",
        audio_codec="aac",
        audio_bitrate=config.AUDIO_BITRATE,
    )

    return output_path
