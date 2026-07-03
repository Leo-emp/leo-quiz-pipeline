# scheduler.py
# ============================================================
# Scheduling for automated daily/weekly video generation.
# Supports local cron via APScheduler and manual triggers.
# Daily: generate one short-form quiz video
# Weekly: compile long-form video from past 7 days
# ============================================================
import argparse
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

import config
from main import run_pipeline
from compiler import compile_longform


def daily_job():
    """# Generate one short-form quiz video for today's category."""
    print(f"\n{'='*60}")
    print(f"[SCHEDULER] Daily job started at {datetime.now()}")
    print(f"{'='*60}")
    try:
        video_path = run_pipeline()
        print(f"[SCHEDULER] Daily job complete: {video_path}")
    except Exception as e:
        print(f"[SCHEDULER] Daily job failed: {e}")
        import traceback
        traceback.print_exc()


def weekly_job():
    """# Compile weekly long-form video from past 7 days of shorts."""
    print(f"\n{'='*60}")
    print(f"[SCHEDULER] Weekly job started at {datetime.now()}")
    print(f"{'='*60}")
    try:
        video_path = compile_longform()
        print(f"[SCHEDULER] Weekly job complete: {video_path}")
    except Exception as e:
        print(f"[SCHEDULER] Weekly job failed: {e}")
        import traceback
        traceback.print_exc()


def start_scheduler():
    """# Start the APScheduler with daily and weekly cron jobs."""
    scheduler = BlockingScheduler()

    # Daily at 6:00 AM UTC — generates one short-form video
    scheduler.add_job(daily_job, "cron", hour=6, minute=0, id="daily_quiz")

    # Weekly on Sunday at 8:00 AM UTC — compiles long-form video
    scheduler.add_job(weekly_job, "cron", day_of_week="sun", hour=8, minute=0,
                      id="weekly_compilation")

    print("[SCHEDULER] Leo Quiz scheduler started")
    print("[SCHEDULER] Daily: 6:00 AM UTC | Weekly: Sunday 8:00 AM UTC")
    print("[SCHEDULER] Press Ctrl+C to stop")

    scheduler.start()


if __name__ == "__main__":
    # CLI: run a job immediately or start the scheduler
    parser = argparse.ArgumentParser(description="Leo Quiz Scheduler")
    parser.add_argument("--now", choices=["short", "long"],
                        help="Run a job immediately instead of scheduling")
    args = parser.parse_args()

    if args.now == "short":
        daily_job()
    elif args.now == "long":
        weekly_job()
    else:
        start_scheduler()
