"""
Free-to-run version — no Claude API needed.
Formats market snapshots directly from raw data and pushes them via ntfy.

Usage:
    python3 main_local.py           # start scheduler + breaking news watcher
    python3 main_local.py --now     # same, but also fires one update immediately
    python3 main_local.py --pause   # silence all notifications (no restart needed)
    python3 main_local.py --resume  # turn them back on
"""

import os
import sys
import logging
import threading
import time
from datetime import datetime, date

import schedule
import pytz
from dotenv import load_dotenv

import collector
import notifier
import tracker

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
log = logging.getLogger("main_local")

load_dotenv()

if not os.environ.get("NTFY_TOPIC"):
    log.error("Missing NTFY_TOPIC in .env — copy .env.example and fill it in")
    sys.exit(1)

BREAKING_THRESHOLD = int(os.environ.get("BREAKING_NEWS_THRESHOLD", 3))
INDEX_THRESHOLD    = float(os.environ.get("INDEX_MOVE_THRESHOLD", 1.5))
BREAKING_COOLDOWN  = int(os.environ.get("BREAKING_COOLDOWN_MIN", 30)) * 60

# These track breaking-news state across poll cycles.
# All in-memory — resets if the process restarts, which is fine.
_alerted_moves: set   = set()
_last_alert_day: date = None
_last_alert_time: float = 0.0

# Subset of tickers shown in scheduled updates — full list is in collector.py
SESSION_TICKERS = [
    "S&P 500", "Nasdaq", "Dow", "VIX",
    "FTSE 100", "DAX", "Nikkei", "Hang Seng",
    "Gold", "Oil (WTI)", "BTC", "10Y Yield",
]


def format_update(session_name: str, market_data: dict, headlines: list[dict]) -> dict:
    et  = pytz.timezone("America/New_York")
    now = datetime.now(et).strftime("%b %d %I:%M %p ET")

    lines = [f"{session_name}  —  {now}", ""]

    for label in SESSION_TICKERS:
        if label in market_data:
            lines.append(f"{label}: {market_data[label]['display']}")

    moves = collector.detect_big_moves(market_data, threshold=INDEX_THRESHOLD)
    if moves:
        lines += ["", "Notable moves:"]
        for m in moves:
            lines.append(f"  {m}")

    if headlines:
        lines += ["", "Headlines:"]
        for h in headlines[:6]:
            lines.append(f"  • {h['title'][:85]}")

    body = "\n".join(lines)

    # Rough direction signal based on S&P. Not sophisticated — just enough
    # to set the notification emoji. main.py uses Claude for a real read.
    sp = market_data.get("S&P 500", {}).get("change_pct", 0)
    if sp > 0.3:
        direction, confidence = "UP", 6
    elif sp < -0.3:
        direction, confidence = "DOWN", 6
    else:
        direction, confidence = "MIXED", 5

    return {
        "session":       session_name,
        "direction":     direction,
        "confidence":    confidence,
        "full_analysis": body,
    }


def run_scheduled_update(session_name: str):
    log.info(f"▶ {session_name}")
    try:
        market_data = collector.get_market_data()
        headlines   = collector.get_headlines()
        update      = format_update(session_name, market_data, headlines)
        notifier.send_scheduled(update)
        log.info(f"✓ {session_name} sent ({update['direction']})")
    except Exception as e:
        log.error(f"Scheduled update failed ({session_name}): {e}", exc_info=True)


def check_breaking_news():
    global _alerted_moves, _last_alert_day, _last_alert_time
    try:
        # New day = fresh slate. Yesterday's big moves aren't news anymore.
        today = date.today()
        if today != _last_alert_day:
            _alerted_moves  = set()
            _last_alert_day = today

        # Hard cooldown — even if something new triggers, wait this long between pushes
        if time.time() - _last_alert_time < BREAKING_COOLDOWN:
            mins_left = int((BREAKING_COOLDOWN - (time.time() - _last_alert_time)) / 60)
            log.debug(f"Breaking cooldown: {mins_left} min remaining")
            return

        headlines   = collector.get_headlines(max_per_feed=5)
        new_stories = tracker.filter_new(headlines)

        all_moves = collector.detect_big_moves(
            collector.get_market_data(), threshold=INDEX_THRESHOLD
        )
        # Only moves we haven't already sent an alert for today
        new_moves = [m for m in all_moves if m not in _alerted_moves]

        if len(new_stories) >= BREAKING_THRESHOLD or new_moves:
            log.info(f"Breaking: {len(new_stories)} new headlines, {len(new_moves)} new moves")
            notifier.send_breaking(
                headlines = [h["title"] for h in new_stories],
                big_moves = new_moves,
            )
            _alerted_moves.update(new_moves)
            _last_alert_time = time.time()
        else:
            log.debug(f"No trigger ({len(new_stories)} new headlines, {len(new_moves)} new moves)")
    except Exception as e:
        log.error(f"Breaking news check failed: {e}", exc_info=True)


def setup_schedule():
    times = {
        os.environ.get("SCHEDULE_ASIA_WRAP", "05:30"): "Asia Wrap",
        os.environ.get("SCHEDULE_EU_OPEN",   "07:30"): "EU Open",
        os.environ.get("SCHEDULE_US_OPEN",   "09:25"): "US Market Open",
        os.environ.get("SCHEDULE_US_CLOSE",  "16:05"): "US Close / EOD",
    }
    for t, label in times.items():
        schedule.every().day.at(t).do(run_scheduled_update, session_name=label)
        log.info(f"  {label} at {t} ET")


def news_watcher_loop():
    log.info("News watcher started (polling every 2 min)")
    while True:
        check_breaking_news()
        time.sleep(120)


def main():
    if "--pause" in sys.argv:
        notifier.pause()
        return
    if "--resume" in sys.argv:
        notifier.resume()
        return

    log.info("=" * 55)
    log.info("Market Alert starting (no-API mode)")
    log.info(f"  Topic    : {os.environ['NTFY_TOPIC']}")
    log.info(f"  Breaking : ≥{BREAKING_THRESHOLD} headlines or ≥{INDEX_THRESHOLD}% new move, cooldown {BREAKING_COOLDOWN//60} min")
    log.info("=" * 55)

    notifier.send_test()
    setup_schedule()

    watcher = threading.Thread(target=news_watcher_loop, daemon=True)
    watcher.start()

    if "--now" in sys.argv:
        run_scheduled_update("Manual Update")

    log.info("Running. Ctrl+C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        log.info("Shutting down.")


if __name__ == "__main__":
    main()
