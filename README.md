# Trend Radar

Trend collector: pulls what's getting attention across Hacker News, GitHub,
Dev.to, and RSS feeds, scores it against your own stack keywords, detects
items that are suddenly accelerating, optionally adds a one-line AI "why
this matters to you" angle, and pushes items to Telegram with a tap-to-save
button.

This is Stage 1-2 of the bigger content-agent idea — get the "what's
trending + does it overlap with what I build" signal working and trustworthy
before adding AI writing/posting on top.

## v2 additions

- **Velocity detection** — if an item you already saw gets re-sent because
  its score spiked 50%+ (and by a meaningful absolute amount, to ignore
  tiny-number noise), it's flagged `🚀 BREAKOUT` and jumps to the top of
  the queue. Config: `VELOCITY_GROWTH_THRESHOLD`, `VELOCITY_MIN_ABSOLUTE_DELTA`.
- **AI angles (Gemini)** — a single batched call per run, capped at the top
  `AI_ANGLE_CANDIDATE_COUNT` (15 by default) pending items, generates a
  one-line "why this matters to you" note. Uses Flash-Lite by default for
  cost; override `GEMINI_MODEL` env var if you want Pro's quality instead
  (at meaningfully higher per-call cost — Pro is roughly 10-20x Flash-Lite's
  token price, worth it only if Flash-Lite's angles feel too generic).
- **Save button** — each item now sends as its own Telegram message with a
  "💾 Save" inline button. Tapping it marks the item `saved=1` in the DB
  and edits the message to show "✅ Saved". No server needed — the next
  collector run polls Telegram's `getUpdates` for any taps since the last
  check, using a stored offset so nothing's processed twice.

## Setup

### 1. Create a Telegram bot
1. Message **@BotFather** on Telegram → `/newbot` → follow prompts → copy the token
2. Send any message to your new bot
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
4. Find `"chat":{"id": ...}` in the JSON — that's your chat ID

### 2. Get a Gemini API key (for AI angles)
Grab a key from Google AI Studio. Set `ENABLE_AI_ANGLES = False` in
`config.py` if you'd rather skip this and stay at zero AI cost.

### 3. Local test run
```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
export GEMINI_API_KEY="your-gemini-key"     # optional, skip if AI angles disabled
python collector.py         # fetches + stores new items, generates AI angles
python notify_telegram.py   # processes saves, sends pending items
```

Without the env vars set, `notify_telegram.py` prints what it *would* send
instead of failing — safe to test dry.

### 4. Deploy on GitHub Actions (recommended)
1. Push this repo to GitHub
2. Repo → Settings → Secrets and variables → Actions → add:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `GEMINI_API_KEY` (skip if AI angles disabled)
3. The workflow (`.github/workflows/trend-radar.yml`) runs every 4 hours
   automatically, or trigger manually from the Actions tab
   ("Run workflow" button)

The SQLite DB persists across runs via GitHub Actions dynamic caching (`actions/cache/restore` and `actions/cache/save`), so you won't get re-notified about the same item twice.

## Customizing

- **`config.py`** — edit `STACK_KEYWORDS` to match what you actually build.
  This is the whole "relevance" signal for now — no AI needed.
- **`config.py`** — edit `RSS_FEEDS` to add/remove feeds.
- **Cron schedule** — edit the `cron:` line in the workflow file
  (currently every 4 hours).

## What's NOT in this version (by design)

- No AI writing/posting yet — this is pure signal collection + notification.
- No X/Twitter source (their API isn't free) — GitHub, HN, Dev.to, RSS cover
  the free/practical ground.


## Project structure

```
trend-radar/
├── collector.py              # main entrypoint — fetch, score, store
├── notify_telegram.py        # sends ranked digest, marks items notified
├── config.py                 # your keywords, feeds, settings
├── schema.sql                # SQLite schema
├── sources/
│   ├── hackernews.py         # HN Firebase API (free, no auth)
│   ├── github_trending.py    # GitHub Search API (free, official)
│   ├── devto.py               # Dev.to public API (free, no auth)
│   └── rss_feeds.py           # generic RSS/Atom polling
└── .github/workflows/
    └── trend-radar.yml        # scheduled runner
```
