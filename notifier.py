import requests
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# Touching this file pauses all outgoing notifications without restarting the process.
# Use main_local.py --pause / --resume rather than managing it by hand.
PAUSE_FILE = Path(__file__).parent / ".paused"


def is_paused() -> bool:
    return PAUSE_FILE.exists()

def pause():
    PAUSE_FILE.touch()
    log.info("Notifications paused — run with --resume to re-enable")

def resume():
    PAUSE_FILE.unlink(missing_ok=True)
    log.info("Notifications resumed")


DIRECTION_EMOJI = {
    "UP":       "📈",
    "DOWN":     "📉",
    "SIDEWAYS": "➡️",
    "MIXED":    "↕️",
    "UNKNOWN":  "❓",
}

DIRECTION_TAG = {
    "UP":       "chart_with_upwards_trend",
    "DOWN":     "chart_with_downwards_trend",
    "SIDEWAYS": "arrow_right",
    "MIXED":    "arrows_counterclockwise",
    "UNKNOWN":  "question",
}

# ntfy's JSON API wants priority as an integer, not a string
PRIORITY_MAP = {
    "urgent":  5,
    "high":    4,
    "default": 3,
    "low":     2,
}


def _confidence_to_priority(confidence: int) -> str:
    if confidence >= 8:
        return "high"
    if confidence >= 5:
        return "default"
    return "low"


def _format_scheduled_message(analysis: dict) -> tuple[str, str]:
    direction = analysis.get("direction", "UNKNOWN")
    emoji     = DIRECTION_EMOJI.get(direction, "❓")
    conf      = analysis.get("confidence", 0)
    session   = analysis.get("session", "Update")
    title = f"{emoji} {session} | {direction} (confidence {conf}/10)"
    body  = analysis.get("full_analysis", analysis.get("summary", "No data."))
    return title, body


def _format_breaking_message(headlines: list[str], big_moves: list[str]) -> tuple[str, str]:
    title = "🚨 Breaking Market Alert"
    lines = []
    if big_moves:
        lines.append("MOVES:")
        lines.extend(f"  {m}" for m in big_moves)
    if headlines:
        lines.append("\nNEWS:")
        lines.extend(f"  • {h}" for h in headlines[:5])
    body = "\n".join(lines) if lines else "Significant market activity detected."
    return title, body


def send_scheduled(analysis: dict) -> bool:
    title, body = _format_scheduled_message(analysis)
    direction   = analysis.get("direction", "UNKNOWN")
    confidence  = analysis.get("confidence", 0)
    return _send(
        title    = title,
        body     = body,
        priority = _confidence_to_priority(confidence),
        tags     = [DIRECTION_TAG.get(direction, "question"), "money_with_wings"],
    )


def send_breaking(headlines: list[str], big_moves: list[str]) -> bool:
    title, body = _format_breaking_message(headlines, big_moves)
    return _send(
        title    = title,
        body     = body,
        priority = "urgent",
        tags     = ["rotating_light", "chart_with_upwards_trend"],
    )


def send_test() -> bool:
    return _send(
        title    = "✅ Market Alert System — online",
        body     = "Backend is running. You'll receive scheduled updates and breaking news alerts here.",
        priority = "default",
        tags     = ["white_check_mark"],
    )


def _send(title: str, body: str, priority: str = "default", tags: list[str] = None) -> bool:
    if is_paused():
        log.info(f"Notifications paused — skipped: {title[:60]}")
        return True

    topic  = os.environ["NTFY_TOPIC"]
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

    # Sending as JSON instead of headers because Python's http.client encodes
    # headers as latin-1, which breaks on emoji in the Title field.
    payload = {
        "topic":    topic,
        "title":    title,
        "message":  body,
        "priority": PRIORITY_MAP.get(priority, 3),
        "tags":     tags or [],
    }

    try:
        r = requests.post(f"{server}/", json=payload, timeout=10)
        r.raise_for_status()
        log.info(f"Ntfy sent: {title[:60]}")
        return True
    except requests.RequestException as e:
        log.error(f"Ntfy send failed: {e}")
        return False
