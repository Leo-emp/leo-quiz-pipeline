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
# Maps string names to easing classes for flexible usage throughout pipeline
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
    # Clamp t to valid range — before start returns start, after end returns end
    if t <= 0.0:
        return start
    if t >= duration:
        return end

    # Look up the easing class, default to linear if unknown
    easing_class = EASING_MAP.get(easing_type, LinearInOut)
    # Create easing function instance with start/end/duration
    easing_fn = easing_class(start=start, end=end, duration=duration)
    # Evaluate the easing function at time t
    return easing_fn(t)


def compute_scale(t: float, start_time: float, duration: float,
                  easing_type: str = "cubic_out") -> float:
    """
    # Compute a scale factor from 0.0 to 1.0 with easing.
    # Used for pop-in effects on images, countdown numbers, etc.
    # t: global time, start_time: when this animation begins
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

    # Ease from off-screen position to center
    x = ease_value("cubic_out", elapsed, duration, float(start_x), float(center))
    return int(x)


def compute_bounce_y(t: float, amplitude: float = 3.0,
                     period: float = 1.2) -> float:
    """
    # Compute vertical offset for idle bounce animation (Leo mascot).
    # Returns a value between -amplitude and +amplitude using sine wave.
    # period: full cycle duration in seconds.
    """
    # Sine wave creates smooth up/down bobbing motion
    phase = (t % period) / period  # Normalize to [0, 1]
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

        # Generate particle properties — each has position, size, opacity, drift speed
        self.particles = []
        for _ in range(count):
            self.particles.append({
                "x": rng.uniform(0, width),       # Initial X position
                "y": rng.uniform(0, height),      # Initial Y position
                "size": rng.randint(2, 6),         # Sparkle radius in pixels
                "opacity": rng.uniform(0.2, 0.6),  # Base opacity
                "speed_x": rng.uniform(-15, 15),   # Horizontal drift (px/sec)
                "speed_y": rng.uniform(-20, -5),    # Vertical drift (upward)
                "phase": rng.uniform(0, 2 * math.pi),  # Twinkle phase offset
            })

    def render(self, frame: np.ndarray, t: float) -> np.ndarray:
        """
        # Composite sparkle particles onto the frame at time t.
        # Particles drift and twinkle (opacity oscillates with sine wave).
        # Returns the modified frame (copy, does not mutate input).
        """
        result = frame.copy()

        for p in self.particles:
            # Calculate current position (wraps around edges for infinite drift)
            x = int((p["x"] + p["speed_x"] * t) % self.width)
            y = int((p["y"] + p["speed_y"] * t) % self.height)
            size = p["size"]

            # Twinkle effect: oscillate opacity with sine wave
            twinkle = 0.5 + 0.5 * math.sin(t * 3.0 + p["phase"])
            opacity = p["opacity"] * twinkle

            # Sparkle color: warm white/gold for a magical feel
            color = np.array([255, 250, 220], dtype=np.float32)

            # Bounds checking — ensure we don't draw outside frame
            y1 = max(0, y - size)
            y2 = min(self.height, y + size)
            x1 = max(0, x - size)
            x2 = min(self.width, x + size)

            if y2 > y1 and x2 > x1:
                # Alpha-blend sparkle onto frame region
                region = result[y1:y2, x1:x2].astype(np.float32)
                sparkle = np.full_like(region, color, dtype=np.float32)
                blended = region * (1 - opacity) + sparkle * opacity
                result[y1:y2, x1:x2] = blended.astype(np.uint8)

        return result
