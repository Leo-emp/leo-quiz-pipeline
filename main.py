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
from thumbnail import generate_thumbnail
from metadata import generate_metadata, save_metadata


def run_pipeline(category: str = None, num_rounds: int = None,
                  output_dir: Path = None) -> Path:
    """
    # Run the complete Leo Quiz pipeline for one short-form video.
    # 8 steps: content → images → silhouettes → narration → audio → video → thumbnail → metadata
    # Returns path to the output video file.
    """
    # Default category from day-of-week rotation
    if category is None:
        category = config.get_today_category()
    # Default 5 rounds per short
    if num_rounds is None:
        num_rounds = config.ROUNDS_PER_SHORT
    # Default output dir: output/shorts/YYYY-MM-DD_category/
    if output_dir is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_dir = config.SHORTS_DIR / f"{date_str}_{category}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[LEO QUIZ] Starting pipeline: {category}, {num_rounds} rounds")
    print(f"[LEO QUIZ] Output: {output_dir}")

    # --- Step 1: Generate quiz content via Gemini ---
    print("[LEO QUIZ] Step 1: Generating quiz content...")
    quiz_pack = generate_quiz_pack(category, num_rounds)
    print(f"[LEO QUIZ]   Generated {len(quiz_pack.rounds)} rounds")
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
        ra = generate_round_narration(r, category, audio_dir)
        round_audios.append(ra)

    # --- Step 5: Mix audio (voice + SFX + music) ---
    print("[LEO QUIZ] Step 5: Mixing audio...")
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
    assemble_short(quiz_pack, image_paths, silhouette_paths,
                    round_audios, audio_path, video_path)

    # --- Step 7: Generate thumbnail ---
    print("[LEO QUIZ] Step 7: Generating thumbnail...")
    thumb_path = output_dir / "thumbnail.png"
    generate_thumbnail(quiz_pack, image_paths, silhouette_paths, thumb_path)

    # --- Step 8: Generate platform metadata ---
    print("[LEO QUIZ] Step 8: Generating metadata...")
    yt_meta = generate_metadata(quiz_pack, "youtube")
    save_metadata(yt_meta, output_dir / "metadata_youtube.json")

    tt_meta = generate_metadata(quiz_pack, "tiktok")
    save_metadata(tt_meta, output_dir / "metadata_tiktok.json")

    print(f"[LEO QUIZ] Pipeline complete! Video: {video_path}")
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
                        help="Number of quiz rounds (default: 5)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory path")

    args = parser.parse_args()
    output_dir = Path(args.output) if args.output else None
    run_pipeline(category=args.category, num_rounds=args.rounds, output_dir=output_dir)
