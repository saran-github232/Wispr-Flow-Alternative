"""Transcript cleanup — local rule-based pipeline and the never-raise contract."""
import unittest

from flowspeak import cleanup
from flowspeak.config import (CLEANUP_LOCAL, CLEANUP_RAW, LEVEL_LIGHT,
                              LEVEL_NONE, Settings)


def _s(**kw):
    s = Settings()
    for k, v in kw.items():
        setattr(s, k, v)
    s.normalize()
    return s


class TestLocalCleanup(unittest.TestCase):
    def test_removes_hesitation_fillers(self):
        out = cleanup.clean("um so uh this is er fine", _s(cleanup_engine=CLEANUP_LOCAL))
        self.assertNotIn("um", out.lower().split())
        self.assertIn("fine", out.lower())

    def test_collapses_immediate_stutter(self):
        out = cleanup.clean("the the plan", _s(cleanup_engine=CLEANUP_LOCAL))
        self.assertEqual(out.lower().count("the"), 1)

    def test_keeps_deliberate_doubles(self):
        out = cleanup.clean("no no stop", _s(cleanup_engine=CLEANUP_LOCAL))
        self.assertEqual(out.lower().split().count("no"), 2)

    def test_spoken_punctuation(self):
        out = cleanup.clean("hello comma world period", _s(cleanup_engine=CLEANUP_LOCAL))
        self.assertIn("hello, world.", out.lower())

    def test_new_line_and_paragraph(self):
        out = cleanup.clean("one new line two new paragraph three",
                            _s(cleanup_engine=CLEANUP_LOCAL))
        self.assertIn("\n", out)

    def test_capitalizes_and_fixes_i(self):
        out = cleanup.clean("i think i am right", _s(cleanup_engine=CLEANUP_LOCAL))
        self.assertTrue(out.startswith("I "))
        self.assertEqual(out.count(" i "), 0)

    def test_dictionary_replacement(self):
        s = _s(cleanup_engine=CLEANUP_LOCAL, dictionary={"flowspeek": "FlowSpeak"})
        out = cleanup.clean("i love flowspeek", s)
        self.assertIn("FlowSpeak", out)

    def test_raw_engine_passes_through_but_applies_dictionary(self):
        s = _s(cleanup_engine=CLEANUP_RAW, dictionary={"teh": "the"})
        out = cleanup.clean("um teh thing", s)
        self.assertIn("um", out)          # raw keeps fillers
        self.assertIn("the", out)         # but still fixes dictionary words

    def test_level_none_only_dictionary(self):
        s = _s(cleanup_engine=CLEANUP_LOCAL, cleanup_level=LEVEL_NONE)
        out = cleanup.clean("um uh hello", s)
        self.assertIn("um", out)          # no filler removal at level none

    def test_never_raises_on_empty_or_weird(self):
        self.assertEqual(cleanup.clean("", _s()), "")
        self.assertEqual(cleanup.clean(None, _s()), "")
        self.assertIsInstance(cleanup.clean("   \n  ", _s()), str)


if __name__ == "__main__":
    unittest.main()
