"""
GitHub 'trending' via the official REST Search API instead of scraping
github.com/trending (which has no API and breaks whenever they change markup).

Approach: repos created in the last 7 days, sorted by stars desc.
This is a solid proxy for "what's suddenly getting attention."

Auth: optional GITHUB_TOKEN env var bumps rate limit from 60/hr -> 5000/hr.
In GitHub Actions, the built-in secrets.GITHUB_TOKEN works fine for this.
"""

from __future__ import annotations

import os
import requests

from datetime import datetime, timedelta, timezone

SEARCH_URL = "https://api.github.com/search/repositories"


def fetch(min_stars: int = 50) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"created:>{since} stars:>={min_stars}"

    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(
            SEARCH_URL,
            params={"q": query, "sort": "stars", "order": "desc", "per_page": 30},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[github_trending] failed to fetch: {e}")
        return []

    items = []
    for repo in data.get("items", []):
        items.append({
            "id": f"gh-{repo['id']}",
            "source": "github_trending",
            "title": f"{repo['full_name']} — {repo.get('description') or 'no description'}",
            "url": repo["html_url"],
            "engagement_score": repo.get("stargazers_count", 0),
        })

    return items
