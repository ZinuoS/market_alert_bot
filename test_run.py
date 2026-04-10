"""
test_run.py — validates your setup end-to-end without waiting for a schedule.
Run this first to confirm everything works before starting main.py.

Usage:
    python test_run.py
"""

import os
import sys
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("test")

load_dotenv()

# ── 1. Check env vars ─────────────────────────────────────────────────────────
print("\n── Step 1: Checking environment variables ──")
for key in ["ANTHROPIC_API_KEY", "NTFY_TOPIC"]:
    val = os.environ.get(key, "")
    if not val or "your" in val.lower():
        print(f"  ✗ {key} is missing or still a placeholder")
        sys.exit(1)
    masked = val[:8] + "..." if len(val) > 8 else val
    print(f"  ✓ {key} = {masked}")

import collector, analyst, notifier, tracker

# ── 2. Market data ────────────────────────────────────────────────────────────
print("\n── Step 2: Fetching market data ──")
market_data = collector.get_market_data()
if not market_data:
    print("  ✗ No market data returned (markets might be closed, yfinance issue?)")
    sys.exit(1)
for label, data in list(market_data.items())[:5]:
    print(f"  ✓ {label}: {data['display']}")
print(f"  … {len(market_data)} tickers total")

# ── 3. Big move detection ─────────────────────────────────────────────────────
print("\n── Step 3: Big move detection ──")
moves = collector.detect_big_moves(market_data, threshold=0.0)  # 0% → catches everything
print(f"  Moves detected at 0% threshold: {len(moves)}")
for m in moves[:3]:
    print(f"  → {m}")

# ── 4. Headlines ──────────────────────────────────────────────────────────────
print("\n── Step 4: Fetching headlines ──")
headlines = collector.get_headlines(max_per_feed=3)
if not headlines:
    print("  ✗ No headlines (RSS feeds may be blocked on your network)")
else:
    print(f"  ✓ {len(headlines)} headlines fetched")
    for h in headlines[:3]:
        print(f"  [{h['source']}] {h['title'][:80]}")

# ── 5. Dedup tracker ─────────────────────────────────────────────────────────
print("\n── Step 5: Deduplication tracker ──")
new1 = tracker.filter_new(headlines)
new2 = tracker.filter_new(headlines)   # second call should return 0
print(f"  ✓ First pass:  {len(new1)} new headlines")
print(f"  ✓ Second pass: {len(new2)} new headlines (should be 0)")

# ── 6. Claude analysis ────────────────────────────────────────────────────────
print("\n── Step 6: Claude analysis (this costs ~1 API call) ──")
try:
    analysis = analyst.analyze("Test Session", market_data, headlines)
    print(f"  ✓ Direction:   {analysis['direction']}")
    print(f"  ✓ Confidence:  {analysis['confidence']}/10")
    print(f"  ✓ Rationale:   {analysis['rationale'][:100]}")
    print(f"\n  Full response preview:\n")
    for line in analysis["full_analysis"].splitlines()[:8]:
        print(f"    {line}")
except Exception as e:
    print(f"  ✗ Claude error: {e}")
    sys.exit(1)

# ── 7. Ntfy push ──────────────────────────────────────────────────────────────
print("\n── Step 7: Sending test push to Ntfy ──")
ok = notifier.send_test()
if ok:
    print(f"  ✓ Push sent! Check the Ntfy app on your phone (topic: {os.environ['NTFY_TOPIC']})")
else:
    print("  ✗ Ntfy send failed — check your NTFY_TOPIC and network")

print("\n── Step 8: Sending a full scheduled update ──")
ok2 = notifier.send_scheduled(analysis)
if ok2:
    print("  ✓ Full analysis push sent!")

print("\n✅ All tests passed. Run `python main.py` to start the live system.")
print("   Add --now flag to also trigger an immediate update: `python main.py --now`\n")
