import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import collector
import config


class CollectorRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "test.db")
        self.db_path_patch = patch.object(config, "DB_PATH", self.db_path)
        self.db_path_patch.start()
        self.conn = collector.get_db()
        self.ai_enabled_patch = patch.object(config, "ENABLE_AI_ANGLES", True)
        self.api_key_patch = patch.object(config, "GEMINI_API_KEY", "test-key")
        self.ai_enabled_patch.start()
        self.api_key_patch.start()

    def tearDown(self):
        self.conn.close()
        self.ai_enabled_patch.stop()
        self.api_key_patch.stop()
        self.db_path_patch.stop()
        self.tempdir.cleanup()

    def add_item(self, item_id="item-1", title="Python tooling"):
        collector.upsert_items(self.conn, [{
            "id": item_id,
            "source": "test",
            "title": title,
            "url": "https://example.com/item",
            "engagement_score": 10,
        }])

    def test_missing_ai_result_stays_pending_for_retry(self):
        self.add_item()
        with patch.object(collector.ai_ranker, "generate_angles", return_value={}):
            collector.apply_ai_angles(self.conn)

        angle = self.conn.execute(
            "SELECT ai_angle FROM items WHERE id = 'item-1'"
        ).fetchone()[0]
        self.assertEqual(angle, "")

        with patch.object(
            collector.ai_ranker, "generate_angles",
            return_value={"item-1": "Useful Python profiling idea"},
        ) as generate:
            collector.apply_ai_angles(self.conn)

        self.assertEqual(
            self.conn.execute(
                "SELECT ai_angle FROM items WHERE id = 'item-1'"
            ).fetchone()[0],
            "Useful Python profiling idea",
        )
        generate.assert_called_once()

    def test_relevance_is_recomputed_when_keywords_change(self):
        with patch.object(config, "STACK_KEYWORDS", ["react"]):
            self.add_item(title="React dashboard")

        with patch.object(config, "STACK_KEYWORDS", ["python"]):
            collector.upsert_items(self.conn, [{
                "id": "item-1",
                "source": "test",
                "title": "Python dashboard",
                "url": "https://example.com/item",
                "engagement_score": 12,
            }])

        row = self.conn.execute(
            "SELECT relevance_score, matched_keywords, title FROM items WHERE id = 'item-1'"
        ).fetchone()
        self.assertEqual(row, (1, "python", "Python dashboard"))

    def test_duplicate_feed_urls_keep_first_source_item(self):
        items = [
            {"id": "hn-1", "source": "hackernews", "url": "https://Example.com/story#comments"},
            {"id": "rss-1", "source": "rss:feed", "url": "https://example.com/story"},
            {"id": "rss-2", "source": "rss:feed", "url": "https://example.com/other"},
        ]

        unique = collector._dedupe_by_url(items)
        self.assertEqual([item["id"] for item in unique], ["hn-1", "rss-2"])

    def test_old_schema_is_upgraded_without_losing_rows(self):
        self.conn.close()
        legacy = sqlite3.connect(self.db_path)
        legacy.execute(
            "CREATE TABLE items (id TEXT PRIMARY KEY, source TEXT NOT NULL, "
            "title TEXT NOT NULL, url TEXT NOT NULL, fetched_at TEXT NOT NULL)"
        )
        legacy.execute(
            "INSERT INTO items (id, source, title, url, fetched_at) "
            "VALUES ('legacy-1', 'test', 'Legacy item', 'https://example.com', '2024-01-01')"
        )
        legacy.commit()
        legacy.close()

        self.conn = collector.get_db()
        row = self.conn.execute(
            "SELECT id, title, notified, ai_angle FROM items WHERE id = 'legacy-1'"
        ).fetchone()
        self.assertEqual(row, ("legacy-1", "Legacy item", 0, ""))


if __name__ == "__main__":
    unittest.main()
