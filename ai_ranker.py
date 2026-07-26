"""
Generates a one-line "why this matters to you" angle for a small batch of
candidate items using Gemini. This is the only AI cost in the whole pipeline
— one batched call per run, capped at config.AI_ANGLE_CANDIDATE_COUNT items,
using a cheap model by default (Flash-Lite).

Cost sanity check: ~15 items * ~150 tokens each in, ~15 * ~30 tokens out
per run ≈ 2.5K in / 450 out. At Flash-Lite rates ($0.10/$0.40 per M tokens)
that's a fraction of a cent per run, a few cents a day at most.
"""

from __future__ import annotations

import json
import re
import requests


import config

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def _build_prompt(items: list[dict]) -> str:
    numbered = "\n".join(
        f"{i}. [{item['source']}] {item['title']}"
        for i, item in enumerate(items)
    )
    return f"""You help a developer spot content ideas from trending tech items.

Their background: {config.USER_PROFILE_BLURB}

For EACH numbered item below, write ONE short punchy sentence (under 20 words)
on why it might matter to THIS person specifically, or what angle they could
write about if it overlaps with their work. If an item genuinely has no
plausible connection to their background, say "No clear angle" for it.

Items:
{numbered}

Respond with ONLY a JSON array, no markdown fences, no preamble, in this
exact shape:
[{{"index": 0, "angle": "..."}}, {{"index": 1, "angle": "..."}}, ...]
One object per item above, in the same order.
"""


def _extract_json(text: str) -> str:
    """Extract JSON array string, stripping markdown code fences or conversational text."""
    text = text.strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return match.group(0)
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def generate_angles(items: list[dict]) -> dict[str, str]:
    """
    Takes a list of item dicts (must have 'id', 'source', 'title').
    Returns {item_id: angle_text} for whichever items got a usable response.
    Returns {} on any failure — callers should treat AI angles as optional.
    """
    if not config.ENABLE_AI_ANGLES or not config.GEMINI_API_KEY or not items:
        return {}

    candidates = items[: config.AI_ANGLE_CANDIDATE_COUNT]
    prompt = _build_prompt(candidates)

    url = GEMINI_URL.format(model=config.GEMINI_MODEL)
    try:
        resp = requests.post(
            url,
            headers={"x-goog-api-key": config.GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1024},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        candidates_resp = data.get("candidates", [])
        if not candidates_resp:
            return {}
        parts = candidates_resp[0].get("content", {}).get("parts", [])
        if not parts:
            return {}
        raw_text = parts[0].get("text", "")
    except Exception as e:
        print(f"[ai_ranker] Gemini call failed, skipping AI angles: {e}")
        return {}

    try:
        parsed = json.loads(_extract_json(raw_text))
    except Exception as e:
        print(f"[ai_ranker] failed to parse Gemini JSON response: {e}")
        return {}

    angles = {}
    if not isinstance(parsed, list):
        return {}

    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        idx_raw = entry.get("index")
        angle = entry.get("angle", "")
        if idx_raw is None or not isinstance(angle, str) or not angle.strip():
            continue
        try:
            idx = int(idx_raw)
        except (ValueError, TypeError):
            continue
        if angle.strip().lower().startswith("no clear angle"):
            continue
        if 0 <= idx < len(candidates):
            angles[candidates[idx]["id"]] = angle.strip()

    return angles
