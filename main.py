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
from quiz_generator import generate_quiz_pack, generate_speed_quiz_pack, QuizPack, QuizRound
from image_generator import generate_quiz_image
from silhouette import extract_silhouette, validate_silhouette
from narration import generate_round_narration, RoundAudio
from audio_mixer import build_short_audio
from video_assembler import assemble_short
from longform_assembler import assemble_longform
from speed_quiz_assembler import assemble_speed_quiz
from speed_quiz_audio import build_speed_audio
from speed_thumbnail import generate_speed_thumbnail
from photo_fetcher import fetch_photos_batch
from thumbnail import generate_thumbnail, generate_all_thumbnails, select_best_thumbnail
from metadata import generate_metadata, generate_speed_metadata, save_metadata
from sfx_generator import ensure_all_sfx
from mascot_generator import ensure_mascot_images
from font_downloader import ensure_fonts
from music_downloader import ensure_music
from speed_narration import generate_speed_narration


def run_pipeline(category: str = None, num_rounds: int = None,
                  output_dir: Path = None, video_format: str = "short") -> Path:
    """
    # Run the complete Leo Quiz pipeline for one video.
    # Supports 4 formats:
    #   - "short": 6 rounds, 9:16 vertical (66s) — YouTube Shorts / TikTok / Reels
    #   - "long":  60 rounds, 16:9 landscape (~10min) — YouTube long-form
    #   - "mega":  100 rounds, 16:9 landscape (~15min) — weekly mega quiz
    #   - "speed": 120 rounds, 16:9 landscape (~16min) — Quiz Blitz style speed quiz
    # Returns path to the output video file.
    """
    # Default category from day-of-week rotation
    if category is None:
        category = config.get_today_category()

    # Default rounds based on video format
    if num_rounds is None:
        if video_format == "speed":
            num_rounds = config.SPEED_ROUNDS          # 120 rounds
        elif video_format == "long":
            num_rounds = config.LONGFORM_ROUNDS       # 60 rounds
        elif video_format == "mega":
            num_rounds = config.MEGA_ROUNDS           # 100 rounds
        else:
            num_rounds = config.ROUNDS_PER_SHORT      # 6 rounds

    # Output directory based on format
    if output_dir is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        if video_format == "speed":
            output_dir = config.LONGFORM_DIR / f"{date_str}_{category}_speed"
        elif video_format in ("long", "mega"):
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

    # ================================================================
    # Step 1: Generate quiz content via Gemini (with cache)
    # ================================================================
    # If a previous run saved quiz_pack.json in this output dir,
    # reuse it instead of burning another Gemini API call.
    # This happens when: same day + same category = same output_dir.
    # ================================================================
    print("[LEO QUIZ] Step 1: Generating quiz content...")

    quiz_pack_path = output_dir / "quiz_pack.json"
    quiz_pack = None

    # --- Check for cached quiz pack from a previous run ---
    if quiz_pack_path.exists():
        try:
            with open(quiz_pack_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached_rounds = cached.get("rounds", [])
            if cached_rounds and len(cached_rounds) >= num_rounds - 1:
                # --- Rebuild QuizPack from cached JSON ---
                quiz_pack = QuizPack(category=cached.get("category", category))
                for rd in cached_rounds:
                    quiz_pack.rounds.append(QuizRound(
                        answer=rd["answer"],
                        hint_question=rd["hint_question"],
                        fun_fact=rd["fun_fact"],
                        difficulty=rd["difficulty"],
                        image_prompt=rd.get("image_prompt", ""),
                        pexels_search=rd.get("pexels_search", ""),
                    ))
                print(f"[LEO QUIZ]   CACHED -- reusing {len(quiz_pack.rounds)} rounds "
                      f"from previous run (saves Gemini API call)")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[LEO QUIZ]   Cache corrupted ({e}), regenerating...")
            quiz_pack = None

    if quiz_pack is None:
        # --- Generate fresh quiz content via Gemini ---
        if video_format == "speed":
            quiz_pack = generate_speed_quiz_pack(category, num_rounds)
        else:
            quiz_pack = generate_quiz_pack(category, num_rounds)

    print(f"[LEO QUIZ]   Generated {len(quiz_pack.rounds)} rounds")

    # Sort rounds by difficulty for long-form/mega/speed
    if video_format in ("long", "mega"):
        difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
        quiz_pack.rounds.sort(key=lambda r: difficulty_order.get(r.difficulty, 1))

    for i, r in enumerate(quiz_pack.rounds):
        print(f"[LEO QUIZ]   Round {i+1}: {r.answer} ({r.difficulty})")

    # Save quiz pack for weekly compiler to collect later (also serves as cache)
    pack_data = {
        "category": quiz_pack.category,
        "rounds": [
            {
                "answer": r.answer,
                "hint_question": r.hint_question,
                "fun_fact": r.fun_fact,
                "difficulty": r.difficulty,
                "image_prompt": r.image_prompt,
                "pexels_search": getattr(r, "pexels_search", ""),
            }
            for r in quiz_pack.rounds
        ]
    }
    with open(quiz_pack_path, "w", encoding="utf-8") as f:
        json.dump(pack_data, f, indent=2, ensure_ascii=False)

    # ================================================================
    # Step 2: Generate images (with cache)
    # ================================================================
    # Images are the second most expensive step (Gemini Imagen for
    # non-speed, Pexels API for speed). If images already exist in
    # rounds_dir from a previous run, skip regeneration entirely.
    # ================================================================
    rounds_dir = output_dir / "rounds"
    rounds_dir.mkdir(exist_ok=True)

    if video_format == "speed":
        # Speed format: fetch real photos from Pexels API
        print("[LEO QUIZ] Step 2: Fetching real photos from Pexels...")

        # --- Check for cached speed photos ---
        cached_photos = [
            rounds_dir / f"round_{i+1}_photo.png"
            for i in range(len(quiz_pack.rounds))
        ]
        # --- Also check .jpg extension (Pexels might save as either) ---
        all_exist = all(p.exists() and p.stat().st_size > 5000 for p in cached_photos)
        if not all_exist:
            cached_photos = [
                rounds_dir / f"round_{i+1}_photo.jpg"
                for i in range(len(quiz_pack.rounds))
            ]
            all_exist = all(p.exists() and p.stat().st_size > 5000 for p in cached_photos)

        if all_exist:
            image_paths = cached_photos
            print(f"[LEO QUIZ]   CACHED -- reusing {len(image_paths)} photos")
        else:
            image_paths = fetch_photos_batch(quiz_pack.rounds, rounds_dir)
            print(f"[LEO QUIZ]   Fetched {len(image_paths)} photos")

        # No silhouettes needed for speed format (real photos shown directly)
        silhouette_paths = []
    else:
        # Original format: generate cartoon images via Gemini
        print("[LEO QUIZ] Step 2: Generating quiz images...")
        image_paths = []
        cached_count = 0
        for i, r in enumerate(quiz_pack.rounds):
            img_path = rounds_dir / f"round_{i+1}_image.png"
            # --- Skip if image already exists from previous run ---
            if img_path.exists() and img_path.stat().st_size > 5000:
                cached_count += 1
                image_paths.append(img_path)
                continue
            print(f"[LEO QUIZ]   Generating image for: {r.answer}")
            generate_quiz_image(r, img_path)
            image_paths.append(img_path)

        if cached_count > 0:
            print(f"[LEO QUIZ]   CACHED {cached_count}/{len(quiz_pack.rounds)} images "
                  f"(saves {cached_count} Gemini Imagen calls)")

        # ================================================================
        # Step 3: Extract silhouettes (with cache)
        # ================================================================
        # Silhouette extraction is local PIL work (free), but still
        # skip if files exist from a previous run for speed.
        # ================================================================
        print("[LEO QUIZ] Step 3: Extracting silhouettes...")
        silhouette_paths = []
        for i, img_path in enumerate(image_paths):
            sil_path = rounds_dir / f"round_{i+1}_silhouette.png"
            # --- Skip if silhouette already exists ---
            if sil_path.exists() and sil_path.stat().st_size > 1000:
                silhouette_paths.append(sil_path)
                continue
            extract_silhouette(img_path, sil_path)

            if not validate_silhouette(sil_path):
                print(f"[LEO QUIZ]   WARNING: Silhouette for round {i+1} may be poor quality")

            silhouette_paths.append(sil_path)

    # ================================================================
    # Step 4: Generate voice narration via ElevenLabs (with cache)
    # ================================================================
    # Narration is the MOST expensive step — each round makes 3
    # ElevenLabs API calls (question, reveal, fun fact).
    # For 6 rounds = 18 calls, for 60 rounds = 180 calls.
    # If audio files already exist from a previous run, reuse them.
    # ================================================================
    print("[LEO QUIZ] Step 4: Generating narration...")
    round_audios = []

    # narration_pack holds the SpeedNarrationPack for speed format (None for others)
    narration_pack = None

    if video_format == "speed":
        # Speed format: ~140 voice clips per video via Gemini + ElevenLabs
        # Structure clips: intro, subscribe, 4 sections, ~12 reactions, outro
        # + 120 per-round answer reveals ("It's a Lion!", "Eagle! Wow!", etc.)
        # Gemini generates varied phrase templates, each round gets a random one
        #
        # --- Check for cached speed narration pack ---
        # Speed narration stores files in output_dir/narration/ — if the
        # intro.mp3 + outro.mp3 + answer reveals exist, skip regeneration
        speed_narr_dir = output_dir / "narration"
        speed_reveals_dir = speed_narr_dir / "reveals"
        speed_cached = (
            speed_narr_dir.exists()
            and (speed_narr_dir / "intro.mp3").exists()
            and (speed_narr_dir / "outro.mp3").exists()
        )
        if speed_cached:
            # --- Count cached answer reveals to verify completeness ---
            reveal_count = len(list(speed_reveals_dir.glob("reveal_*.mp3"))) if speed_reveals_dir.exists() else 0
            speed_cached = reveal_count >= num_rounds - 5  # allow small margin

        if speed_cached:
            print(f"[LEO QUIZ]   CACHED -- reusing speed narration pack "
                  f"({reveal_count} answer reveals found)")
            # --- Rebuild narration pack from cached files ---
            from speed_narration import load_cached_narration_pack
            narration_pack = load_cached_narration_pack(output_dir, num_rounds)
        else:
            print("[LEO QUIZ]   Generating fresh voiceover pack...")
            answer_list = [r.answer for r in quiz_pack.rounds]
            narration_pack = generate_speed_narration(
                category, output_dir, num_rounds, answers=answer_list
            )

        for i, r in enumerate(quiz_pack.rounds):
            r._round_index = i
            round_audios.append(RoundAudio(
                question_path=Path(""), reveal_path=Path(""),
                fact_path=Path(""),
            ))
    else:
        narr_cached_count = 0
        for i, r in enumerate(quiz_pack.rounds):
            audio_dir = rounds_dir / f"round_{i+1}_audio"
            r._round_index = i

            # --- Check if all 3 narration files exist from previous run ---
            q_file = audio_dir / "question.mp3"
            r_file = audio_dir / "reveal.mp3"
            f_file = audio_dir / "fact.mp3"

            if (q_file.exists() and q_file.stat().st_size > 1000
                    and r_file.exists() and r_file.stat().st_size > 1000
                    and f_file.exists() and f_file.stat().st_size > 1000):
                # --- Reuse cached narration (saves 3 ElevenLabs calls) ---
                narr_cached_count += 1

                # --- Load cached timestamps if available ---
                ts_file = audio_dir / "fact_timestamps.json"
                fact_timestamps = []
                if ts_file.exists():
                    try:
                        with open(ts_file, "r", encoding="utf-8") as f:
                            fact_timestamps = json.load(f)
                    except Exception:
                        fact_timestamps = []

                # --- Check for cached reaction ---
                from narration import _ensure_reaction
                reaction_path = _ensure_reaction(i)

                round_audios.append(RoundAudio(
                    question_path=q_file,
                    reveal_path=r_file,
                    fact_path=f_file,
                    fact_timestamps=fact_timestamps,
                    reaction_path=reaction_path,
                ))
            else:
                # --- Generate fresh narration for this round ---
                print(f"[LEO QUIZ]   Narrating: {r.answer}")
                ra = generate_round_narration(r, category, audio_dir)

                # --- Cache the timestamps for future retries ---
                if ra.fact_timestamps:
                    ts_file = audio_dir / "fact_timestamps.json"
                    with open(ts_file, "w", encoding="utf-8") as f:
                        json.dump(ra.fact_timestamps, f)

                round_audios.append(ra)

        if narr_cached_count > 0:
            print(f"[LEO QUIZ]   CACHED {narr_cached_count}/{len(quiz_pack.rounds)} "
                  f"narration rounds (saves {narr_cached_count * 3} ElevenLabs calls)")

    # --- Step 5: Mix audio (voice + SFX + music) ---
    print("[LEO QUIZ] Step 5: Mixing audio...")

    # Calculate total duration based on video format
    if video_format == "speed":
        # Speed: intro + subscribe + (section_card + 30 rounds) × 4 + outro
        total_duration = (config.SPEED_INTRO_DURATION +
                          config.SPEED_SUBSCRIBE_DURATION +
                          len(config.SPEED_DIFFICULTIES) * (
                              config.SPEED_SECTION_CARD_DURATION +
                              config.SPEED_ROUNDS_PER_DIFFICULTY * config.SPEED_ROUND_DURATION
                          ) +
                          config.SPEED_OUTRO_DURATION)
    elif video_format == "long":
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

    if video_format == "speed":
        # Speed format: dedicated audio mixer with fresh voiceover narration pack
        build_speed_audio(round_audios, music_path, total_duration, audio_path,
                          num_rounds=num_rounds, narration_pack=narration_pack)
    else:
        build_short_audio(round_audios, music_path, total_duration, audio_path)

    # --- Step 6: Assemble video (frame-by-frame rendering) ---
    print("[LEO QUIZ] Step 6: Assembling video...")
    video_path = output_dir / "video.mp4"

    if video_format == "speed":
        # Speed quiz assembler: Quiz Blitz style with real photos
        # Pass narration_pack so Leo's speech bubbles show what he's saying
        assemble_speed_quiz(quiz_pack, image_paths, round_audios,
                             audio_path, video_path,
                             narration_pack=narration_pack)
    elif video_format in ("long", "mega"):
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
    if video_format == "speed":
        # Speed format: 5 viral thumbnail variants, Gemini auto-selects best
        thumb_path = generate_speed_thumbnail(quiz_pack, image_paths, output_dir)
        print(f"[LEO QUIZ]   Generated 5 variants: A(Grid) B(Challenge) C(Number) D(Mystery) E(Difficulty)")
    else:
        # Original A/B thumbnail system with Gemini auto-selection
        thumb_paths = generate_all_thumbnails(quiz_pack, image_paths, silhouette_paths, output_dir)
        print(f"[LEO QUIZ]   Generated 3 variants: A (split), B (mystery), C (grid)")
        best_variant = select_best_thumbnail(thumb_paths)
        print(f"[LEO QUIZ]   Gemini selected variant: {best_variant.upper()}")
        import shutil
        thumb_path = output_dir / "thumbnail.png"
        shutil.copy2(thumb_paths[best_variant], thumb_path)

    # --- Step 8: Generate platform metadata ---
    print("[LEO QUIZ] Step 8: Generating metadata...")
    for platform in ("youtube", "tiktok", "instagram", "facebook"):
        if video_format == "speed":
            # Speed format: deterministic SEO formula (no Gemini needed)
            meta = generate_speed_metadata(quiz_pack, platform)
        else:
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
                        choices=["short", "long", "mega", "speed"],
                        help="Video format: short (66s), long (~10min), mega (~15min), speed (~16min)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory path")

    args = parser.parse_args()
    output_dir = Path(args.output) if args.output else None
    run_pipeline(category=args.category, num_rounds=args.rounds,
                  output_dir=output_dir, video_format=args.format)
