import feedparser
import yfinance as yf
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Add, remove, or swap tickers freely — just make sure the yfinance symbol is right.
# Lookup symbols at finance.yahoo.com if you're unsure.
TICKERS = {
    # US
    "S&P 500":   "^GSPC",
    "Nasdaq":    "^IXIC",
    "Dow":       "^DJI",
    "VIX":       "^VIX",
    # Europe
    "FTSE 100":  "^FTSE",
    "DAX":       "^GDAXI",
    "CAC 40":    "^FCHI",
    # Asia
    "Nikkei":    "^N225",
    "Hang Seng": "^HSI",
    "Shanghai":  "000001.SS",
    # Macro / commodities
    "Gold":      "GC=F",
    "Oil (WTI)": "CL=F",
    "DXY":       "DX-Y.NYB",
    "10Y Yield": "^TNX",
    "BTC":       "BTC-USD",
}

# These are free public RSS feeds — no API keys needed.
# Some may occasionally be slow or blocked depending on your network.
RSS_FEEDS = [
    ("Reuters Business",  "https://feeds.reuters.com/reuters/businessNews"),
    ("Reuters Markets",   "https://feeds.reuters.com/reuters/financialMarketsNews"),
    ("BBC Business",      "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("FT",                "https://www.ft.com/rss/home/uk"),
    ("AP Business",       "https://feeds.apnews.com/rss/business"),
    ("MarketWatch",       "https://feeds.marketwatch.com/marketwatch/topstories/"),
]


def get_market_data() -> dict:
    results = {}
    for label, symbol in TICKERS.items():
        try:
            hist = yf.Ticker(symbol).history(period="2d", interval="1d")
            if len(hist) < 2:
                # Market holidays leave gaps — 5d usually has enough rows
                hist = yf.Ticker(symbol).history(period="5d", interval="1d")
            if len(hist) < 2:
                log.warning(f"Not enough data for {label} ({symbol})")
                continue

            prev = hist["Close"].iloc[-2]
            curr = hist["Close"].iloc[-1]
            pct  = (curr - prev) / prev * 100
            arrow = "▲" if pct >= 0 else "▼"

            results[label] = {
                "price":      curr,
                "change_pct": pct,
                "display":    f"{curr:,.2f} {arrow}{abs(pct):.2f}%",
            }
        except Exception as e:
            log.warning(f"Failed to fetch {label}: {e}")
    return results


def get_headlines(max_per_feed: int = 4) -> list[dict]:
    all_headlines = []
    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                all_headlines.append({
                    "title":     entry.get("title", "").strip(),
                    "source":    source_name,
                    "link":      entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            log.warning(f"Feed error ({source_name}): {e}")

    log.info(f"Collected {len(all_headlines)} headlines from {len(RSS_FEEDS)} feeds")
    return all_headlines


def detect_big_moves(market_data: dict, threshold: float = 1.5) -> list[str]:
    # All comparisons are vs yesterday's close, so a move stays "big" all day
    # once it crosses the threshold. The dedup logic in main_local.py
    # makes sure we only alert once per move per day.
    flags = []
    for label, data in market_data.items():
        if abs(data["change_pct"]) >= threshold:
            direction = "up" if data["change_pct"] > 0 else "down"
            flags.append(
                f"{label} is {direction} {abs(data['change_pct']):.2f}% "
                f"({data['display']})"
            )
    return flags
