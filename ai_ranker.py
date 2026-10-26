"""
Generates a short, personalized angle for trending items using Gemini.
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
    numbered = "\\n".join(
        f"{i}. [{item['source']}] {item['title']}"
        for i, item in enumerate(items)
    )
    return f"""You help a developer spot content ideas from trending tech items.

Their background: {config.USER_PROFILE_BLURB}

For EACH numbered item below, write ONE short sentence (under 20 words)
on why it might matter to THIS person or what angle they could write about.
If there is genuinely no plausible connection, say "No clear angle".

Items:
{numbered}

Respond with ONLY a JSON array, no markdown fences, no preamble, in this
exact shape:
[{{"index": 0, "angle": "..."}}, {{"index": 1, "angle": "..."}}, ...]
One object per item above, in the same order.
"""


def _extract_json(text: str) -> str:
    """Extract a JSON array, including when wrapped in markdown fences."""
    text = text.strip()
    match = re.search(r"\\[.*\\]", text, re.DOTALL)
    if match:
        return match.group(0)
    text = re.sub(r"^```(?:json)?\\s*", "", text)
    text = re.sub(r"\\s*```$", "", text)
    return text.strip()


def generate_angles(items: list[dict]) -> dict[str, str]:
    """
    Return usable model responses. Missing results are omitted so callers can
    retry them; explicit "No clear angle" responses count as completed results.
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
        if 0 <= idx < len(candidates):
            angles[candidates[idx]["id"]] = angle.strip()

    return angles
