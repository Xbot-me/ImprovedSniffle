-- Current SQLite schema. collector.py adds known missing columns to older
-- items tables before executing this file, preserving existing rows.

CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,          -- stable hash of url (or source-specific id)
    source TEXT NOT NULL,         -- 'hackernews' | 'github_trending' | 'devto' | 'rss:<feed>'
    title TEXT NOT NULL,
    url TEXT NOT NULL,

    engagement_score INTEGER DEFAULT 0,  -- latest known score (points/stars/reactions)
    last_score INTEGER DEFAULT 0,        -- score as of the previous collector run (for velocity)
    relevance_score INTEGER DEFAULT 0,   -- keyword-overlap score (v1, no AI)
    matched_keywords TEXT DEFAULT '',

    ai_angle TEXT DEFAULT '',            -- one-line "why this matters" from Gemini, if generated
    is_breakout INTEGER DEFAULT 0,       -- 1 = score spiked since it was last notified

    fetched_at TEXT NOT NULL,            -- first seen
    last_checked_at TEXT,                -- most recent collector run that saw this item

    notified INTEGER DEFAULT 0,          -- 0 = pending send in next digest
    notified_at_score INTEGER DEFAULT 0, -- score value at the moment it was last sent
    telegram_message_id TEXT DEFAULT '', -- for editing the message after a Save tap
    saved INTEGER DEFAULT 0              -- 1 = user tapped Save
);

CREATE INDEX IF NOT EXISTS idx_items_notified ON items(notified);
CREATE INDEX IF NOT EXISTS idx_items_fetched_at ON items(fetched_at);

-- Small key/value table for bot polling state (e.g. last Telegram update_id seen)
CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
