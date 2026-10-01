"""Application orchestrator — wires every piece together.

Threads in play:
  * main thread      — Tk main loop (owns the hidden root, overlay, settings UI)
  * keyboard thread  — the global hotkey hook calls _on_down/_on_up/_on_cancel
  * pystray thread   — tray menu callbacks
  * worker (1)       — model warm-up + the transcribe→clean→paste pipeline

The push-to-talk state machine is the single source of truth; every input funnels
through it under a lock, and it emits actions the app carries out. Slow work
(transcription) is pushed to the worker so the keyboard hook never blocks.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import __app_name__
from . import cleanup as cleanup_mod
from . import config as cfg
from .logs import get_logger
from .paths import models_dir
from .statemachine import (CANCEL, CAP, DISCARD, LOCK, START, STOP, PushToTalk)
from .stats import StatsStore

log = get_logger()


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _play_sound(kind: str) -> None:
    """Subtle, non-blocking audio cue (Windows only; silent elsewhere)."""
    def go():
        try:
            import winsound
            freq = {"start": 880, "stop": 600, "error": 380}.get(kind, 700)
            dur = 150 if kind == "error" else 70
            winsound.Beep(freq, dur)
        except Exception:  # noqa: BLE001
            pass
    threading.Thread(target=go, daemon=True).start()


class FlowSpeakApp:
    def __init__(self):
        self.settings = cfg.Settings.load()
        self.stats = StatsStore.load()
        self._lock = threading.Lock()
        self._paused = False
        self._suppress = False          # ignore our own synthetic paste keys
        self._record_start = 0.0
        self._running = False
        self._worker = ThreadPoolExecutor(max_workers=1,
                                          thread_name_prefix="flowspeak")

        import tkinter as tk
        self.tk = tk
        self.root = tk.Tk()
        self.root.withdraw()
        try:
            from .paths import asset_path
            ico = asset_path("flowspeak.ico")
            if ico and ico.exists():
                self.root.iconbitmap(str(ico))
        except Exception:  # noqa: BLE001
            pass

        from .overlay import Overlay
        self.overlay = Overlay(self.root)

        from .transcribe import Transcriber
        self.transcriber = Transcriber(self.settings)
        self.recorder = None

        self.sm = PushToTalk(self.settings.min_hold_ms,
                             self.settings.double_tap_lock,
                             self.settings.session_cap_minutes)

        from .hotkey import HotkeyListener
        self.hotkey = HotkeyListener(self.settings, self._on_down,
                                     self._on_up, self._on_cancel)

        from .tray import Tray
        self.tray = Tray(self._open_settings, self._open_history,
                         self._toggle_pause, self._quit,
                         is_paused=lambda: self._paused)

        self.settings_win = None

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        log.info("%s starting…", __app_name__)
        self._worker.submit(self._warm_up)

        if not self.hotkey.start():
            self._notify("Couldn't capture the global hotkey. Try running "
                         "FlowSpeak as administrator.", "Hotkey unavailable")
        self.tray.start()
        self._running = True
        self._schedule_tick()
        try:
            self.root.mainloop()
        finally:
            self._teardown()

    def _warm_up(self) -> None:
        first_run = True
        try:
            md = models_dir()
            first_run = not any(md.iterdir()) if md.exists() else True
        except Exception:  # noqa: BLE001
            pass
        if self.settings.stt_engine == cfg.STT_LOCAL and first_run:
            self._notify(f"Downloading the {self.settings.whisper_model} speech "
                         "model (~150 MB) — one time only…", "Preparing FlowSpeak")
        ok = self.transcriber.warm_up() if self.settings.stt_engine == cfg.STT_LOCAL else True
        if ok and first_run and self.settings.stt_engine == cfg.STT_LOCAL:
            self._notify("Speech model ready. Hold your hotkey and talk!", __app_name__)

    def _schedule_tick(self) -> None:
        if self._running:
            try:
                self.root.after(500, self._tick)
            except Exception:  # noqa: BLE001
                pass

    def _tick(self) -> None:
        with self._lock:
            actions = self.sm.tick(_now_ms())
            if actions:
                self._dispatch(actions)
        self._schedule_tick()

    def _teardown(self) -> None:
        self._running = False
        try:
            self.hotkey.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.tray.stop()
        except Exception:  # noqa: BLE001
            pass
        self._worker.shutdown(wait=False)

    # ------------------------------------------------------------------ helpers
    def _device_index(self):
        raw = str(self.settings.input_device).strip()
        return int(raw) if raw.isdigit() else None

    def _notify(self, message: str, title: str | None = None) -> None:
        try:
            self.tray.notify(message, title)
        except Exception:  # noqa: BLE001
            log.info("%s: %s", title or __app_name__, message)

    # ------------------------------------------------------------------ input
    def _on_down(self, ts: int) -> None:
        if self._paused or self._suppress:
            return
        with self._lock:
            self._dispatch(self.sm.key_down(ts))

    def _on_up(self, ts: int) -> None:
        if self._paused or self._suppress:
            return
        with self._lock:
            self._dispatch(self.sm.key_up(ts))

    def _on_cancel(self) -> None:
        with self._lock:
            self._dispatch(self.sm.cancel())

    def _dispatch(self, actions) -> None:
        """Carry out state-machine actions. Called while holding self._lock."""
        for a in actions:
            try:
                if a in (START, LOCK):
                    self._begin()
                elif a in (STOP, CAP):
                    self._end_and_process()
                elif a == DISCARD:
                    self._abort()
                elif a == CANCEL:
                    self._abort(notify_cancel=True)
            except Exception as exc:  # noqa: BLE001
                log.error("action %s failed: %s", a, exc)

    # ------------------------------------------------------------------ record
    def _begin(self) -> None:
        from .audio import Recorder
        self.recorder = Recorder(self._device_index(),
                                 on_level=self.overlay.set_level)
        if self.recorder.start():
            self._record_start = time.time()
            self.overlay.show_recording()
            if self.settings.play_sounds:
                _play_sound("start")
        else:
            self.recorder = None
            self.overlay.show_error()
            self._notify("Couldn't open the microphone. Check it's connected "
                         "and allowed in Windows privacy settings.", "Microphone error")

    def _end_and_process(self) -> None:
        rec, self.recorder = self.recorder, None
        if rec is None:
            self.overlay.hide()
            return
        samples = rec.stop()
        dur_ms = int((time.time() - self._record_start) * 1000)
        self.overlay.show_transcribing()
        if self.settings.play_sounds:
            _play_sound("stop")
        self._worker.submit(self._process, samples, dur_ms)

    def _abort(self, notify_cancel: bool = False) -> None:
        rec, self.recorder = self.recorder, None
        if rec is not None:
            try:
                rec.stop()
            except Exception:  # noqa: BLE001
                pass
        self.overlay.hide()

    # ------------------------------------------------------------------ pipeline
    def _process(self, samples, dur_ms: int) -> None:
        """Worker thread: transcribe → clean → paste → record stats."""
        try:
            text = self.transcriber.transcribe(samples, 16000)
            cleaned = cleanup_mod.clean(text, self.settings)
            if not cleaned:
                self.overlay.show_error()
                return
            from .paste import paste_text
            self._suppress = True
            try:
                paste_text(cleaned, self.settings)
            finally:
                threading.Timer(0.35, self._clear_suppress).start()
            app_name = ""
            self.stats.record(cleaned, dur_ms, app=app_name)
            try:
                self.stats.save()
            except Exception as exc:  # noqa: BLE001
                log.debug("stats save: %s", exc)
            self.overlay.show_done()
            self._refresh_settings_history()
        except Exception as exc:  # noqa: BLE001
            log.error("pipeline failed: %s", exc)
            self.overlay.show_error()

    def _clear_suppress(self) -> None:
        self._suppress = False

    # ------------------------------------------------------------------ tray / UI
    def _open_settings(self) -> None:
        self.root.after(0, self._open_settings_main)

    def _open_history(self) -> None:
        self.root.after(0, self._open_settings_main)

    def _open_settings_main(self) -> None:
        try:
            if self.settings_win is None:
                from .settings_window import SettingsWindow
                self.settings_win = SettingsWindow(
                    self.root, self.settings, self._apply_settings, self.stats)
            self.settings_win.settings = self.settings
            self.settings_win.stats = self.stats
            self.settings_win.show()
        except Exception as exc:  # noqa: BLE001
            log.error("open settings: %s", exc)

    def _refresh_settings_history(self) -> None:
        if self.settings_win is not None:
            try:
                self.root.after(0, self.settings_win._refresh_history)
            except Exception:  # noqa: BLE001
                pass

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            with self._lock:
                self._abort()
        self.tray.refresh()
        self._notify("Dictation paused." if self._paused else "Dictation resumed.")

    def _quit(self) -> None:
        self.root.after(0, self._quit_main)

    def _quit_main(self) -> None:
        log.info("Quitting.")
        self._running = False
        try:
            self.root.quit()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ settings
    def _apply_settings(self, new: "cfg.Settings") -> None:
        old = self.settings
        self.settings = new
        try:
            new.save()
        except Exception as exc:  # noqa: BLE001
            log.error("could not save settings: %s", exc)

        # Point live components at the new settings.
        self.transcriber.settings = new  # model reloads lazily if it changed

        with self._lock:
            self.sm = PushToTalk(new.min_hold_ms, new.double_tap_lock,
                                 new.session_cap_minutes)
        self.hotkey.settings = new
        if new.hotkey != old.hotkey:
            self.hotkey.restart()

        if (new.whisper_model, new.compute_type) != (old.whisper_model, old.compute_type):
            if new.stt_engine == cfg.STT_LOCAL:
                self._worker.submit(self.transcriber.warm_up)

        if new.launch_on_startup != old.launch_on_startup:
            try:
                from . import startup
                startup.set_enabled(new.launch_on_startup)
            except Exception as exc:  # noqa: BLE001
                log.warning("autostart toggle failed: %s", exc)


def main() -> None:
    try:
        FlowSpeakApp().start()
    except Exception as exc:  # noqa: BLE001
        log.exception("Fatal error: %s", exc)
        raise


if __name__ == "__main__":
    main()
