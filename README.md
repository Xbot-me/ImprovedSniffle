# StackScout

StackScout collects developer content from Hacker News, GitHub, Dev.to, and configured RSS feeds, scores it against a list of technology interests, and sends selected items to Telegram. Gemini-generated context is optional.

The project is a small Python application backed by SQLite. It is intended for personal use and can be run locally or on a schedule with GitHub Actions.

## What it does

- Fetches stories, repositories, articles, and RSS entries from enabled sources.
- Matches titles against keywords in `config.py`.
- Stores items in SQLite so previously seen items can be recognized.
- Flags previously notified items when their engagement score rises enough to meet the configured breakout thresholds.
- Optionally asks Gemini for a short, personalized note about selected items.
- Sends a ranked Telegram digest with a Save button.

Relevance scoring is currently keyword overlap, not semantic search. GitHub discovery uses recently created repositories sorted by stars; it is a practical proxy for trending projects, not a reproduction of GitHub's Trending page.

## Data sources

| Source | Collection method | Score used |
| --- | --- | --- |
| Hacker News | Official Firebase-backed API | Story score |
| GitHub | Repository Search API | Stars |
| Dev.to | Public articles API | Public reactions |
| RSS/Atom | Configured feeds parsed by Feedparser | No engagement score |

Sources can be enabled or disabled in `config.py`. The default RSS list includes Hacker News and Dev.to feeds as well, so the same story may appear through more than one source under different IDs.

## Requirements

- Python 3.10 or newer
- A Telegram bot and chat ID for delivery
- A Gemini API key only if AI angles are wanted

Install dependencies:

```bash
git clone https://github.com/Xbot-me/ImprovedSniffle.git
cd ImprovedSniffle
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate the environment with `.venv\\Scripts\\activate`.

## Configuration

Set credentials as environment variables rather than putting secrets in source files:

```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
export GEMINI_API_KEY="your-gemini-api-key"  # optional
```

Create a Telegram bot through [@BotFather](https://t.me/BotFather). To find your chat ID, message the bot and inspect the updates returned by Telegram's Bot API. Treat the bot token as a password; do not publish a URL containing it.

Optional configuration is in `config.py`, including:

- `STACK_KEYWORDS`: terms used to score item titles
- `RSS_FEEDS`: RSS/Atom feed URLs
- `ENABLE_HACKERNEWS`, `ENABLE_GITHUB_TRENDING`, `ENABLE_DEVTO`, `ENABLE_RSS`: source switches
- `DIGEST_TOP_N`: maximum number of items selected for a digest
- `VELOCITY_GROWTH_THRESHOLD` and `VELOCITY_MIN_ABSOLUTE_DELTA`: breakout thresholds
- `ENABLE_AI_ANGLES`, `GEMINI_MODEL`, and `AI_ANGLE_CANDIDATE_COUNT`: optional AI settings

The default database path is `trend_radar.db`. Override it with `DB_PATH` if needed.

## Run it

Collect items and update the SQLite database:

```bash
python collector.py
```

Send the pending digest and process Telegram Save-button callbacks:

```bash
python notify_telegram.py
```

Run the collector before the notifier. The collector initializes the database schema; the notifier expects that schema to exist. If Telegram credentials are missing, the notifier prints the messages it would send rather than delivering them.

## GitHub Actions

The workflow at `.github/workflows/trend-radar.yml` runs every four hours and can also be started manually from the Actions tab.

Add these repository Actions secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GEMINI_API_KEY` (optional)

The workflow uses GitHub Actions cache to carry the SQLite database between runs. Cache storage is best-effort, not a durable database: cache eviction, overlapping runs, or a missing cache can affect history and duplicate prevention. For reliable long-term state, use persistent storage instead.

## How breakout detection works

For an item that has already been notified, StackScout compares its current engagement score with the score recorded at its last notification. A breakout is flagged only when the increase meets both the configured absolute-delta threshold and percentage-growth threshold. This is a simple heuristic; it does not measure a true time-series growth rate.

## Project layout

```text
.
├── collector.py              # Fetch, score, and store items
├── notify_telegram.py        # Send Telegram messages and handle Save callbacks
├── ai_ranker.py              # Optional Gemini explanations
├── config.py                 # Sources, keywords, and runtime settings
├── schema.sql                # SQLite schema
└── sources/
    ├── hackernews.py
    ├── github_trending.py
    ├── devto.py
    └── rss_feeds.py
```

## Current limitations

- Keyword matching only examines titles; it does not understand the full article or repository.
- RSS items have no engagement score, so they are primarily ranked by keyword relevance.
- The GitHub query finds recently created repositories with enough stars; it can miss older projects that are newly gaining attention.
- Multiple feeds can surface the same underlying content.
- GitHub Actions cache is not durable storage.
- The project does not currently provide a test suite or a persistent hosted service.

## Contributing

Bug reports and focused improvements are welcome. For changes to collection or notification behavior, include a reproduction or test where practical.

## License

MIT. See [LICENSE](LICENSE) if present in the repository.
