"""The floating pill overlay (Tkinter).

A borderless, always-on-top, transparent-background capsule that sits at the
bottom-center of the screen — mirroring the reference artwork: a near-black
pill with a centered row of teal dots. The dots come alive into a reactive
dotted waveform while recording, show a travelling shimmer while transcribing,
and briefly confirm (teal) or warn (amber) before fading away.

All public methods are thread-safe: workers call them from any thread and they
marshal onto the Tk main loop via ``after``. Tkinter is imported defensively so
the module still imports on headless machines (e.g. CI).
"""
from __future__ import annotations

import math
from typing import Optional

from . import ACCENT
from .logs import get_logger

try:
    import tkinter as tk
except Exception:  # noqa: BLE001 - headless / no Tk
    tk = None

log = get_logger()

# States
IDLE = "idle"
RECORDING = "recording"
TRANSCRIBING = "transcribing"
DONE = "done"
ERROR = "error"

# Look
_PILL_BG = "#0E1013"       # near-black capsule
_TRANSPARENT = "#FF00FF"   # color key punched out to transparent on Windows
_DOT = "#8A94A6"           # resting dot (muted slate)
_ACCENT = ACCENT           # teal while active
_AMBER = "#F2B23E"         # error
_N_BARS = 9
_W, _H = 184, 58           # canvas size
_PAD = 10                  # rounded-corner radius padding feel


class Overlay:
    """Owns a Tk Toplevel pill. Must be created on the thread running the Tk
    main loop (the app creates the hidden root and passes it in)."""

    def __init__(self, root: "tk.Tk"):
        self.root = root
        self.state = IDLE
        self._level = 0.0          # smoothed mic RMS, 0..~1
        self._target = 0.0         # latest raw level target
        self._phase = 0.0          # animation phase
        self._visible = False
        self._anim_job = None
        self._hide_job = None

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.wm_attributes("-topmost", True)
        try:
            self.win.wm_attributes("-transparentcolor", _TRANSPARENT)
        except Exception:  # noqa: BLE001 - non-Windows: no color-key transparency
            pass
        self.canvas = tk.Canvas(self.win, width=_W, height=_H,
                                bg=_TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack()
        self._place_bottom_center()
        self._draw()

    # ------------------------------------------------------------------ layout
    def _place_bottom_center(self) -> None:
        try:
            sw = self.win.winfo_screenwidth()
            sh = self.win.winfo_screenheight()
            x = (sw - _W) // 2
            y = sh - _H - 90          # a comfortable gap above the taskbar
            self.win.geometry(f"{_W}x{_H}+{x}+{y}")
        except Exception as exc:  # noqa: BLE001
            log.debug("overlay place: %s", exc)

    @staticmethod
    def _round_rect(cv, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(pts, smooth=True, **kw)

    # ------------------------------------------------------------------ drawing
    def _bar_color(self) -> str:
        if self.state == ERROR:
            return _AMBER
        if self.state in (RECORDING, TRANSCRIBING, DONE):
            return _ACCENT
        return _DOT

    def _amplitude(self, i: int) -> float:
        """0..1 height factor for bar i given the current state/phase/level."""
        n = _N_BARS
        if self.state == RECORDING:
            # Lively waveform: per-bar sine, scaled by smoothed mic level.
            lvl = min(1.0, self._level * 7.0)
            wobble = 0.5 + 0.5 * math.sin(self._phase * 2.2 + i * 0.9)
            edge = 1.0 - abs((i - (n - 1) / 2) / ((n - 1) / 2)) * 0.35
            return max(0.12, min(1.0, (0.25 + 0.9 * lvl * wobble) * edge))
        if self.state == TRANSCRIBING:
            # A gaussian "pulse" travelling left→right through the dots.
            center = (self._phase * 2.0) % (n + 2) - 1
            g = math.exp(-((i - center) ** 2) / 1.3)
            return max(0.12, min(1.0, 0.16 + 0.95 * g))
        if self.state == DONE:
            return 0.6
        if self.state == ERROR:
            return 0.5
        return 0.12  # idle dots

    def _draw(self) -> None:
        cv = self.canvas
        cv.delete("all")
        # transparent backdrop + the pill body
        cv.create_rectangle(0, 0, _W, _H, fill=_TRANSPARENT, outline=_TRANSPARENT)
        self._round_rect(cv, 2, 2, _W - 2, _H - 2, _H // 2 - 2,
                         fill=_PILL_BG, outline=_PILL_BG)
        color = self._bar_color()
        n = _N_BARS
        gap = 15
        bar_w = 5
        total = (n - 1) * gap
        x0 = (_W - total) / 2
        cy = _H / 2
        max_h = _H * 0.46
        for i in range(n):
            amp = self._amplitude(i)
            h = max(bar_w, amp * max_h)
            x = x0 + i * gap
            self._round_rect(cv, x - bar_w / 2, cy - h / 2,
                             x + bar_w / 2, cy + h / 2, bar_w / 2,
                             fill=color, outline=color)

    # ------------------------------------------------------------------ anim
    def _animate(self) -> None:
        # ease the smoothed level toward the latest target
        self._level += (self._target - self._level) * 0.35
        self._phase += 0.18
        self._draw()
        if self.state in (RECORDING, TRANSCRIBING):
            self._anim_job = self.root.after(33, self._animate)
        else:
            self._anim_job = None

    def _ensure_anim(self) -> None:
        if self._anim_job is None:
            self._anim_job = self.root.after(0, self._animate)

    def _show(self) -> None:
        if not self._visible:
            self.win.deiconify()
            self.win.wm_attributes("-topmost", True)
            self._visible = True

    def _cancel_hide(self) -> None:
        if self._hide_job is not None:
            try:
                self.root.after_cancel(self._hide_job)
            except Exception:  # noqa: BLE001
                pass
            self._hide_job = None

    # ------------------------------------------------------------------ public
    # Each of these may be called from any thread.
    def set_state(self, state: str) -> None:
        self.root.after(0, self._set_state, state)

    def _set_state(self, state: str) -> None:
        self.state = state
        self._cancel_hide()
        if state in (RECORDING, TRANSCRIBING):
            self._show()
            self._ensure_anim()
        elif state in (DONE, ERROR):
            self._show()
            self._draw()
            self._hide_job = self.root.after(750, self._do_hide)
        elif state == IDLE:
            self._show()
            self._draw()
        self._draw()

    def set_level(self, rms: float) -> None:
        # cheap; store the target for the eased animation. No marshalling needed
        # for a float assignment, but keep it on the loop to be safe.
        try:
            self._target = float(rms)
        except Exception:  # noqa: BLE001
            pass

    def show_recording(self) -> None:
        self._target = 0.0
        self.set_state(RECORDING)

    def show_transcribing(self) -> None:
        self.set_state(TRANSCRIBING)

    def show_done(self) -> None:
        self.set_state(DONE)

    def show_error(self) -> None:
        self.set_state(ERROR)

    def hide(self) -> None:
        self.root.after(0, self._do_hide)

    def _do_hide(self) -> None:
        self._cancel_hide()
        if self._anim_job is not None:
            try:
                self.root.after_cancel(self._anim_job)
            except Exception:  # noqa: BLE001
                pass
            self._anim_job = None
        self.state = IDLE
        self._level = self._target = 0.0
        if self._visible:
            self.win.withdraw()
            self._visible = False
