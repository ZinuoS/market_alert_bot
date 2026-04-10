"""
test_scrape.py — tests data collection only (no Claude API, no Ntfy).
Run this to verify market data + RSS feeds work without spending API credits.

Usage:
    python3 test_scrape.py
"""

import sys
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("test_scrape")

load_dotenv()

import collector

# ── 1. Market data ────────────────────────────────────────────────────────────
print("\n── Step 1: Fetching market data ──")
market_data = collector.get_market_data()
if not market_data:
    print("  ✗ No market data returned (markets might be closed or yfinance issue)")
    sys.exit(1)
for label, data in market_data.items():
    print(f"  {label}: {data['display']}")
print(f"\n  ✓ {len(market_data)} tickers fetched")

# ── 2. Big move detection ─────────────────────────────────────────────────────
print("\n── Step 2: Big move detection (threshold = 0% to show all) ──")
moves = collector.detect_big_moves(market_data, threshold=0.0)
for m in moves:
    print(f"  → {m}")
print(f"  ✓ {len(moves)} moves detected")

# ── 3. RSS headlines ──────────────────────────────────────────────────────────
print("\n── Step 3: Fetching headlines ──")
headlines = collector.get_headlines(max_per_feed=4)
if not headlines:
    print("  ✗ No headlines returned (RSS feeds may be blocked on your network)")
    sys.exit(1)
print(f"  ✓ {len(headlines)} headlines fetched\n")
for h in headlines:
    print(f"  [{h['source']}] {h['title'][:90]}")

print("\n✅ Scraping works. Claude API and Ntfy were not called.")
