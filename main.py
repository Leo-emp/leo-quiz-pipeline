# main.py
# ============================================================
# Leo Quiz pipeline orchestrator.
# Runs the full video generation pipeline end-to-end:
# content → images → silhouettes → narration → audio → video → thumbnail → metadata
# Can be triggered via CLI, scheduler, or GitHub Actions.
# ============================================================
import argparse
import json
from datetime import datetime
from pathlib import Path

import config
from quiz_generator import generate_quiz_pack, QuizPack
from image_generator import generate_quiz_image
from silhouette import extract_silhouette, validate_silhouette
from narration import generate_round_narration, RoundAudio
from audio_mixer import build_short_audio
from video_assembler import assemble_short
from longform_assembler import assemble_longform
from thumbnail import generate_thumbnail
from metadata import generate_metadata, save_metadata
from sfx_generator import ensure_all_sfx
from mascot_generator import ensure_mascot_images
from font_downloader import ensure_fonts
from music_downloader import ensure_music


def run_pipeline(category: str = None, num_rounds: int = None,
                  output_dir: Path = None, video_format: str = "short") -> Path:
    """
    # Run the complete Leo Quiz pipeline for one video.
    # Supports 3 formats:
    #   - "short": 6 rounds, 9:16 vertical (66s) — YouTube Shorts / TikTok / Reels
    #   - "long":  60 rounds, 16:9 landscape (~10min) — YouTube long-form
    #   - "mega":  100 rounds, 16:9 landscape (~15min) — weekly mega quiz
    # 8 steps: content → images → silhouettes → narration → audio → video → thumbnail → metadata
    # Returns path to the output video file.
    """
    # Default category from day-of-week rotation
    if category is None:
        category = config.get_today_category()

    # Default rounds based on video format
    if num_rounds is None:
        if video_format == "long":
            num_rounds = config.LONGFORM_ROUNDS      # 60 rounds
        elif video_format == "mega":
            num_rounds = config.MEGA_ROUNDS           # 100 rounds
        else:
            num_rounds = config.ROUNDS_PER_SHORT      # 6 rounds

    # Output directory: shorts/ for short, longform/ for long/mega
    if output_dir is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        if video_format in ("long", "mega"):
            output_dir = config.LONGFORM_DIR / f"{date_str}_{category}_{video_format}"
        else:
            output_dir = config.SHORTS_DIR / f"{date_str}_{category}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[LEO QUIZ] Starting pipeline: {category}, {num_rounds} rounds, format={video_format}")
    print(f"[LEO QUIZ] Output: {output_dir}")

    # --- Step 0a: Ensure custom fonts are available ---
    # Downloads Baloo 2 (titles) and Fredoka One (countdown) from Google Fonts.
    # Only runs if fonts are missing — once downloaded, they're reused forever.
    print("[LEO QUIZ] Step 0a: Checking fonts...")
    ensure_fonts()

    # --- Step 0b: Ensure Leo mascot images exist ---
    # Generates 4 mascot poses via Gemini Imagen (or fallback PIL drawings).
    # Only runs if poses are missing — once generated, they're reused forever.
    print("[LEO QUIZ] Step 0b: Checking mascot assets...")
    ensure_mascot_images()

    # --- Step 0c: Download real background music ---
    # Downloads royalty-free tracks from Pixabay for each category.
    # Real instruments > numpy sine waves. Skips if tracks exist.
    print("[LEO QUIZ] Step 0c: Checking background music...")
    ensure_music()

    # --- Step 0d: Ensure all SFX exist ---
    # Auto-generates any missing SFX from pure math (numpy).
    # BGM generation now only runs if real music download failed.
    # Skips files that already exist — drop in your own WAVs to override.
    print("[LEO QUIZ] Step 0d: Checking sound effects...")
    ensure_all_sfx()

    # --- Step 1: Generate quiz content via Gemini ---
    print("[LEO QUIZ] Step 1: Generating quiz content...")
    quiz_pack = generate_quiz_pack(category, num_rounds)
    print(f"[LEO QUIZ]   Generated {len(quiz_pack.rounds)} rounds")

    # Sort rounds by difficulty for long-form/mega (top performer standard:
    # implicit progression — easy first hooks kids, hard later adds challenge)
    if video_format in ("long", "mega"):
        difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
        quiz_pack.rounds.sort(key=lambda r: difficulty_order.get(r.difficulty, 1))

    for i, r in enumerate(quiz_pack.rounds):
        print(f"[LEO QUIZ]   Round {i+1}: {r.answer} ({r.difficulty})")

    # Save quiz pack for weekly compiler to collect later
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

    # --- Step 2: Generate cartoon images via Gemini Imagen ---
    print("[LEO QUIZ] Step 2: Generating quiz images...")
    rounds_dir = output_dir / "rounds"
    rounds_dir.mkdir(exist_ok=True)

    image_paths = []
    for i, r in enumerate(quiz_pack.rounds):
        img_path = rounds_dir / f"round_{i+1}_image.png"
        print(f"[LEO QUIZ]   Generating image for: {r.answer}")
        generate_quiz_image(r, img_path)
        image_paths.append(img_path)

    # --- Step 3: Extract silhouettes from images ---
    print("[LEO QUIZ] Step 3: Extracting silhouettes...")
    silhouette_paths = []
    for i, img_path in enumerate(image_paths):
        sil_path = rounds_dir / f"round_{i+1}_silhouette.png"
        extract_silhouette(img_path, sil_path)

        # Validate silhouette quality (warn if coverage is too small/large)
        if not validate_silhouette(sil_path):
            print(f"[LEO QUIZ]   WARNING: Silhouette for round {i+1} may be poor quality")

        silhouette_paths.append(sil_path)

    # --- Step 4: Generate voice narration via ElevenLabs ---
    print("[LEO QUIZ] Step 4: Generating narration...")
    round_audios = []
    for i, r in enumerate(quiz_pack.rounds):
        audio_dir = rounds_dir / f"round_{i+1}_audio"
        print(f"[LEO QUIZ]   Narrating: {r.answer}")
        # Tag round with its index so narration picks varied phrases
        r._round_index = i
        ra = generate_round_narration(r, category, audio_dir)
        round_audios.append(ra)

    # --- Step 5: Mix audio (voice + SFX + music) ---
    print("[LEO QUIZ] Step 5: Mixing audio...")

    # Calculate total duration based on video format
    if video_format == "long":
        total_duration = (config.LONGFORM_INTRO_DURATION +
                          num_rounds * config.LONGFORM_ROUND_DURATION +
                          config.LONGFORM_OUTRO_DURATION)
    elif video_format == "mega":
        total_duration = (config.MEGA_INTRO_DURATION +
                          num_rounds * config.MEGA_ROUND_DURATION +
                          config.MEGA_OUTRO_DURATION)
    else:
        total_duration = (config.INTRO_DURATION +
                          num_rounds * config.ROUND_DURATION +
                          config.OUTRO_DURATION)

    # Find a background music track
    music_path = _find_music_track(category)

    audio_path = output_dir / "audio_mixed.wav"
    build_short_audio(round_audios, music_path, total_duration, audio_path)

    # --- Step 6: Assemble video (frame-by-frame rendering) ---
    print("[LEO QUIZ] Step 6: Assembling video...")
    video_path = output_dir / "video.mp4"

    if video_format in ("long", "mega"):
        # 16:9 landscape assembler for long-form / mega quiz
        assemble_longform(quiz_pack, image_paths, silhouette_paths,
                           round_audios, audio_path, video_path,
                           format_type=video_format)
    else:
        # 9:16 vertical assembler for shorts
        assemble_short(quiz_pack, image_paths, silhouette_paths,
                        round_audios, audio_path, video_path)

    # --- Step 7: Generate thumbnail ---
    print("[LEO QUIZ] Step 7: Generating thumbnail...")
    thumb_path = output_dir / "thumbnail.png"
    generate_thumbnail(quiz_pack, image_paths, silhouette_paths, thumb_path)

    # --- Step 8: Generate platform metadata ---
    # Generate metadata for all 4 platforms (YouTube, TikTok, Instagram, Facebook)
    print("[LEO QUIZ] Step 8: Generating metadata...")
    for platform in ("youtube", "tiktok", "instagram", "facebook"):
        meta = generate_metadata(quiz_pack, platform)
        save_metadata(meta, output_dir / f"metadata_{platform}.json")

    print(f"[LEO QUIZ] Pipeline complete! Video: {video_path}")
    print(f"[LEO QUIZ] Format: {video_format}, Duration: ~{total_duration:.0f}s")
    return video_path


def _find_music_track(category: str) -> Path:
    """# Find a background music track — category-specific first, then any."""
    # Check for category-specific music file
    for ext in ("mp3", "wav"):
        path = config.MUSIC_DIR / f"{category}.{ext}"
        if path.exists():
            return path

    # Fall back to any music file in the music directory
    for ext in ("mp3", "wav"):
        tracks = list(config.MUSIC_DIR.glob(f"*.{ext}"))
        if tracks:
            return tracks[0]

    return None


if __name__ == "__main__":
    # CLI interface for manual pipeline runs
    parser = argparse.ArgumentParser(description="Leo Quiz — Kids Quiz Video Pipeline")
    parser.add_argument("--category", type=str, default=None,
                        help="Quiz category (animals, dinosaurs, space, vehicles, fruits, flags)")
    parser.add_argument("--rounds", type=int, default=None,
                        help="Number of quiz rounds (default depends on format)")
    parser.add_argument("--format", type=str, default="short",
                        choices=["short", "long", "mega"],
                        help="Video format: short (66s), long (~10min), mega (~15min)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory path")

    args = parser.parse_args()
    output_dir = Path(args.output) if args.output else None
    run_pipeline(category=args.category, num_rounds=args.rounds,
                  output_dir=output_dir, video_format=args.format)
