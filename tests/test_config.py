"""Settings load/save/normalize and API-readiness helpers."""
import json
import tempfile
import unittest
from pathlib import Path

from flowspeak import config as cfg
from flowspeak.config import Settings


class TestSettings(unittest.TestCase):
    def test_defaults(self):
        s = Settings()
        self.assertEqual(s.hotkey, "right ctrl")
        self.assertEqual(s.stt_engine, cfg.STT_LOCAL)
        self.assertEqual(s.cleanup_engine, cfg.CLEANUP_LOCAL)
        self.assertEqual(s.cleanup_level, cfg.LEVEL_LIGHT)

    def test_normalize_repairs_bad_values(self):
        s = Settings()
        s.cleanup_engine = "bogus"
        s.cleanup_level = "nope"
        s.stt_engine = "???"
        s.paste_mode = "weird"
        s.min_hold_ms = -5
        s.session_cap_minutes = 0
        s.dictionary = ["not", "a", "dict"]
        s.normalize()
        self.assertEqual(s.cleanup_engine, cfg.CLEANUP_LOCAL)
        self.assertEqual(s.cleanup_level, cfg.LEVEL_LIGHT)
        self.assertEqual(s.stt_engine, cfg.STT_LOCAL)
        self.assertEqual(s.paste_mode, "paste")
        self.assertEqual(s.min_hold_ms, 0)
        self.assertEqual(s.session_cap_minutes, 1)
        self.assertEqual(s.dictionary, {})

    def test_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            s = Settings(hotkey="f9", whisper_model="small.en",
                         dictionary={"wat": "what"})
            s.save(p)
            loaded = Settings.load(p)
            self.assertEqual(loaded.hotkey, "f9")
            self.assertEqual(loaded.whisper_model, "small.en")
            self.assertEqual(loaded.dictionary, {"wat": "what"})

    def test_load_ignores_unknown_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            p.write_text(json.dumps({"hotkey": "f8", "from_the_future": 1}),
                         encoding="utf-8")
            loaded = Settings.load(p)
            self.assertEqual(loaded.hotkey, "f8")
            self.assertFalse(hasattr(loaded, "from_the_future"))

    def test_load_missing_file_returns_defaults(self):
        loaded = Settings.load(Path(tempfile.gettempdir()) / "nope_missing.json")
        self.assertEqual(loaded.hotkey, "right ctrl")

    def test_api_readiness(self):
        s = Settings()
        self.assertFalse(s.has_api_key())
        s.openai_api_key = "sk-test"
        self.assertTrue(s.has_api_key())
        s.cleanup_engine = cfg.CLEANUP_OPENAI
        self.assertTrue(s.api_ready())
        s.stt_engine = cfg.STT_OPENAI
        self.assertTrue(s.stt_api_ready())


if __name__ == "__main__":
    unittest.main()
