"""Usage stats: recording, streak, 7-day activity, summary, persistence."""
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from flowspeak.stats import StatsStore, count_words


def _ts(d: date) -> float:
    return datetime(d.year, d.month, d.day, 12, 0, 0).timestamp()


class TestStats(unittest.TestCase):
    def test_count_words_ignores_pure_punctuation(self):
        self.assertEqual(count_words("hello world"), 2)
        self.assertEqual(count_words("hi , . ! there"), 2)
        self.assertEqual(count_words(""), 0)

    def test_record_updates_totals(self):
        s = StatsStore()
        s.record("hello there friend", 60_000)
        self.assertEqual(s.total_words, 3)
        self.assertEqual(s.sessions, 1)
        self.assertEqual(len(s.history()), 1)

    def test_empty_text_not_recorded(self):
        s = StatsStore()
        s.record("   ", 1000)
        self.assertEqual(s.sessions, 0)

    def test_streak_counts_consecutive_days(self):
        s = StatsStore()
        today = date(2026, 10, 1)
        for i in range(3):
            s.record("one two", 1000, ts=_ts(today - timedelta(days=i)))
        self.assertEqual(s.streak(today), 3)
        # a gap breaks the streak
        s2 = StatsStore()
        s2.record("x y", 1000, ts=_ts(today))
        s2.record("x y", 1000, ts=_ts(today - timedelta(days=2)))
        self.assertEqual(s2.streak(today), 1)

    def test_activity_7d_has_seven_days(self):
        s = StatsStore()
        a = s.activity_7d(date(2026, 10, 1))
        self.assertEqual(len(a), 7)
        self.assertEqual(a[-1][0], "2026-10-01")

    def test_summary_keys_and_time_saved(self):
        s = StatsStore()
        s.record(" ".join(["word"] * 80), 60_000, ts=_ts(date(2026, 10, 1)))
        summ = s.summary(date(2026, 10, 1))
        for k in ("total_words", "words_today", "wpm", "streak_days",
                  "time_saved_minutes", "sessions", "activity_7d"):
            self.assertIn(k, summ)
        self.assertEqual(summ["total_words"], 80)
        # 80 words typed at 40 wpm = 2 min; dictated in 1 min => ~1 min saved
        self.assertGreater(summ["time_saved_minutes"], 0)

    def test_history_capped(self):
        s = StatsStore()
        for i in range(250):
            s.record(f"entry number {i}", 1000)
        self.assertLessEqual(len(s.history_items), 200)
        self.assertEqual(s.history(limit=5).__len__(), 5)

    def test_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "stats.json"
            s = StatsStore()
            s.record("alpha beta gamma", 30_000)
            s.save(p)
            loaded = StatsStore.load(p)
            self.assertEqual(loaded.total_words, 3)
            self.assertEqual(loaded.sessions, 1)


if __name__ == "__main__":
    unittest.main()
