# Market Alert System

Push notifications for traders — live market snapshots and breaking news, straight to your phone. No app, no dashboard, no subscription. Just a ping when something moves.

Built on [ntfy.sh](https://ntfy.sh) (free push notifications), yfinance for prices, and public RSS feeds for headlines.

---

## What it sends

| Trigger | Time (ET) | What's in it |
|---|---|---|
| Asia Wrap | 5:30 AM | Overnight recap, Asia close |
| EU Open | 7:30 AM | European open, macro setup |
| US Open | 9:25 AM | Pre-market snapshot |
| US Close | 4:05 PM | EOD recap |
| Breaking | Any time | New headlines or a major index move |

---

## Two modes

### `main_local.py` — free, no API key

Raw prices, notable moves, and headlines. Runs entirely on yfinance + RSS.

```
📈 US Market Open | UP (confidence 6/10)

US Market Open  —  Apr 09 09:25 AM ET

S&P 500: 6,824.66 ▲0.62%
Nasdaq: 22,822.42 ▲0.83%
Dow: 48,185.80 ▲0.58%
VIX: 19.49 ▼7.37%
FTSE 100: 10,608.90 ▲2.51%
DAX: 24,080.63 ▲5.06%
Nikkei: 56,308.42 ▲5.39%
Hang Seng: 25,893.02 ▲3.09%
Gold: 4,785.30 ▲0.75%
Oil (WTI): 98.51 ▲4.34%
10Y Yield: 4.29 ▲0.05%
BTC: 71,812.37 ▲0.97%

Notable moves:
  VIX is down 7.37% (19.49 ▼7.37%)
  DAX is up 5.06% (24,080.63 ▲5.06%)
  Nikkei is up 5.39% (56,308.42 ▲5.39%)
  Oil (WTI) is up 4.34% (98.51 ▲4.34%)

Headlines:
  • North Sea oil prices hit record high as Iran keeps hold over Hormuz
  • S&P 500 posts longest winning streak since October on ceasefire optimism
  • Netflix, big banks face moment of truth as Iran cease-fire rally meets earnings
```

### `main.py` — Claude-powered analysis (~$0.01/day)

Same data, but Claude writes the actual read. Prompt is tuned to sound like a desk trader, not a news anchor.

```
📈 Test — US Session | UP (confidence 6/10)

SUMMARY
US equities rallying hard (+0.6-0.8%) on risk-on flows while VIX craters 7.4%.
Oil surging 4.5% on Iran/Hormuz tensions and ceasefire uncertainty. Europe flat
to down; Asia mixed. Flight-to-safety narrative breaking down.

KEY THEMES
• Oil rally driving energy sector lift; geopolitical premium real and sticky
• Fed-sensitive tech leading (Nasdaq +0.83%) suggests rates expectations softening
• VIX implosion = vol sellers and systematic deleveraging kicking in
• Gold flat-to-up despite DXY weakness = hedge positioning, not USD selling

WATCH
Oil print if it breaks through $100 (momentum trigger for energy rotations).
Iran/Trump rhetoric escalation — any concrete military action will rip risk assets.

DIRECTION: UP | CONFIDENCE: 6 | RATIONALE: Short-term momentum strong but riding
oil rally and geopolitical premium; mean reversion risk if Hormuz tensions ease.
```

Start with `main_local.py`. Switch to `main.py` if you want the written analysis.

---

## Setup

### Prerequisites
- Python 3.9+
- The [ntfy app](https://ntfy.sh) on your phone (free, iOS + Android)

### 1. Clone and install
```bash
git clone <this-repo>
cd market-alert
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
```

Open `.env` and fill in two things:

- **`NTFY_TOPIC`** — your notification channel name. Make it hard to guess (e.g. `market-john-x7k2q9m`) because anyone who knows it can subscribe to your feed.
- **`ANTHROPIC_API_KEY`** — only needed if you're running `main.py`. Get one at [console.anthropic.com](https://console.anthropic.com).

### 3. Subscribe on your phone
Open the ntfy app → Subscribe → type your `NTFY_TOPIC` exactly as it appears in `.env`.

### 4. Test
```bash
# Test prices and RSS feeds — no API key needed
python3 test_scrape.py

# Full end-to-end test including Claude + a real push to your phone
python3 test_run.py
```

### 5. Run
```bash
python3 main_local.py           # start the scheduler
python3 main_local.py --now     # start + fire one update immediately
```

---

## Keeping it running (macOS)

To survive terminal close and restart on login, use a Launch Agent.

> **Important:** put the project in `~/market-alert/` or `~/Documents/`, not `~/Downloads/`. macOS blocks background services from accessing the Downloads folder.

Create `~/Library/LaunchAgents/com.yourname.market-alert.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.yourname.market-alert</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/yourname/market-alert/main_local.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/yourname/market-alert</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>/Users/yourname/Library/Python/3.9/lib/python/site-packages</string>
        <key>HOME</key>
        <string>/Users/yourname</string>
        <key>PATH</key>
        <string>/usr/bin:/bin</string>
    </dict>

    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>

    <key>StandardOutPath</key>
    <string>/Users/yourname/market-alert/logs/market_alert.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/yourname/market-alert/logs/market_alert.log</string>
</dict>
</plist>
```

Replace both instances of `yourname` with your actual macOS username (`echo $USER` if unsure). Then:

```bash
launchctl load ~/Library/LaunchAgents/com.yourname.market-alert.plist

# Confirm it started (should show a PID, not "-")
launchctl list | grep market-alert
```

To stop it:
```bash
launchctl unload ~/Library/LaunchAgents/com.yourname.market-alert.plist
```

> The service won't fire while your Mac is asleep — notifications will resume when it wakes up.

---

## Controls

```bash
# Silence notifications without stopping the process (useful on holidays)
python3 main_local.py --pause
python3 main_local.py --resume

# Watch the live log
tail -f ~/market-alert/logs/market_alert.log
```

---

## Tuning

All thresholds are in `.env`:

| Variable | Default | What it does |
|---|---|---|
| `INDEX_MOVE_THRESHOLD` | 1.5 | % move on any index to count as significant |
| `BREAKING_NEWS_THRESHOLD` | 3 | New headlines needed to trigger a breaking alert |
| `BREAKING_COOLDOWN_MIN` | 30 | Minutes to wait between breaking alerts |

Getting too many alerts? Raise the threshold values. Missing moves you care about? Lower them. The breaking alert also deduplicates big moves — once it fires for DAX +5%, it won't fire for that same move again until the next day.

---

## Upgrading to Claude analysis

Switch from `main_local.py` to `main.py` — same scheduler, same structure, but `analyst.py` sends the data to Claude and gets back a written narrative.

The model is set in `analyst.py`. Haiku is the cheapest option and fast enough for this. Swap in `claude-sonnet-4-6` if you want richer analysis and don't mind spending a bit more.

```bash
python3 main.py --now   # test immediately
```

---

## Project structure

```
market-alert/
├── main_local.py    # scheduler without Claude — start here
├── main.py          # full version with Claude analysis
├── collector.py     # yfinance prices + RSS feed fetching
├── analyst.py       # Claude API prompt + response parsing
├── notifier.py      # ntfy push formatting + sending
├── tracker.py       # headline dedup so stories never double-send
├── test_scrape.py   # quick sanity check: prices + headlines, no API
├── test_run.py      # full end-to-end test with Claude + real push
├── .env             # your secrets — never commit this
├── .env.example     # template, safe to commit
├── requirements.txt
├── data/            # auto-created — stores seen headline hashes
└── logs/            # auto-created — market_alert.log lives here
```
