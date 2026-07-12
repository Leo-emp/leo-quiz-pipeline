# scheduler.py
# ============================================================
# Scheduling for automated daily/weekly video generation.
# Supports local cron via APScheduler and manual triggers.
#
# UPGRADED for speed quiz format (top creator pipeline):
# Daily: generate one speed quiz (120 rounds, ~16min) — the main content
# Also generates a short (66s) for Shorts/TikTok/Reels from same category
# Weekly: mega quiz (100 rounds) as the "event" video
#
# Category rotation: Monday-Saturday = 6 categories, Sunday = mixed
# Never-repeat: history.json tracks all used answers + video_log
# ============================================================
import argparse
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from main import run_pipeline


def daily_job():
    """
    # Generate one speed quiz + one short for today's category.
    # Speed quiz = 120 rounds, ~16min, 16:9 — the MAIN daily upload.
    # Short = 6 rounds, 66s, 9:16 — for Shorts/TikTok/Reels reach.
    # Both use day-of-week category rotation for variety.
    """
    print(f"\n{'='*60}")
    print(f"[SCHEDULER] Daily job started at {datetime.now()}")
    print(f"{'='*60}")
    try:
        # Speed quiz — the main daily video (this is what gets millions of views)
        print("[SCHEDULER] Generating speed quiz video (120 rounds)...")
        speed_path = run_pipeline(video_format="speed")
        print(f"[SCHEDULER] Speed quiz complete: {speed_path}")

        # Short-form — for reach on Shorts/TikTok/Reels
        print("[SCHEDULER] Generating short-form video...")
        short_path = run_pipeline(video_format="short")
        print(f"[SCHEDULER] Short complete: {short_path}")

        print(f"[SCHEDULER] Daily job complete — 2 videos generated")
    except Exception as e:
        print(f"[SCHEDULER] Daily job failed: {e}")
        import traceback
        traceback.print_exc()


def weekly_job():
    """# Generate a mega quiz (100 rounds, ~15 min) as the weekly event."""
    print(f"\n{'='*60}")
    print(f"[SCHEDULER] Weekly mega quiz started at {datetime.now()}")
    print(f"{'='*60}")
    try:
        video_path = run_pipeline(video_format="mega")
        print(f"[SCHEDULER] Weekly mega quiz complete: {video_path}")
    except Exception as e:
        print(f"[SCHEDULER] Weekly mega job failed: {e}")
        import traceback
        traceback.print_exc()


def start_scheduler():
    """# Start the APScheduler with daily and weekly cron jobs."""
    scheduler = BlockingScheduler()

    # Daily at 6:00 AM UTC — speed quiz + short
    scheduler.add_job(daily_job, "cron", hour=6, minute=0, id="daily_quiz")

    # Weekly on Sunday at 8:00 AM UTC — mega quiz
    scheduler.add_job(weekly_job, "cron", day_of_week="sun", hour=8, minute=0,
                      id="weekly_mega")

    print("[SCHEDULER] Leo Quiz scheduler started")
    print("[SCHEDULER] Daily: 6:00 AM UTC (speed quiz + short)")
    print("[SCHEDULER] Weekly: Sunday 8:00 AM UTC (mega quiz)")
    print("[SCHEDULER] Press Ctrl+C to stop")

    scheduler.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Leo Quiz Scheduler")
    parser.add_argument("--now", choices=["short", "long", "mega", "speed", "daily"],
                        help="Run a job immediately")
    args = parser.parse_args()

    if args.now == "short":
        run_pipeline(video_format="short")
    elif args.now == "long":
        run_pipeline(video_format="long")
    elif args.now == "mega":
        weekly_job()
    elif args.now == "speed":
        run_pipeline(video_format="speed")
    elif args.now == "daily":
        daily_job()
    else:
        start_scheduler()
