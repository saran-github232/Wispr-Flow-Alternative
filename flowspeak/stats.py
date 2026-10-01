"""Local-only usage stats and history.

Persisted to %APPDATA%\\FlowSpeak\\stats.json. Tracks words dictated, average
words-per-minute, a day streak, estimated time saved vs. typing, 7-day activity,
and a capped list of recent dictations. Nothing leaves the machine.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from .paths import stats_path

# Assumed typing speed (words/min) used to estimate time saved by dictating.
TYPING_WPM = 40.0
HISTORY_LIMIT = 200


class StatsStore:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.total_words: int = int(data.get("total_words", 0))
        self.total_duration_ms: int = int(data.get("total_duration_ms", 0))
        self.total_chars: int = int(data.get("total_chars", 0))
        self.sessions: int = int(data.get("sessions", 0))
        # date "YYYY-MM-DD" -> words that day
        self.daily: dict[str, int] = dict(data.get("daily", {}))
        # most-recent-first list of {ts, text, words, app}
        self.history_items: list[dict] = list(data.get("history", []))

    # ------------------------------------------------------------------ load/save
    @classmethod
    def load(cls, path: Path | None = None) -> "StatsStore":
        path = path or stats_path()
        try:
            return cls(json.loads(Path(path).read_text(encoding="utf-8")))
        except (FileNotFoundError, ValueError, OSError):
            return cls()

    def to_dict(self) -> dict:
        return {
            "total_words": self.total_words,
            "total_duration_ms": self.total_duration_ms,
            "total_chars": self.total_chars,
            "sessions": self.sessions,
            "daily": self.daily,
            "history": self.history_items[:HISTORY_LIMIT],
        }
    def save(self, path: Path | None = None) -> None:
        path = Path(path or stats_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    # ------------------------------------------------------------------ record
    def record(self, text: str, duration_ms: int, app: str | None = None,
               ts: float | None = None) -> None:
        words = count_words(text)
        if words == 0:
            return
        ts = ts if ts is not None else time.time()
        self.total_words += words
        self.total_duration_ms += max(0, int(duration_ms))
        self.total_chars += len(text)
        self.sessions += 1
        day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        self.daily[day] = self.daily.get(day, 0) + words
        self.history_items.insert(0, {
            "ts": ts,
            "text": text[:2000],
            "words": words,
            "app": app or "",
        })
        del self.history_items[HISTORY_LIMIT:]

    # ------------------------------------------------------------------ queries
    def history(self, limit: int = 50) -> list[dict]:
        return self.history_items[:limit]

    def streak(self, today: date | None = None) -> int:
        today = today or date.today()
        n = 0
        d = today
        while self.daily.get(d.strftime("%Y-%m-%d"), 0) > 0:
            n += 1
            d = d - timedelta(days=1)
        return n

    def activity_7d(self, today: date | None = None) -> list[tuple[str, int]]:
        today = today or date.today()
        out = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            key = d.strftime("%Y-%m-%d")
            out.append((key, self.daily.get(key, 0)))
        return out

    def summary(self, today: date | None = None) -> dict:
        today = today or date.today()
        minutes = self.total_duration_ms / 60000.0
        wpm = (self.total_words / minutes) if minutes > 0 else 0.0
        # Time saved = (time it would take to type) - (time spent dictating).
        type_minutes = self.total_words / TYPING_WPM
        saved_minutes = max(0.0, type_minutes - minutes)
        return {
            "total_words": self.total_words,
            "words_today": self.daily.get(today.strftime("%Y-%m-%d"), 0),
            "wpm": round(wpm, 1),
            "streak_days": self.streak(today),
            "time_saved_minutes": round(saved_minutes, 1),
            "sessions": self.sessions,
            "activity_7d": self.activity_7d(today),
        }


def count_words(text: str) -> int:
    return len([w for w in (text or "").split() if any(c.isalnum() for c in w)])

