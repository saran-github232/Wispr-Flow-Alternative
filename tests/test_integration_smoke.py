"""Headless integration smoke tests.

These exercise the *runtime* modules (audio, paste, hotkey, transcribe) and the
full dictation pipeline with the hardware / GUI / speech-model libraries replaced
by in-process fakes. ``py_compile`` only checks syntax; these catch wiring,
attribute and signature breaks across module boundaries without needing a
microphone, a display, or the heavy speech dependencies.
"""
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np


# --------------------------------------------------------------------------- #
#  Install fakes for libraries that are absent in a headless sandbox.          #
#  (They are only installed if the real library can't be imported, so this     #
#  file is harmless on a full Windows install too.)                            #
# --------------------------------------------------------------------------- #
def _install_fake(name, module):
    try:
        __import__(name)
    except Exception:
        sys.modules[name] = module


# ---- fake sounddevice ----
_sd = types.ModuleType("sounddevice")


class _FakeStream:
    def __init__(self, **kw):
        self.kw = kw
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        pass


def _query_devices(device=None, kind=None):
    dev = {"name": "Fake Mic", "max_input_channels": 2, "default_samplerate": 48000.0}
    if kind == "input" or device is not None:
        return dev
    return [dev]


_sd.InputStream = lambda **kw: _FakeStream(**kw)
_sd.query_devices = _query_devices
_install_fake("sounddevice", _sd)


# ---- fake keyboard ----
_kb = types.ModuleType("keyboard")
_kb._sent, _kb._written, _kb._hook = [], [], None
_kb.send = lambda combo: _kb._sent.append(combo)
_kb.write = lambda text, delay=0: _kb._written.append(text)


def _kb_hook(cb):
    _kb._hook = cb
    return cb


_kb.hook = _kb_hook
_kb.unhook = lambda h: setattr(_kb, "_hook", None)
_install_fake("keyboard", _kb)


# ---- fake pyperclip ----
_pc = types.ModuleType("pyperclip")
_pc._clip = ""
_pc.copy = lambda t: setattr(_pc, "_clip", t)
_pc.paste = lambda: _pc._clip
_install_fake("pyperclip", _pc)


# ---- fake winsound ----
_ws = types.ModuleType("winsound")
_ws.Beep = lambda f, d: None
_install_fake("winsound", _ws)


# ---- fake faster_whisper ----
_fw = types.ModuleType("faster_whisper")


class _Seg:
    def __init__(self, text):
        self.text = text


class _FakeWhisper:
    RESULT = "hello world"

    def __init__(self, *a, **kw):
        self.a, self.kw = a, kw

    def transcribe(self, samples, **kw):
        return ([_Seg(" " + _FakeWhisper.RESULT)], object())


_fw.WhisperModel = _FakeWhisper
_install_fake("faster_whisper", _fw)


# ---- fake tkinter (only if the real one is unavailable) ----
try:
    import tkinter  # noqa: F401
except Exception:
    _tk = types.ModuleType("tkinter")
    for _n in ("Tk", "Toplevel", "Canvas", "Text", "StringVar",
               "BooleanVar", "IntVar"):
        setattr(_tk, _n, mock.MagicMock(name=_n))
    sys.modules["tkinter"] = _tk


import os  # noqa: E402

from flowspeak import audio, hotkey, paste, transcribe  # noqa: E402
from flowspeak import config as cfg  # noqa: E402


def _isolate_appdata():
    """Point all FlowSpeak user-data at a throwaway dir for the test run."""
    tmp = tempfile.mkdtemp(prefix="flowspeak-test-")
    os.environ["XDG_DATA_HOME"] = tmp
    os.environ["APPDATA"] = tmp
    return tmp


class TestRecorder(unittest.TestCase):
    def test_capture_resamples_to_16k(self):
        levels = []
        rec = audio.Recorder(None, on_level=levels.append)
        self.assertTrue(rec.start())                 # fake stream opens
        self.assertEqual(rec.samplerate, 48000)      # from fake query_devices
        # Feed 1 second of audio at the device's native 48 kHz.
        rec._callback(np.full((48000, 1), 0.1, np.float32), 48000, None, None)
        out = rec.stop()
        self.assertEqual(out.dtype, np.float32)
        self.assertEqual(out.size, 16000)            # resampled 48k -> 16k
        self.assertTrue(levels and levels[0] > 0)    # RMS level reported

    def test_list_input_devices(self):
        devs = audio.list_input_devices()
        self.assertEqual(devs, [(0, "Fake Mic")])


class TestPaste(unittest.TestCase):
    def test_paste_mode_sends_ctrl_v(self):
        _kb._sent.clear()
        _pc._clip = ""                               # empty -> no restore thread
        s = cfg.Settings(paste_mode="paste")
        self.assertTrue(paste.paste_text("Hello world", s))
        self.assertEqual(_pc._clip, "Hello world")
        self.assertIn("ctrl+v", _kb._sent)

    def test_type_mode_writes_characters(self):
        _kb._written.clear()
        s = cfg.Settings(paste_mode="type")
        self.assertTrue(paste.paste_text("typed text", s))
        self.assertIn("typed text", _kb._written)

    def test_empty_text_is_noop(self):
        self.assertFalse(paste.paste_text("", cfg.Settings()))


class TestHotkeyEdges(unittest.TestCase):
    def _event(self, etype, name):
        return types.SimpleNamespace(event_type=etype, name=name)

    def test_edges_and_autorepeat(self):
        downs, ups, cancels = [], [], []
        hk = hotkey.HotkeyListener(cfg.Settings(hotkey="right ctrl"),
                                   lambda ts: downs.append(ts),
                                   lambda ts: ups.append(ts),
                                   lambda: cancels.append(True))
        self.assertTrue(hk.start())
        cb = _kb._hook
        cb(self._event("down", "right ctrl"))        # real press
        cb(self._event("down", "right ctrl"))        # auto-repeat -> swallowed
        cb(self._event("up", "right ctrl"))          # release
        cb(self._event("down", "esc"))               # cancel
        cb(self._event("down", "a"))                 # unrelated key -> ignored
        self.assertEqual(len(downs), 1)
        self.assertEqual(len(ups), 1)
        self.assertEqual(len(cancels), 1)
        hk.stop()

    def test_ctrl_c_does_not_trigger_right_ctrl(self):
        downs = []
        hk = hotkey.HotkeyListener(cfg.Settings(hotkey="right ctrl"),
                                   lambda ts: downs.append(ts),
                                   lambda ts: None)
        hk.start()
        _kb._hook(self._event("down", "left ctrl"))  # the Ctrl in Ctrl+C
        self.assertEqual(downs, [])                   # must NOT start recording
        hk.stop()


class TestTranscriber(unittest.TestCase):
    def setUp(self):
        _isolate_appdata()

    def test_local_transcription_via_fake_model(self):
        t = transcribe.Transcriber(cfg.Settings(stt_engine=cfg.STT_LOCAL))
        self.assertTrue(t.warm_up())
        out = t.transcribe(np.full(16000, 0.05, np.float32), 16000)
        self.assertEqual(out, "hello world")

    def test_too_short_audio_returns_empty(self):
        t = transcribe.Transcriber(cfg.Settings())
        self.assertEqual(t.transcribe(np.zeros(10, np.float32), 16000), "")


class _SyncExec:
    """Runs submitted work inline so the pipeline is driven synchronously."""

    def submit(self, fn, *a, **k):
        fn(*a, **k)                                   # _process swallows its own errors

    def shutdown(self, wait=False):
        pass


class TestImportsAndApp(unittest.TestCase):
    def test_every_module_imports(self):
        import importlib
        for name in ("app", "audio", "cleanup", "config", "hotkey", "logs",
                     "overlay", "paste", "paths", "settings_window", "startup",
                     "statemachine", "stats", "transcribe", "tray", "__main__"):
            importlib.import_module(f"flowspeak.{name}")

    def test_full_dictation_pipeline(self):
        _isolate_appdata()
        _kb._sent.clear()
        _pc._clip = ""
        from flowspeak.app import FlowSpeakApp
        app = FlowSpeakApp()
        app._worker = _SyncExec()                     # run transcribe/paste inline
        try:
            app._on_down(0)                           # press hotkey -> START
            self.assertIsNotNone(app.recorder)
            # simulate ~1s of speech at the fake mic's 48 kHz
            app.recorder._callback(np.full((48000, 1), 0.1, np.float32),
                                   48000, None, None)
            app._on_up(300)                           # release after 300ms -> STOP
            # The cleaned transcript was "pasted" and counted.
            self.assertEqual(_pc._clip, "Hello world")
            self.assertIn("ctrl+v", _kb._sent)
            self.assertEqual(app.stats.total_words, 2)
            self.assertEqual(app.stats.history(1)[0]["text"], "Hello world")
        finally:
            app._teardown()


if __name__ == "__main__":
    unittest.main()



