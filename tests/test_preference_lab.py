import tempfile
import unittest
from pathlib import Path

from scripts import preference_lab


class PreferenceLabTests(unittest.TestCase):
    def test_item_rating_and_comparison_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "preferences.sqlite"
            conn = preference_lab.connect(db_path)
            try:
                preference_lab.add_item(conn, item_id="candidate-a", prompt="wooden chair")
                preference_lab.add_item(conn, item_id="candidate-b", prompt="wooden chair")
                preference_lab.record_rating(conn, item_id="candidate-a", score=0.8)
                preference_lab.record_rating(conn, item_id="candidate-b", score=0.5)
                preference_lab.record_comparison(
                    conn,
                    left_item_id="candidate-a",
                    right_item_id="candidate-b",
                    winner="left",
                )
                summary = preference_lab.summary(conn)
            finally:
                conn.close()

        self.assertEqual(summary["items"], 2)
        self.assertEqual(summary["ratings"], 2)
        self.assertEqual(summary["comparisons"], 1)
        self.assertEqual(summary["ranked_items"][0]["item_id"], "candidate-a")

    def test_invalid_comparison_winner_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = preference_lab.connect(Path(tmp) / "preferences.sqlite")
            try:
                preference_lab.add_item(conn, item_id="left")
                preference_lab.add_item(conn, item_id="right")
                with self.assertRaises(ValueError):
                    preference_lab.record_comparison(
                        conn,
                        left_item_id="left",
                        right_item_id="right",
                        winner="middle",
                    )
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

