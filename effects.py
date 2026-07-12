# effects.py
# ============================================================
# Premium visual effects for Leo Quiz videos.
# Confetti bursts, screen shake, Ken Burns zoom, glow rings,
# progress indicators, floating emojis, and themed decorations.
# All effects are rendered per-frame using PIL — no pre-renders.
# ============================================================
import math
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import numpy as np

import config


# ============================================================
# Confetti Burst — explodes colored particles on answer reveal
# ============================================================

class ConfettiBurst:
    """
    # Spawns colorful confetti particles that explode outward from center.
    # Each particle has: random color, angle, speed, size, rotation.
    # Gravity pulls particles downward over time for realistic arc.
    # Triggered at reveal moment — lasts ~1.5 seconds.
    """

    def __init__(self, center_x: int, center_y: int,
                 trigger_time: float, count: int = 60, seed: int = None):
        # Use seed for reproducible confetti (same burst each render pass)
        rng = random.Random(seed)
        self.trigger_time = trigger_time
        self.duration = 1.5          # Confetti visible for 1.5 seconds
        self.gravity = 800.0         # Pixels/sec² — pulls particles down

        # Bright kid-friendly confetti colors
        self.colors = [
            (255, 69, 58),    # Red
            (255, 214, 10),   # Yellow
            (48, 209, 88),    # Green
            (0, 122, 255),    # Blue
            (255, 55, 95),    # Pink
            (175, 82, 222),   # Purple
            (255, 159, 10),   # Orange
            (0, 199, 190),    # Teal
        ]

        # Generate particle properties — mix of shapes including ribbons
        self.particles = []
        for _ in range(count):
            angle = rng.uniform(0, 2 * math.pi)
            speed = rng.uniform(300, 900)
            self.particles.append({
                "x": center_x,
                "y": center_y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed * -0.8,
                "size": rng.randint(6, 14),
                "color": rng.choice(self.colors),
                "rotation": rng.uniform(0, 360),
                "rot_speed": rng.uniform(-500, 500),
                # More shape variety — ribbons tumble like real confetti
                "shape": rng.choice(["ribbon", "ribbon", "circle", "star", "rect"]),
                # Ribbon aspect ratio — tall and thin like real confetti strips
                "aspect": rng.uniform(2.0, 4.0),
                # Air resistance — ribbons flutter and slow down
                "drag": rng.uniform(0.6, 1.0),
            })

    def is_active(self, t: float) -> bool:
        """# Check if confetti should be rendered at time t."""
        elapsed = t - self.trigger_time
        return 0 <= elapsed <= self.duration

    def render(self, frame: Image.Image, t: float) -> Image.Image:
        """
        # Draw all confetti particles on the frame at time t.
        # Particles fly outward, spin, and fall with gravity.
        # Opacity fades as particles age for smooth disappearance.
        """
        if not self.is_active(t):
            return frame

        elapsed = t - self.trigger_time

        # Create transparent overlay for confetti
        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for p in self.particles:
            drag = p.get("drag", 1.0)
            px = int(p["x"] + p["vx"] * elapsed * drag)
            py = int(p["y"] + p["vy"] * elapsed * drag + 0.5 * self.gravity * elapsed ** 2)

            alpha = max(0, int(255 * (1 - elapsed / self.duration)))
            if alpha <= 0:
                continue
            if px < -50 or px > frame.width + 50 or py > frame.height + 50:
                continue

            size = p["size"]
            color = p["color"] + (alpha,)

            # Rotation angle changes over time
            rot = math.radians(p["rotation"] + p["rot_speed"] * elapsed)

            if p["shape"] == "ribbon":
                # Ribbon confetti — elongated rectangle that tumbles
                # Width narrows/widens based on rotation to simulate 3D tumble
                aspect = p.get("aspect", 3.0)
                ribbon_w = size
                ribbon_h = int(size * aspect)
                # 3D tumble: width oscillates as ribbon rotates
                tumble = abs(math.cos(rot))
                apparent_w = max(2, int(ribbon_w * (0.2 + 0.8 * tumble)))
                hw, hh = apparent_w // 2, ribbon_h // 2
                # Rotated corners
                cos_r = math.cos(rot * 0.3)
                sin_r = math.sin(rot * 0.3)
                corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
                rotated = [(int(px + x * cos_r - y * sin_r),
                            int(py + x * sin_r + y * cos_r))
                           for x, y in corners]
                draw.polygon(rotated, fill=color)
            elif p["shape"] == "rect":
                half = size // 2
                draw.rectangle([px - half, py - half, px + half, py + half],
                               fill=color)
            elif p["shape"] == "circle":
                draw.ellipse([px - size // 2, py - size // 2,
                              px + size // 2, py + size // 2],
                             fill=color)
            else:
                self._draw_star(draw, px, py, size, color)

        # Composite confetti onto frame
        if frame.mode != "RGBA":
            frame = frame.convert("RGBA")
        return Image.alpha_composite(frame, overlay)

    def _draw_star(self, draw: ImageDraw.Draw, cx: int, cy: int,
                   size: int, color: tuple):
        """# Draw a simple 4-point star at (cx, cy)."""
        s = size // 2
        # Diamond shape (rotated square = simple star)
        points = [
            (cx, cy - s),      # Top
            (cx + s // 2, cy), # Right
            (cx, cy + s),      # Bottom
            (cx - s // 2, cy), # Left
        ]
        draw.polygon(points, fill=color)


# ============================================================
# Screen Shake — camera shake on reveal and countdown "1"
# ============================================================

class ScreenShake:
    """
    # Simulates camera shake by offsetting the frame randomly.
    # The shake intensity decays exponentially for a natural feel.
    # Fills edges with the category background color to avoid black bars.
    """

    @staticmethod
    def apply(frame: Image.Image, t: float, trigger_time: float,
              duration: float = 0.3, intensity: float = 12.0,
              seed: int = None) -> Image.Image:
        """
        # Apply screen shake to a frame at time t.
        # Returns the shaken frame (new image, doesn't mutate input).
        # intensity: max pixel offset at start of shake.
        """
        elapsed = t - trigger_time
        # Only shake during the active window
        if elapsed < 0 or elapsed > duration:
            return frame

        # Exponential decay — shake reduces over time
        decay = math.exp(-6.0 * elapsed / duration)
        current_intensity = intensity * decay

        # Deterministic random offset for this specific frame time
        # Using frame time as seed ensures same shake on re-renders
        rng = random.Random(int(t * 1000) + (seed or 0))
        dx = int(rng.uniform(-current_intensity, current_intensity))
        dy = int(rng.uniform(-current_intensity, current_intensity))

        if dx == 0 and dy == 0:
            return frame

        # Create new frame with offset content
        w, h = frame.size
        shaken = Image.new(frame.mode, (w, h), (0, 0, 0, 0) if frame.mode == "RGBA" else (0, 0, 0))
        # Paste frame at offset position — edges get filled with black/transparent
        shaken.paste(frame, (dx, dy))

        return shaken


# ============================================================
# Ken Burns Zoom — slow zoom during silhouette phase
# ============================================================

class KenBurnsZoom:
    """
    # Applies a slow zoom effect (Ken Burns) to create visual movement.
    # Crops the frame slightly and upscales to original size.
    # Zoom increases linearly over the duration for smooth push-in.
    """

    @staticmethod
    def apply(frame: Image.Image, t: float, start_time: float,
              duration: float, max_zoom: float = 1.06) -> Image.Image:
        """
        # Apply Ken Burns zoom at time t.
        # max_zoom: maximum zoom level (1.06 = 6% zoom at end).
        # Crops center and upscales — no black bars.
        """
        elapsed = t - start_time
        if elapsed < 0 or duration <= 0:
            return frame

        # Progress from 0 to 1 over the duration
        progress = min(elapsed / duration, 1.0)
        # Zoom level ramps from 1.0 to max_zoom
        zoom = 1.0 + (max_zoom - 1.0) * progress

        if zoom <= 1.001:
            return frame

        w, h = frame.size
        # Calculate crop region (centered)
        crop_w = int(w / zoom)
        crop_h = int(h / zoom)
        left = (w - crop_w) // 2
        top = (h - crop_h) // 2

        # Crop center region and upscale back to original size
        cropped = frame.crop((left, top, left + crop_w, top + crop_h))
        return cropped.resize((w, h), Image.LANCZOS)


# ============================================================
# Glow Ring — pulsing glow around silhouette
# ============================================================

class GlowRing:
    """
    # Renders a pulsing semi-transparent glow circle behind content.
    # Uses category colors — makes silhouettes pop off the background.
    # Pulse speed creates a "breathing" effect that draws attention.
    """

    @staticmethod
    def render(frame: Image.Image, center_x: int, center_y: int,
               radius: int, color: tuple, t: float,
               pulse_speed: float = 2.0) -> Image.Image:
        """
        # Draw a pulsing glow ring on the frame.
        # Radius oscillates ±15% with sine wave.
        # Opacity oscillates between 20-50% for soft breathing effect.
        """
        # Pulse the radius and opacity with sine wave
        pulse = 0.5 + 0.5 * math.sin(t * pulse_speed * 2 * math.pi)
        current_radius = int(radius * (0.85 + 0.30 * pulse))
        current_opacity = int(50 + 80 * pulse)  # 50-130 alpha range

        # Create glow on transparent layer
        glow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)

        # Draw concentric circles for soft glow gradient (outer = more transparent)
        for ring in range(3):
            ring_radius = current_radius + ring * 15
            ring_opacity = max(10, current_opacity - ring * 35)
            ring_color = color + (ring_opacity,)
            glow_draw.ellipse([
                center_x - ring_radius, center_y - ring_radius,
                center_x + ring_radius, center_y + ring_radius,
            ], outline=ring_color, width=4)

        # Blur the glow for soft edges
        glow = glow.filter(ImageFilter.GaussianBlur(8))

        if frame.mode != "RGBA":
            frame = frame.convert("RGBA")
        return Image.alpha_composite(frame, glow)


# ============================================================
# Progress Indicator — shows round progress at bottom
# ============================================================

class ProgressIndicator:
    """
    # Renders a row of circles showing quiz progress.
    # Filled circles = completed rounds, outlined = remaining.
    # Current round gets a pulsing highlight animation.
    """

    @staticmethod
    def render(frame: Image.Image, current_round: int,
               total_rounds: int, t: float,
               color: tuple = (255, 255, 255),
               y_position: float = 0.94) -> Image.Image:
        """
        # Draw progress dots at the bottom of the frame.
        # current_round: 0-indexed current round (-1 for intro)
        """
        w, h = frame.size
        y = int(h * y_position)

        # Calculate spacing — dots centered horizontally
        dot_radius = 8
        dot_gap = 30
        total_width = total_rounds * dot_gap
        start_x = (w - total_width) // 2 + dot_gap // 2

        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for i in range(total_rounds):
            cx = start_x + i * dot_gap

            if i < current_round:
                # Completed round — filled circle with checkmark feel
                draw.ellipse([cx - dot_radius, y - dot_radius,
                              cx + dot_radius, y + dot_radius],
                             fill=color + (220,))
            elif i == current_round:
                # Current round — pulsing circle
                pulse = 0.5 + 0.5 * math.sin(t * 4)
                r = int(dot_radius * (1.0 + 0.3 * pulse))
                alpha = int(180 + 75 * pulse)
                draw.ellipse([cx - r, y - r, cx + r, y + r],
                             fill=color + (alpha,), outline=color + (255,), width=2)
            else:
                # Future round — outlined circle
                draw.ellipse([cx - dot_radius, y - dot_radius,
                              cx + dot_radius, y + dot_radius],
                             outline=color + (100,), width=2)

        if frame.mode != "RGBA":
            frame = frame.convert("RGBA")
        return Image.alpha_composite(frame, overlay)


# ============================================================
# Themed Decorations — category-specific floating elements
# ============================================================

class ThemedDecorations:
    """
    # Draws floating themed shapes in the background based on category.
    # Animals: leaf/pawprint shapes, Space: stars/planets,
    # Dinosaurs: volcanic rocks, etc.
    # Shapes drift slowly for visual depth — like a parallax layer.
    """

    def __init__(self, category: str, width: int, height: int, seed: int = 99):
        rng = random.Random(seed)
        self.width = width
        self.height = height
        self.category = category

        # Generate 8-12 floating decorative elements
        count = rng.randint(8, 12)
        self.elements = []
        for _ in range(count):
            self.elements.append({
                "x": rng.uniform(0, width),
                "y": rng.uniform(0, height),
                "size": rng.uniform(15, 40),
                "speed_x": rng.uniform(-8, 8),     # Slow horizontal drift
                "speed_y": rng.uniform(-5, 5),      # Slow vertical drift
                "opacity": rng.uniform(0.06, 0.15), # Very subtle — background layer
                "phase": rng.uniform(0, 2 * math.pi),
                "shape": self._pick_shape(category, rng),
            })

    def _pick_shape(self, category: str, rng: random.Random) -> str:
        """# Pick a themed shape type based on quiz category."""
        shapes = {
            "animals": ["circle", "diamond", "leaf"],
            "dinosaurs": ["triangle", "diamond", "circle"],
            "space": ["star", "circle", "diamond"],
            "vehicles": ["diamond", "triangle", "circle"],
            "fruits": ["circle", "star", "leaf"],
            "flags": ["star", "diamond", "triangle"],
        }
        return rng.choice(shapes.get(category, ["circle", "star"]))

    def render(self, frame: Image.Image, t: float) -> Image.Image:
        """
        # Draw floating themed decorations on the frame.
        # Elements drift slowly and pulse in opacity for depth.
        """
        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for elem in self.elements:
            # Position drifts over time (wraps around edges)
            x = int((elem["x"] + elem["speed_x"] * t) % self.width)
            y = int((elem["y"] + elem["speed_y"] * t) % self.height)
            size = int(elem["size"])

            # Subtle opacity pulse
            pulse = 0.5 + 0.5 * math.sin(t * 1.5 + elem["phase"])
            alpha = int(255 * elem["opacity"] * (0.5 + 0.5 * pulse))
            color = (255, 255, 255, alpha)

            # Draw the shape
            shape = elem["shape"]
            if shape == "circle":
                draw.ellipse([x - size, y - size, x + size, y + size],
                             outline=color, width=2)
            elif shape == "diamond":
                points = [(x, y - size), (x + size, y),
                          (x, y + size), (x - size, y)]
                draw.polygon(points, outline=color)
            elif shape == "triangle":
                points = [(x, y - size), (x + size, y + size),
                          (x - size, y + size)]
                draw.polygon(points, outline=color)
            elif shape == "star":
                self._draw_star_shape(draw, x, y, size, color)
            elif shape == "leaf":
                # Leaf = two overlapping ellipses
                draw.ellipse([x - size // 2, y - size, x + size // 2, y],
                             outline=color, width=2)

        if frame.mode != "RGBA":
            frame = frame.convert("RGBA")
        return Image.alpha_composite(frame, overlay)

    def _draw_star_shape(self, draw: ImageDraw.Draw,
                         cx: int, cy: int, size: int, color: tuple):
        """# Draw a 5-point star outline at (cx, cy)."""
        points = []
        for i in range(5):
            # Outer points
            angle = math.radians(i * 72 - 90)
            points.append((cx + int(size * math.cos(angle)),
                           cy + int(size * math.sin(angle))))
            # Inner points (at half radius)
            inner_angle = math.radians(i * 72 - 90 + 36)
            points.append((cx + int(size * 0.4 * math.cos(inner_angle)),
                           cy + int(size * 0.4 * math.sin(inner_angle))))
        draw.polygon(points, outline=color)


# ============================================================
# Countdown Timer Bar — animated urgency indicator
# ============================================================

class CountdownBar:
    """
    # Renders an animated countdown bar that shrinks over time.
    # Creates visual urgency during the guessing phase.
    # Bar starts full and empties as the countdown progresses,
    # with color shift from green → yellow → red at the end.
    """

    @staticmethod
    def render(frame: Image.Image, progress: float,
               color: tuple = (255, 255, 255),
               y_position: float = 0.175,
               bar_width_ratio: float = 0.75,
               bar_height: int = 12) -> Image.Image:
        """
        # Draw countdown bar on the frame.
        # progress: 0.0 = full bar (start), 1.0 = empty bar (time up)
        """
        progress = max(0.0, min(1.0, progress))
        w, h = frame.size

        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        bar_full_w = int(w * bar_width_ratio)
        bar_x = (w - bar_full_w) // 2
        bar_y = int(h * y_position)
        remaining = 1.0 - progress

        # Color shifts: green → yellow → red as time runs out
        if remaining > 0.5:
            # Green zone
            bar_color = (80, 220, 100, 200)
        elif remaining > 0.25:
            # Yellow zone
            bar_color = (255, 220, 50, 220)
        else:
            # Red zone — pulse for urgency
            pulse = 0.7 + 0.3 * math.sin(progress * 20)
            bar_color = (255, int(60 * pulse), int(60 * pulse), 240)

        # Background track (dark, subtle)
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + bar_full_w, bar_y + bar_height],
            radius=bar_height // 2,
            fill=(0, 0, 0, 80)
        )

        # Filled portion (remaining time)
        filled_w = max(bar_height, int(bar_full_w * remaining))
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + filled_w, bar_y + bar_height],
            radius=bar_height // 2,
            fill=bar_color
        )

        # Bright tip at the end of the filled portion
        if remaining > 0.05:
            tip_x = bar_x + filled_w - bar_height // 2
            draw.ellipse(
                [tip_x - 3, bar_y - 2, tip_x + 3, bar_y + bar_height + 2],
                fill=(255, 255, 255, 180)
            )

        if frame.mode != "RGBA":
            frame = frame.convert("RGBA")
        return Image.alpha_composite(frame, overlay)


# ============================================================
# Enhanced text effects — glow, rainbow, pulsing
# ============================================================

def render_glow_text(frame: Image.Image, text: str,
                     position: tuple, font_size: int,
                     glow_color: tuple = (255, 200, 50),
                     text_color: tuple = (255, 255, 255),
                     glow_radius: int = 8) -> Image.Image:
    """
    # Render text with a bright outer glow effect.
    # Used for countdown numbers and answer reveals.
    # Creates the "neon sign" effect seen in top kids content.
    """
    if frame.mode != "RGBA":
        frame = frame.convert("RGBA")

    # Load font
    from frame_composer import _get_font
    font = _get_font(font_size)

    # --- Step 1: Draw glow layer (blurred colored text behind main text) ---
    glow_layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    # Draw text in glow color at slightly larger size for spread
    glow_draw.text(position, text, font=font,
                   fill=glow_color + (200,), anchor="mm")
    # Blur to create the glow spread
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(glow_radius))
    frame = Image.alpha_composite(frame, glow_layer)

    # --- Step 2: Draw a second glow pass for extra intensity ---
    glow2 = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    glow2_draw = ImageDraw.Draw(glow2)
    glow2_draw.text(position, text, font=font,
                    fill=glow_color + (150,), anchor="mm")
    glow2 = glow2.filter(ImageFilter.GaussianBlur(glow_radius // 2))
    frame = Image.alpha_composite(frame, glow2)

    # --- Step 3: Draw crisp main text on top ---
    main_draw = ImageDraw.Draw(frame)
    main_draw.text(position, text, font=font,
                   fill=text_color, anchor="mm",
                   stroke_width=3, stroke_fill=(0, 0, 0))

    return frame


def render_rainbow_text(frame: Image.Image, text: str,
                        position: tuple, font_size: int,
                        t: float = 0.0) -> Image.Image:
    """
    # Render text with animated rainbow gradient coloring.
    # Each character gets a different hue that shifts over time.
    # Used for the answer reveal "It's a ___!" text.
    """
    import colorsys
    # Always copy to avoid mutating the input image
    result = frame.copy()
    if result.mode != "RGBA":
        result = result.convert("RGBA")

    from frame_composer import _get_font
    font = _get_font(font_size)

    # Calculate total text width for centering
    temp_draw = ImageDraw.Draw(result)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Start position (centered at position)
    start_x = position[0] - text_width // 2
    y = position[1] - text_height // 2

    # Draw each character with a different rainbow color
    draw = ImageDraw.Draw(result)
    x_offset = 0
    for i, char in enumerate(text):
        # Hue cycles through rainbow, animated over time
        hue = (i / max(len(text), 1) + t * 0.5) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.9, 1.0)
        color = (int(r * 255), int(g * 255), int(b * 255))

        # Get this character's width for positioning
        char_bbox = font.getbbox(char)
        char_w = char_bbox[2] - char_bbox[0]

        # Draw character with black stroke for readability
        draw.text((start_x + x_offset, y), char, font=font,
                  fill=color, stroke_width=3, stroke_fill=(0, 0, 0))
        x_offset += char_w

    return result


def render_text_wrapped(frame: Image.Image, text: str,
                        position: tuple, font_size: int,
                        max_width: int, color: tuple = (255, 255, 255),
                        stroke_width: int = 2) -> Image.Image:
    """
    # Render text with automatic word wrapping.
    # Splits text into multiple lines that fit within max_width.
    # Used for fun facts that are too long for a single line.
    """
    if frame.mode != "RGBA":
        frame = frame.convert("RGBA")

    from frame_composer import _get_font
    font = _get_font(font_size)
    draw = ImageDraw.Draw(frame)

    # Word-wrap: split text into lines that fit max_width
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = font.getbbox(test_line)
        if bbox[2] - bbox[0] > max_width and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    # Calculate total height for vertical centering
    line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1] + 8
    total_height = len(lines) * line_height
    start_y = position[1] - total_height // 2

    # Draw each line centered
    for i, line in enumerate(lines):
        line_y = start_y + i * line_height + line_height // 2
        draw.text((position[0], line_y), line, font=font,
                  fill=color, anchor="mm",
                  stroke_width=stroke_width, stroke_fill=(0, 0, 0))

    return frame


# ============================================================
# Vignette overlay — darkens edges for cinematic depth
# ============================================================

def apply_vignette(frame: Image.Image, intensity: float = 0.4) -> Image.Image:
    """
    # Apply a vignette (darkened edges) to the frame.
    # Creates cinematic depth and draws focus to the center.
    # intensity: 0.0 = no vignette, 1.0 = heavy vignette
    """
    if frame.mode != "RGBA":
        frame = frame.convert("RGBA")

    w, h = frame.size
    # Create radial gradient: white center, black edges
    vignette = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(vignette)

    # Draw concentric ellipses — bright at center, dark at edges
    cx, cy = w // 2, h // 2
    max_radius = int(math.sqrt(cx ** 2 + cy ** 2))
    for r in range(max_radius, 0, -2):
        # Brightness falls off with distance from center
        progress = r / max_radius
        brightness = int(255 * (1 - progress * progress * intensity))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=brightness)

    # Apply vignette as darkening mask
    # Multiply frame brightness by vignette mask
    frame_arr = np.array(frame).astype(np.float32)
    vig_arr = np.array(vignette).astype(np.float32) / 255.0
    # Apply to RGB channels only, keep alpha intact
    frame_arr[:, :, 0] *= vig_arr
    frame_arr[:, :, 1] *= vig_arr
    frame_arr[:, :, 2] *= vig_arr

    return Image.fromarray(frame_arr.astype(np.uint8))


# ============================================================
# Animated round transition — wipe/zoom between rounds
# ============================================================

def render_round_transition(frame1: Image.Image, frame2: Image.Image,
                            progress: float) -> Image.Image:
    """
    # Blend two frames together for a round transition.
    # progress: 0.0 = full frame1, 1.0 = full frame2
    # Uses a zoom-out/zoom-in effect instead of simple crossfade.
    """
    if progress <= 0:
        return frame1
    if progress >= 1:
        return frame2

    w, h = frame1.size

    # Frame 1 zooms out (shrinks + fades)
    zoom1 = 1.0 + 0.1 * progress  # Grows slightly
    opacity1 = 1.0 - progress

    # Frame 2 zooms in (from small + faded)
    zoom2 = 0.9 + 0.1 * progress  # Grows from 0.9 to 1.0
    opacity2 = progress

    # Apply zoom to frame 1
    f1 = KenBurnsZoom.apply(frame1, progress, 0, 1.0, zoom1)
    # Apply zoom to frame 2
    f2 = KenBurnsZoom.apply(frame2, 1 - progress, 0, 1.0, 1.0 / zoom2)

    # Alpha blend the two frames
    f1_arr = np.array(f1.convert("RGBA")).astype(np.float32)
    f2_arr = np.array(f2.convert("RGBA")).astype(np.float32)
    blended = f1_arr * opacity1 + f2_arr * opacity2
    return Image.fromarray(blended.astype(np.uint8))
