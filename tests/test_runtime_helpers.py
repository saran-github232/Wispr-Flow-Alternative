"""Pure helpers in the runtime modules (safe to test headless)."""
import unittest

import numpy as np

from flowspeak.audio import TARGET_SR, resample_to_16k
from flowspeak.hotkey import name_variants
from flowspeak.transcribe import to_wav_bytes


class TestResample(unittest.TestCase):
    def test_identity_at_target_rate(self):
        x = np.linspace(-1, 1, 16000, dtype=np.float32)
        out = resample_to_16k(x, TARGET_SR)
        self.assertEqual(out.size, 16000)

    def test_downsample_length(self):
        x = np.zeros(48000, dtype=np.float32)   # 1s @ 48k
        out = resample_to_16k(x, 48000)
        self.assertEqual(out.size, 16000)       # 1s @ 16k

    def test_upsample_length(self):
        x = np.zeros(8000, dtype=np.float32)    # 1s @ 8k
        out = resample_to_16k(x, 8000)
        self.assertEqual(out.size, 16000)

    def test_empty_input(self):
        self.assertEqual(resample_to_16k(np.zeros(0, dtype=np.float32), 44100).size, 0)


class TestWav(unittest.TestCase):
    def test_wav_header_and_size(self):
        samples = np.zeros(16000, dtype=np.float32)
        data = to_wav_bytes(samples, 16000)
        self.assertEqual(data[:4], b"RIFF")
        self.assertEqual(data[8:12], b"WAVE")
        # 16000 samples * 2 bytes + 44-byte header
        self.assertEqual(len(data), 44 + 16000 * 2)

    def test_clipping_is_safe(self):
        samples = np.array([2.0, -2.0, 0.5], dtype=np.float32)  # out of range
        data = to_wav_bytes(samples, 16000)
        self.assertGreater(len(data), 44)


class TestHotkeyNames(unittest.TestCase):
    def test_right_ctrl_is_exact(self):
        self.assertEqual(name_variants("right ctrl"), {"right ctrl"})

    def test_generic_ctrl_matches_both_sides(self):
        v = name_variants("ctrl")
        self.assertIn("left ctrl", v)
        self.assertIn("right ctrl", v)

    def test_case_and_space_normalized(self):
        self.assertEqual(name_variants("  F9 "), {"f9"})


if __name__ == "__main__":
    unittest.main()
