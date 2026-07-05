# scheduler.py
# ============================================================
# Scheduling for automated daily/weekly video generation.
# Supports local cron via APScheduler and manual triggers.
#
# Daily: generate one short (66s) + one long-form (10min) for today's category
# Weekly: generate a 100-round mega quiz (~15min)
# ============================================================
import argparse
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from main import run_pipeline


def daily_job():
    """# Generate one short + one long-form quiz video for today's category.
    # Both use the same day-of-week category rotation.
    # Short = 6 rounds (66s), Long = 60 rounds (~10min)."""
    print(f"\n{'='*60}")
    print(f"[SCHEDULER] Daily job started at {datetime.now()}")
    print(f"{'='*60}")
    try:
        # Short-form (66s, 6 rounds, 9:16 vertical)
        print("[SCHEDULER] Generating short-form video...")
        short_path = run_pipeline(video_format="short")
        print(f"[SCHEDULER] Short complete: {short_path}")

        # Long-form (10min, 60 rounds, 16:9 landscape — same category)
        print("[SCHEDULER] Generating long-form video...")
        long_path = run_pipeline(video_format="long")
        print(f"[SCHEDULER] Long-form complete: {long_path}")

        print(f"[SCHEDULER] Daily job complete — 2 videos generated")
    except Exception as e:
        print(f"[SCHEDULER] Daily job failed: {e}")
        import traceback
        traceback.print_exc()


def weekly_job():
    """# Generate a mega quiz (100 rounds, 16:9 landscape, ~15 min).
    # Runs weekly — the big event video for maximum watch time."""
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

    # Daily at 6:00 AM UTC — generates one short + one long-form video
    scheduler.add_job(daily_job, "cron", hour=6, minute=0, id="daily_quiz")

    # Weekly on Sunday at 8:00 AM UTC — generates mega quiz (100 rounds)
    scheduler.add_job(weekly_job, "cron", day_of_week="sun", hour=8, minute=0,
                      id="weekly_mega")

    print("[SCHEDULER] Leo Quiz scheduler started")
    print("[SCHEDULER] Daily: 6:00 AM UTC (short + long-form)")
    print("[SCHEDULER] Weekly: Sunday 8:00 AM UTC (mega quiz)")
    print("[SCHEDULER] Press Ctrl+C to stop")

    scheduler.start()


if __name__ == "__main__":
    # CLI: run a job immediately or start the scheduler
    parser = argparse.ArgumentParser(description="Leo Quiz Scheduler")
    parser.add_argument("--now", choices=["short", "long", "mega", "daily"],
                        help="Run a job immediately: short, long, mega, or daily (short+long)")
    args = parser.parse_args()

    if args.now == "short":
        run_pipeline(video_format="short")
    elif args.now == "long":
        run_pipeline(video_format="long")
    elif args.now == "mega":
        weekly_job()
    elif args.now == "daily":
        daily_job()
    else:
        start_scheduler()
