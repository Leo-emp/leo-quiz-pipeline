# video_assembler.py
# ============================================================
# Frame-by-frame video renderer for Leo Quiz.
# MASSIVELY UPGRADED from v1: now includes confetti bursts,
# screen shake, Ken Burns zoom, glow text, rainbow reveals,
# themed decorations, vignette, progress dots, and enhanced
# intro/outro sequences. Every frame is computed from easing
# functions — no pre-rendered keyframes.
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
class VideoContext:
    """# All data needed to render any frame of the video."""
    width: int               # Frame width in pixels
    height: int              # Frame height in pixels
    category: str            # Quiz category for colors/labels
    rounds: list[QuizRound]  # All quiz round data
    image_paths: list[Path]  # Paths to full-color images
    silhouette_paths: list[Path]  # Paths to silhouette images
    mascot_images: dict      # {"thinking": Image, "excited": Image, ...}
    particle_system: ParticleSystem  # Sparkle overlay system
    themed_decorations: ThemedDecorations  # Category-themed floating shapes
    confetti_bursts: list[ConfettiBurst] = field(default_factory=list)
    round_audios: list[RoundAudio] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)


def build_round_timeline(round_index: int, round_start: float) -> list[dict]:
    """
    # Build a list of timed events for one quiz round.
    # Each event has: phase, start, end, and round index.
    # Phases: silhouette → countdown_3 → countdown_2 → countdown_1 → reveal → fun_fact
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
    # Returns flat list of all timed events in order.
    """
    timeline = []

    # Intro phase — title card + mascot wave
    timeline.append({
        "phase": "intro",
        "start": 0.0,
        "end": config.INTRO_DURATION,
        "round": -1,
    })

    # All quiz rounds back-to-back
    for i in range(num_rounds):
        round_start = config.INTRO_DURATION + i * config.ROUND_DURATION
        timeline.extend(build_round_timeline(i, round_start))

    # Outro phase — score recap + subscribe CTA
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
    return timeline[-1] if timeline else {"phase": "intro", "start": 0, "end": 0, "round": -1}


def _composite_image_on_frame(frame_img: Image.Image, overlay: Image.Image,
                               center_x: int, center_y: int,
                               scale: float = 1.0, opacity: float = 1.0) -> Image.Image:
    """
    # Paste an RGBA image onto the frame at a given center position,
    # with scale and opacity applied. Used for silhouettes, reveals, mascot.
    """
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


def render_frame(t: float, ctx: VideoContext) -> np.ndarray:
    """
    # Render a single video frame at time t.
    # Called 30 times per second by MoviePy.
    # Returns a numpy array (H, W, 3) in RGB format.
    #
    # UPGRADED rendering pipeline:
    # 1. Gradient background with radial highlight
    # 2. Themed decorations (category-specific shapes)
    # 3. Sparkle particles
    # 4. Content (silhouette/reveal image)
    # 5. Glow ring around silhouette
    # 6. Text (glow countdown, rainbow answer, wrapped facts)
    # 7. Confetti burst on reveals
    # 8. Progress indicator dots
    # 9. Mascot with idle bounce
    # 10. Vignette overlay
    # 11. Screen shake (if active)
    # 12. Ken Burns zoom (if in silhouette phase)
    """
    w, h = ctx.width, ctx.height

    # --- Layer 1: Background gradient ---
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

    # ===================================================================
    # INTRO: animated title + mascot + particles burst
    # ===================================================================
    if phase == "intro":
        intro_elapsed = t - event["start"]
        intro_duration = event["end"] - event["start"]

        # Title text pops in with elastic bounce
        title_scale = compute_scale(intro_elapsed, 0.0, 0.6, "elastic_out")
        cat_display = config.CATEGORIES[ctx.category]["display"]
        title_text = f"GUESS THE {cat_display.upper()}!"
        title_size = int((config.TITLE_FONT_SIZE + 20) * max(0.1, title_scale))

        # Title with glow effect
        frame = render_glow_text(frame, title_text,
                                 position=(w // 2, int(h * 0.30)),
                                 font_size=title_size,
                                 glow_color=hex_to_rgb(
                                     config.CATEGORY_COLORS[ctx.category]["primary"]
                                 ))

        # Subtitle fades in after title
        sub_opacity = compute_opacity(intro_elapsed, 0.4, 0.4, "quad_out")
        if sub_opacity > 0.01:
            frame = render_text(frame, f"{len(ctx.rounds)} Rounds!",
                                position=(w // 2, int(h * 0.42)),
                                font_size=config.CTA_FONT_SIZE,
                                color=(255, 255, 200))

        # Mascot waves in with BackEaseOut pop from bottom
        if "waving" in ctx.mascot_images:
            mascot = ctx.mascot_images["waving"]
            mascot_scale = compute_scale(intro_elapsed, 0.2, 0.5, "back_out")
            mascot_h = int(h * 0.30)
            mascot_w = int(mascot.width * (mascot_h / mascot.height))
            mascot_resized = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
            # Slide up from below frame
            mascot_y = int(h * 0.65 + (1 - mascot_scale) * h * 0.3)
            frame = _composite_image_on_frame(
                frame, mascot_resized, w // 2, mascot_y, scale=min(1.0, mascot_scale)
            )

        # Apply vignette for cinematic depth
        frame = apply_vignette(frame, config.VIGNETTE_INTENSITY)
        return np.array(frame.convert("RGB"))

    # ===================================================================
    # OUTRO: score recap + subscribe CTA + mascot celebration
    # ===================================================================
    if phase == "outro":
        outro_elapsed = t - event["start"]

        # "How many did you get?" bounces in
        score_text_scale = compute_scale(outro_elapsed, 0.0, 0.5, "back_out")
        if score_text_scale > 0.01:
            frame = render_glow_text(frame, "How many did you get?",
                                     position=(w // 2, int(h * 0.25)),
                                     font_size=int(config.TITLE_FONT_SIZE * max(0.1, score_text_scale)),
                                     glow_color=(255, 200, 50))

        # Score display (big number)
        score_display = f"{len(ctx.rounds)}/{len(ctx.rounds)}"
        score_scale = compute_scale(outro_elapsed, 0.3, 0.5, "elastic_out")
        if score_scale > 0.01:
            frame = render_glow_text(frame, score_display,
                                     position=(w // 2, int(h * 0.40)),
                                     font_size=int(100 * max(0.1, score_scale)),
                                     glow_color=(50, 255, 100))

        # Subscribe CTA fades in
        cta_opacity = compute_opacity(outro_elapsed, 1.0, 0.5, "quad_out")
        if cta_opacity > 0.01:
            frame = render_text(frame, "SUBSCRIBE for more quizzes!",
                                position=(w // 2, int(h * 0.58)),
                                font_size=config.CTA_FONT_SIZE,
                                color=(255, 255, 100))
            # Like + Comment reminder
            frame = render_text(frame, "Like & Comment your score!",
                                position=(w // 2, int(h * 0.66)),
                                font_size=config.ROUND_LABEL_FONT_SIZE,
                                color=(255, 255, 255))

        # Mascot celebration with bounce
        if "excited" in ctx.mascot_images:
            mascot = ctx.mascot_images["excited"]
            mascot_h = int(h * 0.25)
            mascot_w = int(mascot.width * (mascot_h / mascot.height))
            mascot_resized = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)
            bounce = compute_bounce_y(t, amplitude=8.0, period=0.6)
            frame = _composite_image_on_frame(
                frame, mascot_resized, w // 2, int(h * 0.82) + int(bounce)
            )

        # Confetti during outro
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)

        frame = apply_vignette(frame, config.VIGNETTE_INTENSITY)
        return np.array(frame.convert("RGB"))

    # ===================================================================
    # QUIZ ROUND PHASES
    # ===================================================================
    if round_idx < 0 or round_idx >= len(ctx.rounds):
        return np.array(frame.convert("RGB"))

    round_data = ctx.rounds[round_idx]
    score = round_idx  # Score = completed rounds
    total = len(ctx.rounds)
    round_start = config.INTRO_DURATION + round_idx * config.ROUND_DURATION
    elapsed_in_round = t - round_start

    # Get category colors
    cat_display = config.CATEGORIES[ctx.category]["display"]
    colors = config.CATEGORY_COLORS[ctx.category]
    primary_rgb = hex_to_rgb(colors["primary"])

    # --- Persistent UI: Title bar at top ---
    frame = render_text(frame, f"GUESS THE {cat_display.upper()}",
                        position=(w // 2, int(h * 0.06)),
                        font_size=config.TITLE_FONT_SIZE,
                        color=primary_rgb)

    # --- Persistent UI: Round label below title ---
    frame = render_text(frame, f"Round {round_idx + 1}/{total}",
                        position=(w // 2, int(h * 0.12)),
                        font_size=config.ROUND_LABEL_FONT_SIZE,
                        color=(255, 255, 255), stroke_width=2)

    # Content area dimensions
    content_size = int(w * 0.5)
    content_center_x = w // 2
    content_center_y = int(h * 0.35)

    # ---------------------------------------------------------------
    # SILHOUETTE + COUNTDOWN PHASES
    # ---------------------------------------------------------------
    if phase in ("silhouette", "countdown_3", "countdown_2", "countdown_1"):
        # Glow ring behind silhouette — pulsing category-colored circle
        frame = GlowRing.render(frame, content_center_x, content_center_y,
                                int(content_size * 0.6), primary_rgb, t)

        # Show silhouette with slide-in animation
        if round_idx < len(ctx.silhouette_paths):
            sil = Image.open(ctx.silhouette_paths[round_idx]).convert("RGBA")
            sil = sil.resize((content_size, content_size), Image.LANCZOS)

            # CubicEaseOut slide from off-screen to center
            slide_progress = compute_scale(
                elapsed_in_round, 0.0, config.EASE_SLIDE_IN, "cubic_out"
            )
            sil_x = int(-content_size + (content_center_x + content_size) * slide_progress)
            frame = _composite_image_on_frame(frame, sil, sil_x, content_center_y)

        # Question hint text fades in (word-wrapped for long questions)
        q_opacity = compute_opacity(
            elapsed_in_round, 0.2, config.EASE_TEXT_IN, "quad_out"
        )
        if q_opacity > 0.01:
            # Pill background behind question text
            frame = render_pill_background(
                frame, round_data.hint_question,
                (w // 2, int(h * 0.62)), config.QUESTION_FONT_SIZE,
                bg_opacity=120
            )
            frame = render_text_wrapped(frame, round_data.hint_question,
                                        position=(w // 2, int(h * 0.62)),
                                        font_size=config.QUESTION_FONT_SIZE)

    # ---------------------------------------------------------------
    # TIMER BAR — animated countdown bar below the title
    # ---------------------------------------------------------------
    if phase in ("silhouette", "countdown_3", "countdown_2", "countdown_1"):
        # Progress from 0 (bar full) to 1 (bar empty) over the entire guess phase
        guess_start = round_start + config.SILHOUETTE_START
        guess_end = round_start + config.REVEAL_START
        guess_progress = (t - guess_start) / (guess_end - guess_start)
        frame = CountdownBar.render(frame, guess_progress, primary_rgb)

    # ---------------------------------------------------------------
    # COUNTDOWN NUMBER POP — with GLOW effect
    # ---------------------------------------------------------------
    if phase.startswith("countdown_"):
        number = event.get("number", 3)
        countdown_elapsed = t - event["start"]
        # BackEaseOut pop — number bounces in from small to large
        num_scale = compute_scale(
            countdown_elapsed, 0.0, config.EASE_COUNTDOWN_IN, "back_out"
        )
        scaled_font_size = int(config.COUNTDOWN_FONT_SIZE * max(0.1, num_scale))

        # Glow text for countdown numbers — bright and dramatic
        glow_color = primary_rgb
        if number == 1:
            glow_color = (255, 50, 50)  # Red glow on "1" for tension

        frame = render_glow_text(frame, str(number),
                                 position=(w // 2, int(h * 0.55)),
                                 font_size=scaled_font_size,
                                 glow_color=glow_color,
                                 glow_radius=config.GLOW_RADIUS)

        # Screen shake on countdown "1" — builds tension
        if number == 1 and countdown_elapsed > 0.3:
            frame = ScreenShake.apply(frame, t, event["start"] + 0.3,
                                       duration=0.2, intensity=6.0)

    # ---------------------------------------------------------------
    # REVEAL PHASE — answer with rainbow text + confetti
    # ---------------------------------------------------------------
    if phase == "reveal":
        reveal_elapsed = elapsed_in_round - config.REVEAL_START

        # Full color image pops in with ElasticEaseOut
        if round_idx < len(ctx.image_paths):
            img = Image.open(ctx.image_paths[round_idx]).convert("RGBA")
            img = img.resize((content_size, content_size), Image.LANCZOS)
            img_scale = compute_scale(
                reveal_elapsed, 0.0, config.EASE_REVEAL, "elastic_out"
            )
            frame = _composite_image_on_frame(
                frame, img, content_center_x, content_center_y, scale=img_scale
            )

        # Answer text — rainbow gradient for excitement
        answer_scale = compute_scale(
            reveal_elapsed, 0.1, config.EASE_ANSWER_IN, "back_out"
        )
        if answer_scale > 0.01:
            ans_font = int(config.ANSWER_FONT_SIZE * max(0.1, answer_scale))
            frame = render_rainbow_text(
                frame, f"It's a {round_data.answer}!",
                position=(w // 2, int(h * 0.62)),
                font_size=ans_font, t=t
            )

        # Confetti burst — all bursts render if active
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)

        # Screen shake on reveal — dramatic camera effect
        frame = ScreenShake.apply(frame, t,
                                   round_start + config.REVEAL_START,
                                   duration=config.SHAKE_DURATION,
                                   intensity=config.SHAKE_INTENSITY)

    # ---------------------------------------------------------------
    # FUN FACT PHASE — keep image + answer, add fact
    # ---------------------------------------------------------------
    if phase == "fun_fact":
        # Keep reveal image visible (no animation — static)
        if round_idx < len(ctx.image_paths):
            img = Image.open(ctx.image_paths[round_idx]).convert("RGBA")
            img = img.resize((content_size, content_size), Image.LANCZOS)
            frame = _composite_image_on_frame(
                frame, img, content_center_x, content_center_y
            )

        # Answer text stays visible
        frame = render_text(frame, f"It's a {round_data.answer}!",
                            position=(w // 2, int(h * 0.60)),
                            font_size=config.ANSWER_FONT_SIZE,
                            color=primary_rgb,
                            stroke_color=(255, 255, 255))

        # Fun fact fades in — word-wrapped with pill background
        fact_elapsed = elapsed_in_round - config.FUN_FACT_START
        fact_opacity = compute_opacity(fact_elapsed, 0.0, 0.3, "quad_out")
        if fact_opacity > 0.01:
            fact_y = int(h * 0.74)
            # Pill background for readability
            frame = render_pill_background(
                frame, round_data.fun_fact,
                (w // 2, fact_y), config.FACT_FONT_SIZE,
                bg_opacity=int(170 * fact_opacity)
            )
            # Word-wrapped fact text
            frame = render_text_wrapped(frame, round_data.fun_fact,
                                        position=(w // 2, fact_y),
                                        font_size=config.FACT_FONT_SIZE,
                                        stroke_width=0, shadow=False)

        # Confetti continues during fun fact
        for burst in ctx.confetti_bursts:
            frame = burst.render(frame, t)

    # ---------------------------------------------------------------
    # PERSISTENT LAYER: Progress indicator dots
    # ---------------------------------------------------------------
    frame = ProgressIndicator.render(frame, round_idx, total, t,
                                     color=primary_rgb, y_position=0.94)

    # ---------------------------------------------------------------
    # PERSISTENT LAYER: Score counter
    # ---------------------------------------------------------------
    # Score updates with bounce on reveal
    displayed_score = score
    if phase in ("reveal", "fun_fact"):
        displayed_score = score + 1  # Show updated score after reveal

    score_y = int(h * 0.88)
    # Score pill background
    frame = render_pill_background(frame, f"Score: {displayed_score}/{total}",
                                   (w // 2, score_y), config.SCORE_FONT_SIZE,
                                   padding=15, bg_opacity=100)
    frame = render_text(frame, f"Score: {displayed_score}/{total}",
                        position=(w // 2, score_y),
                        font_size=config.SCORE_FONT_SIZE)

    # ---------------------------------------------------------------
    # PERSISTENT LAYER: Leo mascot with idle bounce + pose swap
    # ---------------------------------------------------------------
    mascot_pose = "thinking" if phase in ("silhouette", "countdown_3", "countdown_2", "countdown_1") else "excited"
    if mascot_pose in ctx.mascot_images:
        mascot = ctx.mascot_images[mascot_pose]
        mascot_h = int(h * 0.13)
        mascot_w = int(mascot.width * (mascot_h / mascot.height))
        mascot_resized = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)

        # Idle bounce — gentle bobbing
        bounce_y = compute_bounce_y(t, amplitude=4.0, period=1.0)
        mascot_x = w - mascot_w // 2 - 40
        mascot_y = h - mascot_h // 2 - 60 + int(bounce_y)

        # Scale pulse on reveal — mascot gets excited
        m_scale = 1.0
        if phase == "reveal":
            reveal_elapsed = elapsed_in_round - config.REVEAL_START
            if reveal_elapsed < 0.4:
                m_scale = 1.0 + 0.15 * compute_scale(
                    reveal_elapsed, 0.0, 0.4, "back_out"
                )

        frame = _composite_image_on_frame(
            frame, mascot_resized, mascot_x, mascot_y, scale=m_scale
        )

    # ---------------------------------------------------------------
    # POST-PROCESSING: Vignette + Ken Burns zoom + round transition
    # ---------------------------------------------------------------
    # Apply vignette for cinematic depth on all frames
    frame = apply_vignette(frame, config.VIGNETTE_INTENSITY)

    # Ken Burns zoom during silhouette phase — slow push-in
    if phase == "silhouette":
        frame = KenBurnsZoom.apply(frame, t, round_start,
                                    config.SILHOUETTE_DURATION + config.COUNTDOWN_START,
                                    config.ZOOM_MAX)

    # Smooth zoom-out transition at end of round (last 0.3s)
    # Creates a subtle scale-down that blends into next round's slide-in
    transition_start = round_start + config.TRANSITION_START
    if t >= transition_start and phase == "fun_fact":
        trans_progress = (t - transition_start) / config.TRANSITION_DURATION
        trans_progress = min(1.0, max(0.0, trans_progress))
        if trans_progress > 0.01:
            # Scale down slightly + fade for crossfade feel
            zoom_out = 1.0 + 0.08 * trans_progress
            frame = KenBurnsZoom.apply(frame, trans_progress, 0, 1.0, zoom_out)
            # Fade to slightly darker (simulates dissolve)
            arr = np.array(frame).astype(np.float32)
            arr *= (1.0 - 0.4 * trans_progress)
            frame = Image.fromarray(arr.astype(np.uint8))

    return np.array(frame.convert("RGB"))


def assemble_short(quiz_pack: QuizPack, image_paths: list[Path],
                    silhouette_paths: list[Path],
                    round_audios: list[RoundAudio],
                    audio_path: Path, output_path: Path,
                    mascot_dir: Path = None) -> Path:
    """
    # Assemble a complete short-form quiz video (60s, 9:16).
    # UPGRADED: now creates confetti bursts, themed decorations,
    # and uses all premium visual effects automatically.
    """
    from moviepy import VideoClip, AudioFileClip

    w, h = config.SHORTS_SIZE
    num_rounds = len(quiz_pack.rounds)
    total_duration = config.INTRO_DURATION + num_rounds * config.ROUND_DURATION + config.OUTRO_DURATION

    # Load mascot images (pre-generated PNG poses)
    mascot_images = {}
    if mascot_dir is None:
        mascot_dir = config.MASCOT_DIR
    for pose_name, pose_path in config.MASCOT_POSES.items():
        if pose_path.exists():
            mascot_images[pose_name] = Image.open(pose_path).convert("RGBA")

    # Build complete timeline
    timeline = build_full_timeline(num_rounds)

    # Create particle system for sparkle overlay
    particles = ParticleSystem(w, h, count=config.PARTICLE_COUNT)

    # Create themed decorations based on quiz category
    decorations = ThemedDecorations(quiz_pack.category, w, h)

    # Pre-create confetti bursts for each reveal moment + outro
    confetti_bursts = []
    for i in range(num_rounds):
        reveal_time = config.INTRO_DURATION + i * config.ROUND_DURATION + config.REVEAL_START
        burst = ConfettiBurst(
            center_x=w // 2, center_y=int(h * 0.35),
            trigger_time=reveal_time,
            count=config.CONFETTI_COUNT,
            seed=i * 100  # Different pattern for each round
        )
        confetti_bursts.append(burst)

    # Outro confetti — extra celebration at the end
    outro_start = config.INTRO_DURATION + num_rounds * config.ROUND_DURATION
    confetti_bursts.append(ConfettiBurst(
        center_x=w // 2, center_y=int(h * 0.30),
        trigger_time=outro_start + 0.3,
        count=80, seed=999
    ))

    # Build video context with all effect systems
    ctx = VideoContext(
        width=w, height=h,
        category=quiz_pack.category,
        rounds=quiz_pack.rounds,
        image_paths=image_paths,
        silhouette_paths=silhouette_paths,
        mascot_images=mascot_images,
        particle_system=particles,
        themed_decorations=decorations,
        confetti_bursts=confetti_bursts,
        round_audios=round_audios,
        timeline=timeline,
    )

    # Create video clip with frame-by-frame rendering function
    video = VideoClip(lambda t: render_frame(t, ctx), duration=total_duration)
    video = video.with_fps(config.FPS)

    # Attach mixed audio track
    if audio_path and audio_path.exists():
        audio = AudioFileClip(str(audio_path))
        video = video.with_audio(audio)

    # Export final video — H.264 with AAC audio
    output_path.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(output_path),
        codec="libx264",
        bitrate=config.VIDEO_BITRATE,
        preset="slow",       # Slower = better compression quality
        audio_codec="aac",
        audio_bitrate=config.AUDIO_BITRATE,
    )

    return output_path
