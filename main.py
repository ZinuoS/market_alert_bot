"""
main.py — entry point
Runs two loops in parallel:
  1. Scheduler   → fires analysis + push at configured session times
  2. News watcher → polls every 2 min, fires breaking-news push on new stories
"""

import os
import sys
import logging
import threading
import time
from datetime import datetime

import schedule
from dotenv import load_dotenv

import collector
import analyst
import notifier
import tracker

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "market_alert.log")),
    ],
)
log = logging.getLogger("main")


# ── Load env ──────────────────────────────────────────────────────────────────
load_dotenv()

REQUIRED = ["ANTHROPIC_API_KEY", "NTFY_TOPIC"]
for key in REQUIRED:
    if not os.environ.get(key):
        log.error(f"Missing env var: {key}. Copy .env.example to .env and fill it in.")
        sys.exit(1)

BREAKING_THRESHOLD = int(os.environ.get("BREAKING_NEWS_THRESHOLD", 3))
INDEX_THRESHOLD    = float(os.environ.get("INDEX_MOVE_THRESHOLD", 0.8))


# ── Core jobs ─────────────────────────────────────────────────────────────────

def run_scheduled_update(session_name: str):
    """Collect data → analyze → push. Called by the scheduler."""
    log.info(f"▶ Scheduled update: {session_name}")
    try:
        market_data = collector.get_market_data()
        headlines   = collector.get_headlines()
        analysis    = analyst.analyze(session_name, market_data, headlines)
        notifier.send_scheduled(analysis)
        log.info(f"✓ {session_name} update sent. Direction: {analysis['direction']} ({analysis['confidence']}/10)")
    except Exception as e:
        log.error(f"Scheduled update failed ({session_name}): {e}", exc_info=True)


def check_breaking_news():
    """
    Poll feeds, filter to only unseen headlines.
    If enough new headlines or a big index move → send breaking alert.
    Called every 2 minutes by the news watcher loop.
    """
    try:
        headlines   = collector.get_headlines(max_per_feed=5)
        new_stories = tracker.filter_new(headlines)
        big_moves   = collector.detect_big_moves(
            collector.get_market_data(), threshold=INDEX_THRESHOLD
        )

        if len(new_stories) >= BREAKING_THRESHOLD or big_moves:
            log.info(
                f"Breaking trigger: {len(new_stories)} new headlines, "
                f"{len(big_moves)} big moves"
            )
            notifier.send_breaking(
                headlines  = [h["title"] for h in new_stories],
                big_moves  = big_moves,
            )
        else:
            log.debug(f"No breaking trigger ({len(new_stories)} new headlines)")
    except Exception as e:
        log.error(f"Breaking news check failed: {e}", exc_info=True)


# ── Scheduler setup ───────────────────────────────────────────────────────────

def setup_schedule():
    times = {
        os.environ.get("SCHEDULE_ASIA_WRAP",  "05:30"): "Asia Wrap",
        os.environ.get("SCHEDULE_EU_OPEN",    "07:30"): "EU Open",
        os.environ.get("SCHEDULE_US_OPEN",    "09:25"): "US Market Open",
        os.environ.get("SCHEDULE_US_CLOSE",   "16:05"): "US Close / EOD",
    }
    for t, label in times.items():
        schedule.every().day.at(t).do(run_scheduled_update, session_name=label)
        log.info(f"Scheduled: {label} at {t}")


# ── Background news-watcher thread ────────────────────────────────────────────

def news_watcher_loop():
    """Runs forever in a daemon thread, checking for breaking news every 2 min."""
    log.info("News watcher started (polling every 2 min)")
    while True:
        check_breaking_news()
        time.sleep(120)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Market Alert System starting up")
    log.info(f"  Ntfy topic : {os.environ['NTFY_TOPIC']}")
    log.info(f"  Breaking   : ≥{BREAKING_THRESHOLD} new headlines or ≥{INDEX_THRESHOLD}% index move")
    log.info("=" * 60)

    # Send a test ping immediately so you know it's working
    notifier.send_test()

    # Set up the daily schedule
    setup_schedule()

    # Kick off the breaking-news watcher in the background
    watcher = threading.Thread(target=news_watcher_loop, daemon=True)
    watcher.start()

    # Optional: run the US Open update immediately if --now flag passed
    if "--now" in sys.argv:
        log.info("--now flag detected, running immediate update...")
        run_scheduled_update("Manual Test")

    # Main loop: run pending scheduled jobs
    log.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Shutting down.")


if __name__ == "__main__":
    main()
