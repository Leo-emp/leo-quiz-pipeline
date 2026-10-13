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

from PIL import Image

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
from photo_fetcher import fetch_photos_batch, fetch_photo
from thumbnail import generate_thumbnail, generate_all_thumbnails, select_best_thumbnail
from metadata import generate_metadata, generate_speed_metadata, save_metadata
from sfx_generator import ensure_all_sfx
from mascot_generator import ensure_mascot_images
from font_downloader import ensure_fonts
from music_downloader import ensure_music
from speed_narration import generate_speed_narration
from emoji_quiz_generator import (
    generate_emoji_quiz_pack, EmojiQuizPack, EmojiQuizRound,
    serialize_emoji_pack, deserialize_emoji_pack,
)
from emoji_quiz_assembler import assemble_emoji_quiz
from emoji_quiz_audio import build_emoji_audio
from emoji_quiz_narration import generate_emoji_narration


def run_pipeline(category: str = None, num_rounds: int = None,
                  output_dir: Path = None, video_format: str = "short") -> Path:
    """
    # Run the complete Leo Quiz pipeline for one video.
    # Supports 5 formats:
    #   - "short": 6 rounds, 9:16 vertical (66s) — YouTube Shorts / TikTok / Reels
    #   - "long":  60 rounds, 16:9 landscape (~10min) — YouTube long-form
    #   - "mega":  100 rounds, 16:9 landscape (~15min) — weekly mega quiz
    #   - "speed": 120 rounds, 16:9 landscape (~16min) — Quiz Blitz style speed quiz
    #   - "emoji": 40 rounds, 16:9 landscape (~6min) — Monkey Quiz style emoji quiz
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
        elif video_format == "emoji":
            num_rounds = config.EMOJI_ROUNDS           # 40 rounds
        else:
            num_rounds = config.ROUNDS_PER_SHORT      # 6 rounds

    # Output directory based on format
    if output_dir is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        if video_format == "speed":
            output_dir = config.LONGFORM_DIR / f"{date_str}_{category}_speed"
        elif video_format == "emoji":
            output_dir = config.LONGFORM_DIR / f"{date_str}_{category}_emoji"
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
    # EMOJI FORMAT — completely separate pipeline
    # ================================================================
    # Emoji quiz doesn't need images, silhouettes, or per-round narration.
    # It uses Gemini to generate emoji clue + answer pairs, then renders
    # video with big emoji characters and text reveals.
    # ================================================================
    if video_format == "emoji":
        return _run_emoji_pipeline(category, num_rounds, output_dir)

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

    # --- Cache check: skip audio mixing if mixed file already exists ---
    if audio_path.exists() and audio_path.stat().st_size > 10000:
        print("[LEO QUIZ] Step 5: CACHED audio_mixed.wav — skipping mix")
    else:
        if video_format == "speed":
            build_speed_audio(round_audios, music_path, total_duration, audio_path,
                              num_rounds=num_rounds, narration_pack=narration_pack)
        else:
            build_short_audio(round_audios, music_path, total_duration, audio_path)

    # --- Step 6: Assemble video (frame-by-frame rendering) ---
    video_path = output_dir / "video.mp4"

    # --- Cache check: skip 20+ minute render if video already exists ---
    if video_path.exists() and video_path.stat().st_size > 100000:
        print(f"[LEO QUIZ] Step 6: CACHED video.mp4 "
              f"({video_path.stat().st_size / 1024 / 1024:.1f} MB) — skipping render")
    else:
        print("[LEO QUIZ] Step 6: Assembling video...")
        if video_format == "speed":
            assemble_speed_quiz(quiz_pack, image_paths, round_audios,
                                 audio_path, video_path,
                                 narration_pack=narration_pack)
        elif video_format in ("long", "mega"):
            assemble_longform(quiz_pack, image_paths, silhouette_paths,
                               round_audios, audio_path, video_path,
                               format_type=video_format)
        else:
            assemble_short(quiz_pack, image_paths, silhouette_paths,
                            round_audios, audio_path, video_path)

    # --- Step 7: Generate thumbnail ---
    thumb_path = output_dir / "thumbnail.png"

    # --- Cache check: skip thumbnail if it already exists ---
    if thumb_path.exists() and thumb_path.stat().st_size > 5000:
        print(f"[LEO QUIZ] Step 7: CACHED thumbnail.png — skipping generation")
    else:
        print("[LEO QUIZ] Step 7: Generating thumbnail...")
        if video_format == "speed":
            thumb_path = generate_speed_thumbnail(quiz_pack, image_paths, output_dir)
            print(f"[LEO QUIZ]   Generated 5 variants: A(Grid) B(Challenge) C(Number) D(Mystery) E(Difficulty)")
        else:
            thumb_paths = generate_all_thumbnails(quiz_pack, image_paths, silhouette_paths, output_dir)
            print(f"[LEO QUIZ]   Generated 3 variants: A (split), B (mystery), C (grid)")
            best_variant = select_best_thumbnail(thumb_paths)
            print(f"[LEO QUIZ]   Gemini selected variant: {best_variant.upper()}")
            import shutil
            thumb_path = output_dir / "thumbnail.png"
            shutil.copy2(thumb_paths[best_variant], thumb_path)

    # --- Step 8: Generate platform metadata ---
    # --- Cache check: skip if all 4 platform metadata files exist ---
    platforms = ("youtube", "tiktok", "instagram", "facebook")
    meta_paths = [output_dir / f"metadata_{p}.json" for p in platforms]
    if all(p.exists() for p in meta_paths):
        print("[LEO QUIZ] Step 8: CACHED metadata — skipping generation")
    else:
        print("[LEO QUIZ] Step 8: Generating metadata...")
        for platform in platforms:
            meta_file = output_dir / f"metadata_{platform}.json"
            if meta_file.exists():
                continue
            try:
                if video_format == "speed":
                    meta = generate_speed_metadata(quiz_pack, platform)
                else:
                    meta = generate_metadata(quiz_pack, platform)
                save_metadata(meta, meta_file)
            except RuntimeError as e:
                # Gemini quota exhausted — skip metadata, don't crash the pipeline
                print(f"[LEO QUIZ]   SKIPPED {platform} metadata (Gemini unavailable: {e})")
                print("[LEO QUIZ]   You can write the title/description manually or re-run later")
                break

    print(f"[LEO QUIZ] Pipeline complete! Video: {video_path}")
    print(f"[LEO QUIZ] Format: {video_format}, Duration: ~{total_duration:.0f}s")
    return video_path


def _run_emoji_pipeline(category: str, num_rounds: int,
                         output_dir: Path) -> Path:
    """
    # Run the Emoji Quiz pipeline — "Guess the X by Emoji" format.
    # Monkey Quiz quality with full voiceover narration throughout.
    #
    # Steps:
    #   1. Generate emoji quiz content (wordplay emoji clues via Gemini)
    #   1.5. Generate voice narration via ElevenLabs (intro, per-round, outro)
    #   2. Mix audio (music + SFX + voice narration with ducking)
    #   3. Render video (emoji clues → countdown → answer reveal)
    #   4. Generate thumbnail
    #   5. Generate metadata
    """
    # ================================================================
    # Step 1: Generate emoji quiz content (with cache)
    # ================================================================
    print("[EMOJI QUIZ] Step 1: Generating emoji quiz content...")

    quiz_pack_path = output_dir / "emoji_pack.json"
    emoji_pack = None

    # --- Check for cached emoji pack ---
    if quiz_pack_path.exists():
        try:
            with open(quiz_pack_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached_rounds = cached.get("rounds", [])
            if cached_rounds and len(cached_rounds) >= num_rounds - 1:
                emoji_pack = deserialize_emoji_pack(cached)
                print(f"[EMOJI QUIZ]   CACHED -- reusing {len(emoji_pack.rounds)} rounds")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[EMOJI QUIZ]   Cache corrupted ({e}), regenerating...")
            emoji_pack = None

    if emoji_pack is None:
        emoji_pack = generate_emoji_quiz_pack(category, num_rounds)

    print(f"[EMOJI QUIZ]   Generated {len(emoji_pack.rounds)} rounds")
    for i, r in enumerate(emoji_pack.rounds):
        # Use repr for emoji chars to avoid cp1252 encoding errors on Windows
        clues = " + ".join(repr(e) for e in r.emoji_clues)
        try:
            print(f"[EMOJI QUIZ]   Round {i+1}: {clues} = {r.answer} ({r.difficulty})")
        except UnicodeEncodeError:
            print(f"[EMOJI QUIZ]   Round {i+1}: [emoji] = {r.answer} ({r.difficulty})")

    # --- Save emoji pack for cache ---
    pack_data = serialize_emoji_pack(emoji_pack)
    with open(quiz_pack_path, "w", encoding="utf-8") as f:
        json.dump(pack_data, f, indent=2, ensure_ascii=False)

    # ================================================================
    # Step 1.5: Generate voice narration via ElevenLabs
    # ================================================================
    print("[EMOJI QUIZ] Step 1.5: Generating voice narration...")

    # --- Extract answer list for narration ---
    answers = [r.answer for r in emoji_pack.rounds]
    narr_pack = generate_emoji_narration(
        category, output_dir, len(emoji_pack.rounds), answers)

    narr_count = sum(1 for p in narr_pack.question_paths if p)
    print(f"[EMOJI QUIZ]   Narration: {narr_count} question + {narr_count} reveal clips")

    # ================================================================
    # Step 2: Mix audio (music + SFX + voice narration)
    # ================================================================
    print("[EMOJI QUIZ] Step 2: Mixing audio with narration...")

    # --- Calculate total duration using DYNAMIC intro length ---
    # Intro duration adapts to actual voiceover length (no overlap)
    from emoji_quiz_assembler import build_emoji_timeline
    intro_voice_dur = narr_pack.intro_duration + narr_pack.subscribe_duration
    timeline = build_emoji_timeline(len(emoji_pack.rounds),
                                     intro_duration=intro_voice_dur)
    total_duration = timeline[-1]["end"]
    print(f"[EMOJI QUIZ]   Intro voice: {intro_voice_dur:.1f}s -> "
          f"intro phase: {timeline[0]['end']:.1f}s")

    music_path = _find_music_track(category)
    audio_path = output_dir / "audio_mixed.wav"

    if audio_path.exists() and audio_path.stat().st_size > 10000:
        print("[EMOJI QUIZ]   CACHED audio_mixed.wav -- skipping mix")
    else:
        build_emoji_audio(music_path, total_duration, audio_path,
                           num_rounds=len(emoji_pack.rounds),
                           narration_pack=narr_pack,
                           emoji_counts=[len(r.emoji_clues) for r in emoji_pack.rounds])

    # ================================================================
    # Step 2.5: Fetch answer images from Pexels for reveal screen
    # ================================================================
    print("[EMOJI QUIZ] Step 2.5: Fetching answer images...")
    answer_images = {}
    photos_dir = output_dir / "answer_photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    # Build a smarter search query based on category so Pexels
    # returns the actual thing (e.g. "catfish animal" not a food dish)
    cat_info = config.EMOJI_CATEGORIES.get(emoji_pack.category, {})
    # Map each category to search suffix keywords that disambiguate
    _PHOTO_SEARCH_HINTS = {
        "animals": "animal wildlife",       # "catfish animal wildlife" → actual fish
        "food": "dish meal",                # "pizza dish meal" → food photo
        "restaurant": "restaurant logo",    # "McDonald's restaurant logo"
        "candy": "candy sweet",             # "Kit Kat candy sweet"
        "country": "country landscape",     # "Japan country landscape"
        "movie": "movie poster",            # "Frozen movie poster"
        "sport": "sport playing",           # "Tennis sport playing"
    }
    search_hint = _PHOTO_SEARCH_HINTS.get(emoji_pack.category, "")

    for i, rnd in enumerate(emoji_pack.rounds):
        photo_path = photos_dir / f"{i}_{rnd.answer.lower().replace(' ', '_')}.jpg"
        if photo_path.exists() and photo_path.stat().st_size > 5000:
            try:
                answer_images[i] = Image.open(photo_path).convert("RGBA")
            except Exception:
                pass
        else:
            try:
                # Use category-aware search query to get the right photo
                search_query = f"{rnd.answer} {search_hint}".strip()
                print(f"[EMOJI QUIZ]   Searching Pexels: '{search_query}'")
                result = fetch_photo(search_query, photo_path, orientation="square")
                if result and result.exists():
                    answer_images[i] = Image.open(result).convert("RGBA")
            except Exception as e:
                print(f"[EMOJI QUIZ]   Photo failed for {rnd.answer}: {e}")

    print(f"[EMOJI QUIZ]   Got {len(answer_images)}/{len(emoji_pack.rounds)} answer images")

    # ================================================================
    # Step 3: Render video
    # ================================================================
    video_path = output_dir / "video.mp4"

    if video_path.exists() and video_path.stat().st_size > 100000:
        print(f"[EMOJI QUIZ] Step 3: CACHED video.mp4 "
              f"({video_path.stat().st_size / 1024 / 1024:.1f} MB) -- skipping render")
    else:
        print("[EMOJI QUIZ] Step 3: Rendering video...")
        assemble_emoji_quiz(emoji_pack, audio_path, video_path,
                             narration_pack=narr_pack,
                             answer_images=answer_images)

    # ================================================================
    # Step 4: Generate thumbnail (reuse existing or generate simple one)
    # ================================================================
    thumb_path = output_dir / "thumbnail.png"
    if not (thumb_path.exists() and thumb_path.stat().st_size > 5000):
        print("[EMOJI QUIZ] Step 4: Generating thumbnail...")
        _generate_emoji_thumbnail(emoji_pack, thumb_path)
    else:
        print("[EMOJI QUIZ] Step 4: CACHED thumbnail.png — skipping")

    # ================================================================
    # Step 5: Generate metadata
    # ================================================================
    platforms = ("youtube", "tiktok", "instagram", "facebook")
    meta_paths = [output_dir / f"metadata_{p}.json" for p in platforms]
    if all(p.exists() for p in meta_paths):
        print("[EMOJI QUIZ] Step 5: CACHED metadata — skipping")
    else:
        print("[EMOJI QUIZ] Step 5: Generating metadata...")
        for platform in platforms:
            meta_file = output_dir / f"metadata_{platform}.json"
            if meta_file.exists():
                continue
            try:
                meta = generate_metadata(
                    # Wrap emoji pack as a QuizPack-like object for metadata gen
                    _emoji_to_quiz_pack(emoji_pack), platform)
                save_metadata(meta, meta_file)
            except RuntimeError as e:
                print(f"[EMOJI QUIZ]   SKIPPED {platform} metadata ({e})")
                break

    print(f"[EMOJI QUIZ] Pipeline complete! Video: {video_path}")
    print(f"[EMOJI QUIZ] Format: emoji, Duration: ~{total_duration:.0f}s")
    return video_path


def _emoji_to_quiz_pack(emoji_pack: EmojiQuizPack) -> QuizPack:
    """# Convert EmojiQuizPack to QuizPack for metadata generation."""
    pack = QuizPack(category=emoji_pack.category)
    for r in emoji_pack.rounds:
        clues = " + ".join(r.emoji_clues)
        pack.rounds.append(QuizRound(
            answer=r.answer,
            hint_question=f"Emoji clues: {clues}",
            fun_fact=r.fun_fact,
            difficulty=r.difficulty,
            image_prompt="",
        ))
    return pack


def _generate_emoji_thumbnail(emoji_pack: EmojiQuizPack,
                               output_path: Path) -> None:
    """
    # Generate a simple thumbnail for emoji quiz videos.
    # Shows 2-3 emoji from the first round + "GUESS THE [CATEGORY]" text.
    # Monkey Quiz-style purple gradient background.
    """
    from PIL import Image, ImageDraw
    w, h = 1920, 1080

    # --- Purple gradient background ---
    c1 = config.EMOJI_BG_GRADIENT_TOP
    c2 = config.EMOJI_BG_GRADIENT_BOTTOM
    import numpy as np
    ratios = np.linspace(0, 1, h, dtype=np.float32).reshape(-1, 1)
    gradient = np.array(c1, dtype=np.float32) * (1 - ratios) + np.array(c2, dtype=np.float32) * ratios
    gradient = np.clip(gradient, 0, 255).astype(np.uint8)
    arr = np.broadcast_to(gradient[:, np.newaxis, :], (h, w, 3)).copy()
    thumb = Image.fromarray(arr)
    draw = ImageDraw.Draw(thumb)

    # --- Title text ---
    cat_info = config.EMOJI_CATEGORIES.get(emoji_pack.category, {})
    display = cat_info.get("display", emoji_pack.category.upper())
    title_color = cat_info.get("title_color", (255, 215, 0))

    from frame_composer import _get_font
    title_font = _get_font(90, bold=True)
    draw.text((w // 2, 120), "GUESS THE", fill=(255, 255, 255),
              anchor="mm", font=title_font)
    cat_font = _get_font(120, bold=True)
    draw.text((w // 2, 240), display, fill=title_color,
              anchor="mm", font=cat_font)
    sub_font = _get_font(60, bold=True)
    draw.text((w // 2, 340), "BY EMOJI", fill=(255, 255, 255, 200),
              anchor="mm", font=sub_font)

    # --- Show emoji from first few rounds as sticker images ---
    from emoji_renderer import get_emoji_image
    if emoji_pack.rounds:
        clues = emoji_pack.rounds[0].emoji_clues
        emoji_size = 160
        total_w = len(clues) * emoji_size + (len(clues) - 1) * 40
        start_x = (w - total_w) // 2
        y_pos = int(h * 0.55) - emoji_size // 2
        for ci, clue_char in enumerate(clues):
            eimg = get_emoji_image(clue_char, emoji_size, sticker=True)
            if eimg:
                x = start_x + ci * (emoji_size + 40)
                thumb.paste(eimg, (x, y_pos), eimg)

    # --- Round count ---
    count_font = _get_font(50, bold=True)
    draw.text((w // 2, int(h * 0.80)),
              f"{len(emoji_pack.rounds)} ROUNDS",
              fill=(255, 215, 0), anchor="mm", font=count_font)

    thumb.save(str(output_path), "PNG")
    print(f"[EMOJI QUIZ] Thumbnail saved: {output_path.name}")


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
                        choices=["short", "long", "mega", "speed", "emoji"],
                        help="Video format: short (66s), long (~10min), mega (~15min), speed (~16min), emoji (~6min)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory path")

    args = parser.parse_args()
    output_dir = Path(args.output) if args.output else None
    run_pipeline(category=args.category, num_rounds=args.rounds,
                  output_dir=output_dir, video_format=args.format)
