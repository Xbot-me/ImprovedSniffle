"""
Dev.to — free public API, no auth needed for reads.
Docs: https://developers.forem.com/api
"""

from __future__ import annotations

import requests


ARTICLES_URL = "https://dev.to/api/articles"


def fetch(top_n: int = 30) -> list[dict]:
    try:
        resp = requests.get(
            ARTICLES_URL,
            params={"top": 7, "per_page": top_n},  # top articles from last 7 days
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[devto] failed to fetch: {e}")
        return []

    items = []
    if not isinstance(data, list):
        return []

    for article in data:
        if not isinstance(article, dict) or not article.get("id"):
            continue
        items.append({
            "id": f"devto-{article['id']}",
            "source": "devto",
            "title": str(article.get("title") or "").strip(),
            "url": str(article.get("url") or ""),
            "engagement_score": article.get("public_reactions_count", 0),
        })

    return items

