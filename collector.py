"""
Trend Radar collector.
Fetches from all enabled sources, scores relevance against your stack
keywords, detects velocity spikes on already-seen items, optionally
generates AI angles for top candidates, and stores everything in SQLite.

Run manually:  python collector.py
Run on cron via GitHub Actions (see .github/workflows/trend-radar.yml)
"""

from __future__ import annotations

import os
import re
import sqlite3

from datetime import datetime, timezone

import config
import ai_ranker
from sources import hackernews, github_trending, devto, rss_feeds


def score_relevance(title: str) -> tuple[int, list[str]]:
    """Keyword match with word boundary support for plain words and exact matching for tech symbols."""
    title_lower = title.lower()
    matched = []
    for kw in config.STACK_KEYWORDS:
        if not kw.isalnum():
            if kw in title_lower:
                matched.append(kw)
        else:
            if re.search(r"\b" + re.escape(kw) + r"\b", title_lower):
                matched.append(kw)
    return len(matched), matched


def get_db():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(base_dir, "schema.sql")
    conn = sqlite3.connect(config.DB_PATH)
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
    """An already-notified item counts as a breakout if it grew enough,
    both proportionally and in absolute terms (avoids noise on tiny numbers)."""
    if notified_at_score <= 0:
        return False
    delta = new_score - notified_at_score
    if delta < config.VELOCITY_MIN_ABSOLUTE_DELTA:
        return False
    return (delta / notified_at_score) >= config.VELOCITY_GROWTH_THRESHOLD


def upsert_items(conn: sqlite3.Connection, raw_items: list[dict]) -> tuple[int, int]:
    """
    Insert new items, or update engagement_score + check velocity on existing ones.
    Returns (new_count, breakout_count).
    """
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    breakout_count = 0

    for item in raw_items:
        new_score = item.get("engagement_score", 0)
        cur.execute("SELECT engagement_score, notified, notified_at_score FROM items WHERE id = ?",
                     (item["id"],))
        row = cur.fetchone()

        if row is None:
            # brand new item
            relevance_score, matched_keywords = score_relevance(item["title"])
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
        else:
            old_score, notified, notified_at_score = row
            breakout = is_breakout(new_score, notified_at_score) if notified else False
            if breakout:
                breakout_count += 1

            cur.execute(
                """
                UPDATE items
                SET engagement_score = ?,
                    last_score = ?,
                    last_checked_at = ?,
                    is_breakout = ?,
                    notified = CASE WHEN ? THEN 0 ELSE notified END
                WHERE id = ?
                """,
                (new_score, old_score, now, 1 if breakout else 0, breakout, item["id"]),
            )

    conn.commit()
    return new_count, breakout_count


def apply_ai_angles(conn: sqlite3.Connection):
    """Generate AI angles for the top pending (un-notified) candidates only."""
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

    # Convert to dicts manually to avoid global row_factory mutation
    candidates = [{"id": r[0], "source": r[1], "title": r[2]} for r in rows]

    print(f"Requesting AI angles for {len(candidates)} candidates...")
    angles = ai_ranker.generate_angles(candidates)

    for cand in candidates:
        item_id = cand["id"]
        angle = angles.get(item_id, "N/A")
        cur.execute("UPDATE items SET ai_angle = ? WHERE id = ?", (angle, item_id))
    conn.commit()
    print(f"Updated AI angles for {len(candidates)} candidate(s).")



def main():
    conn = get_db()
    raw_items = collect_all()
    new_count, breakout_count = upsert_items(conn, raw_items)
    print(f"Stored {new_count} new items. Detected {breakout_count} breakout(s).")
    apply_ai_angles(conn)
    conn.close()


if __name__ == "__main__":
    main()
