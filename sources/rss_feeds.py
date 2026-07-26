"""
Generic RSS/Atom feed source. Feeds are configured in config.RSS_FEEDS.
No engagement score available from RSS itself, so these rank purely on
relevance_score (keyword overlap) rather than engagement.
"""

from __future__ import annotations

import hashlib
import feedparser



def fetch(feed_urls: list[str]) -> list[dict]:
    items = []
    for feed_url in feed_urls:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[rss_feeds] failed to parse {feed_url}: {e}")
            continue

        if parsed.bozo and not parsed.entries:
            print(f"[rss_feeds] no entries parsed from {feed_url}")
            continue

        for entry in parsed.entries[:20]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            item_id = "rss-" + hashlib.sha256(link.encode()).hexdigest()[:16]
            items.append({
                "id": item_id,
                "source": f"rss:{feed_url}",
                "title": title,
                "url": link,
                "engagement_score": 0,  # RSS has no native engagement metric
            })

    return items
