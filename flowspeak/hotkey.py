"""Global push-to-talk hotkey listener (via the `keyboard` library).

Watches the single configured key (default "right ctrl") everywhere in the OS
and reports clean press / release *edges* — auto-repeat "down" events that fire
while a key is held are swallowed here so the state machine only ever sees real
transitions. Esc is also watched, to cancel an in-progress take.

Matching is done on the event *name* ("right ctrl"), not the raw scan code:
on Windows left and right Ctrl share scan code 29, so a scan-code match would
make ordinary Ctrl+C start a recording. The library distinguishes the physical
key by name, which is exactly what we want. A generic modifier like "ctrl"
matches either side.

Callbacks fire on the keyboard library's own listener thread, so the app layer
is responsible for marshalling them somewhere safe (e.g. a queue or Tk.after).

`keyboard` is imported lazily and needs administrator rights on some systems;
start() returns False (and logs) instead of raising if it can't hook.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from . import config as cfg
from .logs import get_logger

log = get_logger()


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def name_variants(name: str) -> set[str]:
    """Accepted event names for a configured key. A generic modifier accepts
    both its left and right physical variants."""
    name = (name or "").strip().lower()
    out = {name}
    if name in ("ctrl", "control"):
        out |= {"ctrl", "left ctrl", "right ctrl"}
    elif name == "shift":
        out |= {"left shift", "right shift"}
    elif name == "alt":
        out |= {"left alt", "right alt", "alt gr"}
    elif name in ("win", "cmd", "super", "windows"):
        out |= {"left windows", "right windows"}
    return out


class HotkeyListener:
    """Feed-forward edges from the OS keyboard into the push-to-talk layer."""

    def __init__(self, settings: "cfg.Settings",
                 on_down: Callable[[int], None],
                 on_up: Callable[[int], None],
                 on_cancel: Optional[Callable[[], None]] = None):
        self.settings = settings
        self.on_down = on_down
        self.on_up = on_up
        self.on_cancel = on_cancel
        self._hook = None
        self._pressed = False
        self._names: set[str] = set()

    # ------------------------------------------------------------------ control
    def start(self) -> bool:
        try:
            import keyboard
        except Exception as exc:  # noqa: BLE001
            log.error("keyboard library unavailable: %s", exc)
            return False
        self._names = name_variants(self.settings.hotkey)
        try:
            self._pressed = False
            self._hook = keyboard.hook(self._on_event)
            log.info("Hotkey listener active on %r (names=%s).",
                     self.settings.hotkey, sorted(self._names))
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("Could not install keyboard hook: %s", exc)
            self._hook = None
            return False

    def stop(self) -> None:
        if self._hook is not None:
            try:
                import keyboard
                keyboard.unhook(self._hook)
            except Exception as exc:  # noqa: BLE001
                log.debug("unhook: %s", exc)
        self._hook = None
        self._pressed = False

    def restart(self) -> bool:
        """Re-read the hotkey from settings (after the user changes it)."""
        self.stop()
        return self.start()

    # ------------------------------------------------------------------ events
    def _matches(self, event) -> bool:
        name = (getattr(event, "name", None) or "").strip().lower()
        return bool(name) and name in self._names

    def _on_event(self, event) -> None:
        try:
            etype = getattr(event, "event_type", None)
            name = (getattr(event, "name", None) or "").strip().lower()
            if self._matches(event):
                if etype == "down":
                    if not self._pressed:          # ignore held-key auto-repeat
                        self._pressed = True
                        self.on_down(_now_ms())
                elif etype == "up":
                    if self._pressed:
                        self._pressed = False
                        self.on_up(_now_ms())
            elif etype == "down" and name == "esc" and self.on_cancel:
                self.on_cancel()
        except Exception as exc:  # noqa: BLE001
            log.debug("hotkey event error: %s", exc)
