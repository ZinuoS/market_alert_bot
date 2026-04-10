import anthropic
import logging
import os

log = logging.getLogger(__name__)
_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def _build_prompt(session: str, market_data: dict, headlines: list[dict]) -> str:
    market_block = "\n".join(
        f"  {label}: {data['display']}"
        for label, data in market_data.items()
    )
    headline_block = "\n".join(
        f"  [{h['source']}] {h['title']}"
        for h in headlines[:15]  # 15 is roughly the token sweet spot before it gets noisy
    )

    return f"""You are a senior macro trader writing a fast, sharp morning/session update for a prop desk.

SESSION: {session}

MARKET DATA:
{market_block}

TOP HEADLINES:
{headline_block}

Write a concise update in exactly this format — no extra commentary:

SUMMARY (2-3 sentences max): <what's actually happening across markets right now>

KEY THEMES: <bullet list of 2-4 themes driving price action, one line each>

WATCH: <1-2 specific things to watch in the next session>

DIRECTION: <UP / DOWN / SIDEWAYS / MIXED> | CONFIDENCE: <1-10> | RATIONALE: <one sentence>

Be direct. No hedging phrases like "it's important to note" or "as always". Write like you're texting a trader who has 30 seconds."""


def analyze(session: str, market_data: dict, headlines: list[dict]) -> dict:
    prompt = _build_prompt(session, market_data, headlines)

    try:
        response = _get_client().messages.create(
            # Haiku is fast and cheap (~$0.01/day for 4 daily updates).
            # Swap in claude-sonnet-4-6 if you want noticeably better analysis.
            model      = "claude-haiku-4-5-20251001",
            max_tokens = 500,
            messages   = [{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        log.info(f"Claude responded ({len(raw)} chars)")
    except Exception as e:
        log.error(f"Claude API error: {e}")
        raise

    # Parse the structured DIRECTION line out of the free-text response.
    # This breaks if Claude ignores the format — doesn't happen often but worth knowing.
    direction  = "UNKNOWN"
    confidence = 0
    rationale  = ""
    summary    = ""

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("DIRECTION:"):
            parts = line.split("|")
            direction = parts[0].replace("DIRECTION:", "").strip()
            if len(parts) > 1:
                conf_part = parts[1].replace("CONFIDENCE:", "").strip()
                try:
                    confidence = int("".join(c for c in conf_part if c.isdigit()))
                except ValueError:
                    confidence = 0
            if len(parts) > 2:
                rationale = parts[2].replace("RATIONALE:", "").strip()
        if line.startswith("SUMMARY"):
            after = line.split(":", 1)
            if len(after) > 1 and after[1].strip():
                summary = after[1].strip()

    return {
        "session":       session,
        "raw_text":      raw,
        "direction":     direction,
        "confidence":    confidence,
        "rationale":     rationale,
        "summary":       summary or raw[:200],
        "full_analysis": raw,
    }
