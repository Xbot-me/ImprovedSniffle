"""
Trend Radar collector.
Fetches from enabled sources, scores relevance, detects score spikes,
optionally generates AI angles, and stores results in SQLite.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone

import config
import ai_ranker
from sources import hackernews, github_trending, devto, rss_feeds


# Add columns before schema.sql creates indexes: CREATE TABLE IF NOT EXISTS
# does not upgrade an existing table.
_MISSING_COLUMNS = {
    "engagement_score": "INTEGER DEFAULT 0",
    "last_score": "INTEGER DEFAULT 0",
    "relevance_score": "INTEGER DEFAULT 0",
    "matched_keywords": "TEXT DEFAULT ''",
    "ai_angle": "TEXT DEFAULT ''",
    "is_breakout": "INTEGER DEFAULT 0",
    "last_checked_at": "TEXT",
    "notified": "INTEGER DEFAULT 0",
    "notified_at_score": "INTEGER DEFAULT 0",
    "telegram_message_id": "TEXT DEFAULT ''",
    "saved": "INTEGER DEFAULT 0",
}


def _upgrade_schema(conn: sqlite3.Connection) -> None:
    """Add columns missing from an older database without discarding its data."""
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'items'"
    ).fetchone()
    if not table:
        return

    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()
    }
    for column, declaration in _MISSING_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE items ADD COLUMN {column} {declaration}")
    conn.commit()


def score_relevance(title: str) -> tuple[int, list[str]]:
    """Count keyword matches, using word boundaries for plain words."""
    title_lower = title.lower()
    matched = []
    for kw in config.STACK_KEYWORDS:
        if not kw.isalnum():
            if kw in title_lower:
                matched.append(kw)
        elif re.search(r"\\b" + re.escape(kw) + r"\\b", title_lower):
            matched.append(kw)
    return len(matched), matched


def get_db():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(base_dir, "schema.sql")
    conn = sqlite3.connect(config.DB_PATH)
    _upgrade_schema(conn)
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    return conn


def collect_all() -> list[dict]:
    """Pull from every enabled source and return a flat list of raw items."""
    raw_items = []

    if config.ENABLE_HACKERNEWS:
        print("Fetching Hacker News...")
        raw_items += hackernews.fetch(limit=config.HN_TOP_STORY_COUNT)

    if config.ENABLE_GITHUB_TRENDING:
        print("Fetching GitHub trending...")
        raw_items += github_trending.fetch(min_stars=config.GITHUB_TRENDING_MIN_STARS)

    if config.ENABLE_DEVTO:
        print("Fetching Dev.to...")
        raw_items += devto.fetch(top_n=config.DEVTO_TOP_N)

    if config.ENABLE_RSS:
        print("Fetching RSS feeds...")
        raw_items += rss_feeds.fetch(config.RSS_FEEDS)

    print(f"Collected {len(raw_items)} raw items across all sources.")
    return raw_items


def is_breakout(new_score: int, notified_at_score: int) -> bool:
    """Return true when an item's growth clears both configured thresholds."""
    if notified_at_score <= 0:
        return False
    delta = new_score - notified_at_score
    if delta < config.VELOCITY_MIN_ABSOLUTE_DELTA:
        return False
    return (delta / notified_at_score) >= config.VELOCITY_GROWTH_THRESHOLD


def upsert_items(conn: sqlite3.Connection, raw_items: list[dict]) -> tuple[int, int]:
    """Insert new items or update scores/relevance; return (new, breakout) counts."""
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    breakout_count = 0

    for item in raw_items:
        new_score = item.get("engagement_score", 0)
        relevance_score, matched_keywords = score_relevance(item["title"])
        cur.execute(
            "SELECT engagement_score, notified, notified_at_score FROM items WHERE id = ?",
            (item["id"],),
        )
        row = cur.fetchone()

        if row is None:
            cur.execute(
                """
                INSERT INTO items
                    (id, source, title, url, engagement_score, last_score,
                     relevance_score, matched_keywords, fetched_at, last_checked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"], item["source"], item["title"], item["url"],
                    new_score, new_score, relevance_score,
                    ",".join(matched_keywords), now, now,
                ),
            )
            new_count += 1
            continue

        old_score, notified, notified_at_score = row
        breakout = is_breakout(new_score, notified_at_score) if notified else False
        if breakout:
            breakout_count += 1

        cur.execute(
            """
            UPDATE items
            SET title = ?, url = ?, engagement_score = ?, last_score = ?,
                relevance_score = ?, matched_keywords = ?, last_checked_at = ?,
                is_breakout = ?,
                notified = CASE WHEN ? THEN 0 ELSE notified END
            WHERE id = ?
            """,
            (
                item["title"], item["url"], new_score, old_score,
                relevance_score, ",".join(matched_keywords), now,
                1 if breakout else 0, breakout, item["id"],
            ),
        )

    conn.commit()
    return new_count, breakout_count


def apply_ai_angles(conn: sqlite3.Connection):
    """Generate angles for pending items; leave failed/missing results retryable."""
    if not config.ENABLE_AI_ANGLES or not config.GEMINI_API_KEY:
        print("[collector] AI angles disabled or no GEMINI_API_KEY set, skipping.")
        return

    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, source, title FROM items
        WHERE notified = 0 AND (ai_angle = '' OR ai_angle IS NULL)
        ORDER BY relevance_score DESC, engagement_score DESC
        LIMIT ?
        """,
        (config.AI_ANGLE_CANDIDATE_COUNT,),
    )
    rows = cur.fetchall()
    if not rows:
        return

    candidates = [{"id": r[0], "source": r[1], "title": r[2]} for r in rows]
    print(f"Requesting AI angles for {len(candidates)} candidates...")
    angles = ai_ranker.generate_angles(candidates)

    updated = 0
    for cand in candidates:
        item_id = cand["id"]
        angle = angles.get(item_id)
        # Missing results indicate a failed/incomplete response. Keep the field
        # empty so the next run can retry rather than permanently storing "N/A".
        if angle:
            cur.execute("UPDATE items SET ai_angle = ? WHERE id = ?", (angle, item_id))
            updated += 1
    conn.commit()
    print(f"Updated AI angles for {updated} candidate(s).")


def main():
    conn = get_db()
    try:
        raw_items = collect_all()
        new_count, breakout_count = upsert_items(conn, raw_items)
        print(f"Stored {new_count} new items. Detected {breakout_count} breakout(s).")
        apply_ai_angles(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
