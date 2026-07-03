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
from PIL import Image, ImageDraw

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
    width: int               # Frame width in pixels
    height: int              # Frame height in pixels
    category: str            # Quiz category for colors/labels
    rounds: list[QuizRound]  # All quiz round data
    image_paths: list[Path]  # Paths to full-color images
    silhouette_paths: list[Path]  # Paths to silhouette images
    mascot_images: dict      # {"thinking": Image, "excited": Image, ...}
    particle_system: ParticleSystem  # Sparkle overlay system
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
        # Silhouette slides in, question text appears
        {"phase": "silhouette", "start": t + config.SILHOUETTE_START,
         "end": t + config.COUNTDOWN_START, "round": round_index},
        # 3-2-1 countdown with pop-in numbers
        {"phase": "countdown_3", "start": t + config.COUNTDOWN_START,
         "end": t + config.COUNTDOWN_START + 1.0, "round": round_index, "number": 3},
        {"phase": "countdown_2", "start": t + config.COUNTDOWN_START + 1.0,
         "end": t + config.COUNTDOWN_START + 2.0, "round": round_index, "number": 2},
        {"phase": "countdown_1", "start": t + config.COUNTDOWN_START + 2.0,
         "end": t + config.REVEAL_START, "round": round_index, "number": 1},
        # Answer reveal with elastic pop animation
        {"phase": "reveal", "start": t + config.REVEAL_START,
         "end": t + config.FUN_FACT_START, "round": round_index},
        # Fun fact text appears
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
    # Default to last event if past end
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

    # Scale the overlay image
    new_w = max(1, int(overlay.width * scale))
    new_h = max(1, int(overlay.height * scale))
    scaled = overlay.resize((new_w, new_h), Image.LANCZOS)

    # Apply opacity by modifying alpha channel
    if opacity < 1.0:
        arr = np.array(scaled)
        arr[:, :, 3] = (arr[:, :, 3] * opacity).astype(np.uint8)
        scaled = Image.fromarray(arr)

    # Calculate paste position (centered on given coordinates)
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
    # All animation is computed from easing functions — no keyframes.
    """
    w, h = ctx.width, ctx.height

    # --- Layer 1: Background gradient + particle overlay ---
    bg = render_gradient_background(w, h, ctx.category, t)
    frame = bg.convert("RGBA")

    # Add floating sparkle particles for premium depth
    if ctx.particle_system:
        frame_arr = np.array(frame)[:, :, :3]
        frame_arr = ctx.particle_system.render(frame_arr, t)
        alpha = np.array(frame)[:, :, 3:]
        frame = Image.fromarray(
            np.concatenate([frame_arr, alpha], axis=2)
        )

    # Find current timeline event for this frame
    event = _get_current_event(t, ctx.timeline)
    phase = event["phase"]
    round_idx = event["round"]

    # --- Intro: title + mascot waving in ---
    if phase == "intro":
        cat_display = config.CATEGORIES[ctx.category]["display"]
        frame = render_text(frame, f"GUESS THE {cat_display.upper()}!",
                            position=(w // 2, int(h * 0.35)),
                            font_size=config.TITLE_FONT_SIZE + 20,
                            color=(255, 255, 255))
        # Mascot waves in with BackEaseOut pop
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

    # --- Outro: score recap + subscribe CTA ---
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
    score = round_idx  # Score = how many rounds already revealed
    total = len(ctx.rounds)
    round_start = config.INTRO_DURATION + round_idx * config.ROUND_DURATION
    elapsed_in_round = t - round_start

    # Persistent UI: score counter at bottom
    frame = render_text(frame, f"Score: {score}/{total}",
                        position=(w // 2, int(h * 0.90)),
                        font_size=config.SCORE_FONT_SIZE)

    # Persistent UI: title bar at top
    cat_display = config.CATEGORIES[ctx.category]["display"]
    colors = config.CATEGORY_COLORS[ctx.category]
    frame = render_text(frame, f"GUESS THE {cat_display.upper()}",
                        position=(w // 2, int(h * 0.06)),
                        font_size=config.TITLE_FONT_SIZE,
                        color=hex_to_rgb(colors["primary"]))

    # Content area dimensions
    content_size = int(w * 0.5)
    content_center_x = w // 2
    content_center_y = int(h * 0.35)

    # --- Silhouette + countdown phases ---
    if phase in ("silhouette", "countdown_3", "countdown_2", "countdown_1"):
        # Show silhouette with slide-in animation from left
        if round_idx < len(ctx.silhouette_paths):
            sil = Image.open(ctx.silhouette_paths[round_idx]).convert("RGBA")
            sil = sil.resize((content_size, content_size), Image.LANCZOS)

            # CubicEaseOut slide from off-screen to center
            slide_progress = compute_scale(
                elapsed_in_round, 0.0, config.EASE_SLIDE_IN, "cubic_out"
            )
            sil_x = int(-content_size + (content_center_x + content_size) * slide_progress)
            frame = _composite_image_on_frame(frame, sil, sil_x, content_center_y)

        # Question hint text fades in
        q_opacity = compute_opacity(
            elapsed_in_round, 0.2, config.EASE_TEXT_IN, "quad_out"
        )
        if q_opacity > 0.01:
            frame = render_text(frame, round_data.hint_question,
                                position=(w // 2, int(h * 0.62)),
                                font_size=config.QUESTION_FONT_SIZE)

    # --- Countdown number pop ---
    if phase.startswith("countdown_"):
        number = event.get("number", 3)
        countdown_elapsed = t - event["start"]
        # BackEaseOut pop — number bounces in from small to large
        num_scale = compute_scale(
            countdown_elapsed, 0.0, config.EASE_COUNTDOWN_IN, "back_out"
        )
        scaled_font_size = int(config.COUNTDOWN_FONT_SIZE * max(0.1, num_scale))
        frame = render_text(frame, str(number),
                            position=(w // 2, int(h * 0.55)),
                            font_size=scaled_font_size,
                            color=(255, 255, 255),
                            stroke_color=hex_to_rgb(colors["primary"]),
                            stroke_width=6)

    # --- Reveal phase: show answer ---
    if phase == "reveal":
        if round_idx < len(ctx.image_paths):
            img = Image.open(ctx.image_paths[round_idx]).convert("RGBA")
            img = img.resize((content_size, content_size), Image.LANCZOS)
            # ElasticEaseOut pop — image bounces in dramatically
            reveal_elapsed = elapsed_in_round - config.REVEAL_START
            img_scale = compute_scale(
                reveal_elapsed, 0.0, config.EASE_REVEAL, "elastic_out"
            )
            frame = _composite_image_on_frame(
                frame, img, content_center_x, content_center_y, scale=img_scale
            )

        # Answer text pops in with BackEaseOut
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

    # --- Fun fact phase ---
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
                            position=(w // 2, int(h * 0.62)),
                            font_size=config.ANSWER_FONT_SIZE,
                            color=hex_to_rgb(colors["primary"]),
                            stroke_color=(255, 255, 255))

        # Fun fact fades in with pill background
        fact_elapsed = elapsed_in_round - config.FUN_FACT_START
        fact_opacity = compute_opacity(fact_elapsed, 0.0, 0.3, "quad_out")
        if fact_opacity > 0.01:
            fact_y = int(h * 0.74)
            # Semi-transparent rounded rectangle behind fact text
            pill_layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
            pill_draw = ImageDraw.Draw(pill_layer)
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
    # Thinking pose during question, excited pose during reveal/fact
    mascot_pose = "thinking" if phase in ("silhouette", "countdown_3", "countdown_2", "countdown_1") else "excited"
    if mascot_pose in ctx.mascot_images:
        mascot = ctx.mascot_images[mascot_pose]
        mascot_h = int(h * 0.12)
        mascot_w = int(mascot.width * (mascot_h / mascot.height))
        mascot_resized = mascot.resize((mascot_w, mascot_h), Image.LANCZOS)

        # Idle bounce — gentle up/down bobbing
        bounce_y = compute_bounce_y(t, amplitude=3.0, period=1.2)
        mascot_x = w - mascot_w // 2 - 40
        mascot_y = h - mascot_h // 2 - 40 + int(bounce_y)

        # Scale pulse on reveal moment
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
    # MoviePy calls render_frame() 30 times per second.
    """
    from moviepy import VideoClip, AudioFileClip

    w, h = config.SHORTS_SIZE
    num_rounds = len(quiz_pack.rounds)
    # Total duration: intro + all rounds + outro
    total_duration = config.INTRO_DURATION + num_rounds * config.ROUND_DURATION + config.OUTRO_DURATION

    # Load mascot images (pre-generated PNG poses)
    mascot_images = {}
    if mascot_dir is None:
        mascot_dir = config.MASCOT_DIR
    for pose_name, pose_path in config.MASCOT_POSES.items():
        if pose_path.exists():
            mascot_images[pose_name] = Image.open(pose_path).convert("RGBA")

    # Build complete timeline of all events
    timeline = build_full_timeline(num_rounds)

    # Create particle system for sparkle overlay
    particles = ParticleSystem(w, h, count=config.PARTICLE_COUNT)

    # Build video context — everything the renderer needs
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
