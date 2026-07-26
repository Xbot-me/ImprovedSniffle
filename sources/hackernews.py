"""
Hacker News — free, no auth, official Firebase-backed API.
Docs: https://github.com/HackerNews/API
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import requests


TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"


def _fetch_single_story(story_id: int) -> dict | None:
    try:
        resp = requests.get(ITEM_URL.format(id=story_id), timeout=10).json()
    except Exception as e:
        print(f"[hackernews] failed to fetch item {story_id}: {e}")
        return None

    if not resp or resp.get("type") != "story":
        return None

    url = resp.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
    return {
        "id": f"hn-{story_id}",
        "source": "hackernews",
        "title": resp.get("title", "").strip(),
        "url": url,
        "engagement_score": resp.get("score", 0),
    }


def fetch(limit: int = 60) -> list[dict]:
    """Return top HN stories as normalized dicts."""
    try:
        top_ids = requests.get(TOP_STORIES_URL, timeout=10).json()[:limit]
    except Exception as e:
        print(f"[hackernews] failed to fetch top stories: {e}")
        return []

    items = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(_fetch_single_story, top_ids)
        for res in results:
            if res:
                items.append(res)

    return items

