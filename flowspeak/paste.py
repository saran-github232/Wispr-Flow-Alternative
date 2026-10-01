"""Insert transcribed text into whatever window currently has focus.

Default mode "paste" copies the text to the clipboard and sends Ctrl+V, then
restores the previous clipboard contents a moment later (so the user's copy
buffer isn't clobbered). Mode "type" sends the characters one-by-one, which is
slower but works in the rare app that blocks programmatic paste.

Everything here is lazy-imported and wrapped so a failure degrades gracefully:
at worst the text is left on the clipboard for the user to paste manually.
"""
from __future__ import annotations

import threading
import time

from . import config as cfg
from .logs import get_logger

log = get_logger()


def _copy_to_clipboard(text: str) -> None:
    import pyperclip
    pyperclip.copy(text)


def _read_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception:  # noqa: BLE001
        return ""


def _send_paste_hotkey() -> None:
    import keyboard
    keyboard.send("ctrl+v")


def _type_text(text: str) -> None:
    import keyboard
    # delay spreads keystrokes out so fast apps don't drop characters.
    keyboard.write(text, delay=0.004)


def paste_text(text: str, settings: "cfg.Settings") -> bool:
    """Insert `text` at the cursor. Returns True if the insert was issued.

    Never raises; on any failure the text is at least left on the clipboard.
    """
    if not text:
        return False

    if settings.paste_mode == "type":
        try:
            _type_text(text)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Type mode failed (%s); falling back to clipboard.", exc)

    # Clipboard + Ctrl+V, preserving the user's existing clipboard.
    previous = _read_clipboard()
    try:
        _copy_to_clipboard(text)
    except Exception as exc:  # noqa: BLE001
        log.error("Could not write to clipboard: %s", exc)
        return False

    try:
        # Tiny settle time so the target app sees the new clipboard contents.
        time.sleep(0.02)
        _send_paste_hotkey()
    except Exception as exc:  # noqa: BLE001
        log.warning("Auto-paste failed (%s); text left on clipboard.", exc)
        return False

    # Restore the old clipboard shortly after, off the hot path.
    if previous:
        def _restore():
            time.sleep(0.4)
            try:
                _copy_to_clipboard(previous)
            except Exception:  # noqa: BLE001
                pass
        threading.Thread(target=_restore, daemon=True).start()
    return True
