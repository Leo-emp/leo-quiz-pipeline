# ffmpeg_pipe.py
# ============================================================
# PIL-to-ffmpeg frame pipe for Leo Quiz.
# Replaces MoviePy's VideoClip → write_videofile with direct
# raw frame piping to ffmpeg stdin. 3-5x faster rendering.
#
# Usage:
#   pipe_frames_to_video(
#       render_fn=lambda t: render_frame(t, ctx),
#       duration=total_duration,
#       fps=30,
#       width=1080, height=1920,
#       audio_path="mixed_audio.mp3",
#       output_path="output.mp4",
#   )
#
# How it works:
#   1. Opens ffmpeg subprocess with rawvideo on stdin
#   2. Loops t from 0 to duration at 1/fps increments
#   3. Calls render_fn(t) → numpy array (H, W, 3) uint8
#   4. Writes raw RGB bytes to ffmpeg's stdin pipe
#   5. ffmpeg encodes to H.264 with AAC audio
#
# Why faster than MoviePy:
#   - No intermediate temp files
#   - No Python-side audio processing
#   - No MoviePy overhead (progress bars, codec probing)
#   - ffmpeg handles muxing natively
# ============================================================
import os
import subprocess
import sys
import time

import numpy as np

# --- Ensure FFmpeg is on PATH (winget install location on Windows) ---
_ffmpeg_dir = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Microsoft", "WinGet", "Packages",
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe",
    "ffmpeg-9.0.1-full_build", "bin",
)
if os.path.isdir(_ffmpeg_dir) and _ffmpeg_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def pipe_frames_to_video(
    render_fn,
    duration: float,
    fps: int,
    width: int,
    height: int,
    audio_path: str = None,
    output_path: str = "output.mp4",
    bitrate: str = "8000k",
    preset: str = "fast",
    audio_bitrate: str = "192k",
    progress_interval: float = 5.0,
):
    """
    # Pipe PIL-rendered frames directly to ffmpeg for encoding.
    #
    # Args:
    #   render_fn: function(t: float) -> numpy array (H, W, 3) uint8
    #              Same signature as MoviePy's make_frame.
    #   duration:  total video length in seconds
    #   fps:       frames per second (typically 30)
    #   width:     frame width in pixels
    #   height:    frame height in pixels
    #   audio_path: optional mixed audio file to mux in
    #   output_path: where to save the final MP4
    #   bitrate:   video bitrate (e.g. "8000k")
    #   preset:    x264 preset ("ultrafast" to "veryslow")
    #   audio_bitrate: audio bitrate (e.g. "192k")
    #   progress_interval: seconds between progress prints
    """
    total_frames = int(duration * fps)
    frame_size = width * height * 3  # RGB24: 3 bytes per pixel

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # --- Build ffmpeg command ---
    cmd = ["ffmpeg", "-y"]

    # --- Input 0: raw video frames from stdin ---
    cmd += [
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "pipe:0",
    ]

    # --- Input 1: audio file (optional) ---
    has_audio = audio_path and os.path.exists(str(audio_path))
    if has_audio:
        cmd += ["-i", str(audio_path)]

    # --- Output encoding ---
    cmd += [
        "-c:v", "libx264",
        "-preset", preset,
        "-b:v", bitrate,
        "-pix_fmt", "yuv420p",
        "-fps_mode", "vfr",
    ]

    if has_audio:
        cmd += [
            "-c:a", "aac",
            "-b:a", audio_bitrate,
            "-shortest",
        ]
    else:
        cmd += ["-an"]

    cmd += [str(output_path)]

    print(f"[FFMPEG PIPE] Rendering {total_frames} frames ({duration:.1f}s @ {fps}fps)")
    print(f"[FFMPEG PIPE] Resolution: {width}x{height}, preset: {preset}")
    sys.stdout.flush()

    # --- Redirect ffmpeg stderr to a temp file to prevent deadlock ---
    # CRITICAL: using stderr=PIPE causes deadlock on Windows because Python
    # writes frames to stdin while ffmpeg writes progress to stderr. Once the
    # stderr pipe buffer fills (~4KB), ffmpeg blocks → Python blocks → deadlock.
    # Solution: write stderr to a temp file, read it after ffmpeg finishes.
    import tempfile
    stderr_file = tempfile.NamedTemporaryFile(
        mode="w+b", suffix="_ffmpeg.log", delete=False
    )
    stderr_path = stderr_file.name

    # --- Open ffmpeg subprocess with piped stdin ---
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=stderr_file,
    )

    start_time = time.time()
    last_progress = start_time
    frames_written = 0

    try:
        for frame_idx in range(total_frames):
            t = frame_idx / fps

            # --- Render frame via PIL/numpy ---
            frame_array = render_fn(t)

            # --- Ensure correct dtype and shape ---
            if frame_array.dtype != np.uint8:
                frame_array = frame_array.astype(np.uint8)
            if frame_array.shape != (height, width, 3):
                # --- Handle RGBA → RGB ---
                if len(frame_array.shape) == 3 and frame_array.shape[2] == 4:
                    frame_array = frame_array[:, :, :3]

            # --- Write raw bytes to ffmpeg stdin ---
            proc.stdin.write(frame_array.tobytes())
            frames_written += 1

            # --- Progress reporting ---
            now = time.time()
            if now - last_progress >= progress_interval:
                elapsed = now - start_time
                pct = (frame_idx + 1) / total_frames * 100
                fps_actual = frames_written / elapsed if elapsed > 0 else 0
                eta = (total_frames - frame_idx) / fps_actual if fps_actual > 0 else 0
                print(
                    f"[FFMPEG PIPE] {pct:.0f}% ({frame_idx + 1}/{total_frames}) "
                    f"— {fps_actual:.1f} fps — ETA {eta:.0f}s"
                )
                sys.stdout.flush()
                last_progress = now

    except BrokenPipeError:
        # --- ffmpeg exited early (error in encoding) ---
        proc.wait()
        stderr_file.close()
        with open(stderr_path, "rb") as f:
            stderr_text = f.read().decode(errors="replace")
        os.unlink(stderr_path)
        print(f"[FFMPEG PIPE] Pipe broken: {stderr_text[-300:]}")
        return None

    # --- Close stdin and wait for ffmpeg to finish ---
    proc.stdin.close()
    proc.wait(timeout=120)
    stderr_file.close()

    # --- Read stderr log for error reporting ---
    with open(stderr_path, "rb") as f:
        stderr_text = f.read().decode(errors="replace")
    os.unlink(stderr_path)

    elapsed = time.time() - start_time

    if proc.returncode != 0:
        print(f"[FFMPEG PIPE] Encoding failed: {stderr_text[-300:]}")
        return None

    # --- Verify output ---
    if os.path.exists(output_path) and os.path.getsize(output_path) > 10_000:
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(
            f"[FFMPEG PIPE] Done: {size_mb:.1f} MB, "
            f"{frames_written} frames in {elapsed:.1f}s "
            f"({frames_written / elapsed:.1f} fps)"
        )
        return output_path
    else:
        print("[FFMPEG PIPE] Output missing or too small")
        return None
