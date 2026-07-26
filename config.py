"""
Trend Radar config.
Edit STACK_KEYWORDS to match what you actually build — this is used to
score/rank incoming items with zero AI cost (pure keyword overlap for v1).
"""

import os

# --- Your stack / interest keywords (lowercase, used for substring matching) ---
STACK_KEYWORDS = [
    "woocommerce", "wordpress", "wp-cli", "elementor",
    "go", "golang", "livekit", "webrtc", "rabbitmq", "redis",
    "flutter", "dart", "riverpod",
    "react", "next.js", "nextjs", "typescript", "vite",
    "python", "ocr", "tesseract", "streamlit",
    "mysql", "nginx", "docker", "self-hosted", "devops",
    "github actions", "ci/cd", "bash",
    "e-commerce", "ecommerce", "scaling", "performance", "caching",
    "bangladesh", "bangla",
]

# --- RSS feeds to poll (add/remove freely) ---
RSS_FEEDS = [
    "https://dev.to/feed",
    "https://news.ycombinator.com/rss",  # backup if HN API is unreachable
    "https://www.reddit.com/r/webdev/.rss",
    "https://www.reddit.com/r/programming/.rss",
]

# --- Source toggles ---
ENABLE_HACKERNEWS = True
ENABLE_GITHUB_TRENDING = True
ENABLE_DEVTO = True
ENABLE_RSS = True

# --- Fetch limits ---
HN_TOP_STORY_COUNT = 60          # how many top HN story IDs to check per run
GITHUB_TRENDING_MIN_STARS = 50   # ignore repos with fewer stars than this
DEVTO_TOP_N = 30

# --- Telegram (set as env vars / GitHub Actions secrets — never hardcode) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- Storage ---
DB_PATH = os.environ.get("DB_PATH", "trend_radar.db")

# --- How many items to send per notification digest ---
DIGEST_TOP_N = 8

# --- Velocity detection (re-surface items whose score spikes after being sent) ---
# An already-notified item gets re-sent (marked breakout) if its score grows
# by at least this fraction AND at least this absolute amount since it was last sent.
VELOCITY_GROWTH_THRESHOLD = 0.5   # 50% growth
VELOCITY_MIN_ABSOLUTE_DELTA = 20  # ignore tiny-number noise (e.g. 2 -> 3 stars)

# --- AI angle generation (Gemini) ---
ENABLE_AI_ANGLES = True
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Flash-Lite is the cheap default. Override via env var if you want higher quality
# (e.g. GEMINI_MODEL=gemini-2.5-flash or gemini-2.5-pro), at higher per-call cost.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
# Cap how many items get an AI call per run -- this is the actual cost lever.
AI_ANGLE_CANDIDATE_COUNT = 15

# Short profile used in the AI prompt -- edit this to match how you'd describe
# yourself/your work, it directly shapes the quality of the generated angles.
USER_PROFILE_BLURB = (
    "A full-stack developer who owns a WooCommerce e-commerce platform with "
    "236,000+ orders, does Fiverr freelance work, and builds side projects in "
    "Go, Flutter, React/Next.js, and Python (including a LiveKit-based video "
    "platform and a Bangla OCR pipeline). Interested in backend architecture, "
    "e-commerce scaling, DevOps, and practical open-source tools."
)
