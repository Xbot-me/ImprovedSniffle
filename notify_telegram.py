"""
Sends new/breakout items to Telegram as individual messages (one per item)
with an inline "Save" button, and processes any pending Save button taps
from the previous run via polling (no webhook server needed).

Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as env vars.
Getting these:
  1. Message @BotFather on Telegram -> /newbot -> get the token
  2. Message your new bot anything, then visit:
     https://api.telegram.org/bot<TOKEN>/getUpdates
     -> find "chat":{"id": ...} in the response, that's your chat id
"""

from __future__ import annotations

import html
import sqlite3
import requests


import config


API_BASE = "https://api.telegram.org/bot{token}/{method}"


def api_call(method: str, **params) -> dict | None:
    if not config.TELEGRAM_BOT_TOKEN:
        return None
    url = API_BASE.format(token=config.TELEGRAM_BOT_TOKEN, method=method)
    try:
        resp = requests.post(url, json=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[notify_telegram] {method} failed: {e}")
        return None


def get_bot_state(conn: sqlite3.Connection, key: str, default: str = "0") -> str:
    cur = conn.execute("SELECT value FROM bot_state WHERE key = ?", (key,))
    row = cur.fetchone()
    return row[0] if row else default


def set_bot_state(conn: sqlite3.Connection, key: str, value: str):
    conn.execute(
        "INSERT INTO bot_state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def process_pending_saves(conn: sqlite3.Connection):
    """Poll for Save button taps since the last update_id we processed."""
    if not config.TELEGRAM_BOT_TOKEN:
        return

    last_update_id = int(get_bot_state(conn, "last_update_id", "0"))
    result = api_call("getUpdates", offset=last_update_id + 1, timeout=0)
    if not result or not result.get("ok"):
        return

    updates = result.get("result", [])
    max_update_id = last_update_id

    for update in updates:
        max_update_id = max(max_update_id, update["update_id"])
        cq = update.get("callback_query")
        if not cq:
            continue

        item_id = cq.get("data", "")
        if not item_id or item_id == "noop":
            continue

        callback_id = cq["id"]
        message = cq.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")

        conn.execute("UPDATE items SET saved = 1 WHERE id = ?", (item_id,))
        conn.commit()

        api_call("answerCallbackQuery", callback_query_id=callback_id, text="Saved ✅")
        if chat_id and message_id:
            api_call(
                "editMessageReplyMarkup",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup={"inline_keyboard": [[{"text": "✅ Saved", "callback_data": "noop"}]]},
            )
        print(f"[notify_telegram] marked item {item_id} as saved.")

    if max_update_id != last_update_id:
        set_bot_state(conn, "last_update_id", str(max_update_id))


def get_pending_items(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        """
        SELECT * FROM items
        WHERE notified = 0
        ORDER BY is_breakout DESC, relevance_score DESC, engagement_score DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cur.fetchall()


def format_item_message(item: sqlite3.Row) -> str:
    tag = "🚀 BREAKOUT" if item["is_breakout"] else ("⭐" if item["relevance_score"] > 0 else "•")
    title = html.escape(str(item["title"] or ""))
    url = html.escape(str(item["url"] or ""))
    source = html.escape(str(item["source"] or ""))
    matched = html.escape(str(item["matched_keywords"] or ""))
    ai_angle = html.escape(str(item["ai_angle"] or ""))

    lines = [f"{tag} <a href=\"{url}\">{title}</a>"]
    lines.append(f"<i>{source} · score {item['engagement_score']}</i>")
    if matched:
        lines.append(f"Matches: {matched}")
    if ai_angle and ai_angle != "N/A":
        lines.append(f"💡 {ai_angle}")
    return "\n".join(lines)



def send_item(item: sqlite3.Row) -> dict | None:
    text = format_item_message(item)
    return api_call(
        "sendMessage",
        chat_id=config.TELEGRAM_CHAT_ID,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=False,
        reply_markup={"inline_keyboard": [[{"text": "💾 Save", "callback_data": item["id"]}]]},
    )


def main():
    conn = sqlite3.connect(config.DB_PATH)

    process_pending_saves(conn)

    items = get_pending_items(conn, config.DIGEST_TOP_N)
    if not items:
        print("No new items to notify.")
        conn.close()
        return

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[notify_telegram] missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.")
        print(f"--- Would have sent {len(items)} item(s) ---")
        for item in items:
            print(format_item_message(item))
            print("---")
        conn.close()
        return

    api_call(
        "sendMessage",
        chat_id=config.TELEGRAM_CHAT_ID,
        text=f"<b>🔥 Trend Radar — {len(items)} item(s)</b>",
        parse_mode="HTML",
    )

    sent_count = 0
    for item in items:
        result = send_item(item)
        if result and result.get("ok"):
            message_id = result["result"]["message_id"]
            conn.execute(
                """
                UPDATE items
                SET notified = 1, notified_at_score = engagement_score,
                    is_breakout = 0, telegram_message_id = ?
                WHERE id = ?
                """,
                (str(message_id), item["id"]),
            )
            conn.commit()
            sent_count += 1

    print(f"Sent {sent_count}/{len(items)} item(s).")
    conn.close()


if __name__ == "__main__":
    main()
