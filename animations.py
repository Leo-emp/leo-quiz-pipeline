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
    # UPGRADED: 4-point star shapes, multiple warm colors, larger size range,
    # individual rotation, and a central bright core for each sparkle.
    # Creates the "premium animation" feel seen in top kids content.
    """

    # Sparkle color palette — warm golds, whites, and soft pastels
    SPARKLE_COLORS = [
        np.array([255, 250, 220], dtype=np.float32),  # Warm white
        np.array([255, 230, 150], dtype=np.float32),  # Gold
        np.array([255, 200, 200], dtype=np.float32),  # Soft pink
        np.array([200, 230, 255], dtype=np.float32),  # Ice blue
        np.array([220, 255, 220], dtype=np.float32),  # Mint
    ]

    def __init__(self, width: int, height: int, count: int = 30, seed: int = 42):
        rng = random.Random(seed)
        self.width = width
        self.height = height

        # Generate particle properties with more variety
        self.particles = []
        for _ in range(count):
            self.particles.append({
                "x": rng.uniform(0, width),
                "y": rng.uniform(0, height),
                "size": rng.randint(2, 8),          # Wider size range
                "opacity": rng.uniform(0.15, 0.55),
                "speed_x": rng.uniform(-12, 12),
                "speed_y": rng.uniform(-18, -3),     # Upward drift
                "phase": rng.uniform(0, 2 * math.pi),
                "twinkle_speed": rng.uniform(2.0, 5.0),  # Individual twinkle rate
                "color_idx": rng.randint(0, len(self.SPARKLE_COLORS) - 1),
                "is_star": rng.random() > 0.4,       # 60% are star-shaped
            })

    def render(self, frame: np.ndarray, t: float) -> np.ndarray:
        """
        # Composite sparkle particles onto the frame at time t.
        # UPGRADED: renders 4-point star shapes with bright core,
        # using multiple colors and individual twinkle rates.
        """
        result = frame.copy()

        for p in self.particles:
            x = int((p["x"] + p["speed_x"] * t) % self.width)
            y = int((p["y"] + p["speed_y"] * t) % self.height)
            size = p["size"]

            # Individual twinkle rate — each sparkle blinks independently
            twinkle = 0.5 + 0.5 * math.sin(t * p["twinkle_speed"] + p["phase"])
            opacity = p["opacity"] * twinkle
            if opacity < 0.02:
                continue

            color = self.SPARKLE_COLORS[p["color_idx"]]

            if p["is_star"] and size >= 3:
                # Draw 4-point star: horizontal + vertical cross
                # Vertical arm
                for dy in range(-size, size + 1):
                    py = y + dy
                    if 0 <= py < self.height and 0 <= x < self.width:
                        # Brightness falls off toward tips
                        arm_opacity = opacity * (1 - abs(dy) / size)
                        pixel = result[py, x].astype(np.float32)
                        result[py, x] = (pixel * (1 - arm_opacity) + color * arm_opacity).astype(np.uint8)
                # Horizontal arm
                for dx in range(-size, size + 1):
                    px = x + dx
                    if 0 <= y < self.height and 0 <= px < self.width:
                        arm_opacity = opacity * (1 - abs(dx) / size)
                        pixel = result[y, px].astype(np.float32)
                        result[y, px] = (pixel * (1 - arm_opacity) + color * arm_opacity).astype(np.uint8)
                # Bright core (2x2 center)
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        py, px = y + dy, x + dx
                        if 0 <= py < self.height and 0 <= px < self.width:
                            core_opacity = min(1.0, opacity * 1.5)
                            pixel = result[py, px].astype(np.float32)
                            result[py, px] = (pixel * (1 - core_opacity) + color * core_opacity).astype(np.uint8)
            else:
                # Simple dot sparkle (original style for smaller particles)
                y1 = max(0, y - size)
                y2 = min(self.height, y + size)
                x1 = max(0, x - size)
                x2 = min(self.width, x + size)
                if y2 > y1 and x2 > x1:
                    region = result[y1:y2, x1:x2].astype(np.float32)
                    sparkle = np.full_like(region, color, dtype=np.float32)
                    blended = region * (1 - opacity) + sparkle * opacity
                    result[y1:y2, x1:x2] = blended.astype(np.uint8)

        return result
