"""System-tray icon and menu (pystray + Pillow).

Lives in the notification area and is the app's only persistent, visible
surface. The menu exposes Settings, Dictation history, a pause toggle for the
hotkey, and Quit. pystray runs its own event loop on a daemon thread; menu
callbacks fire on that thread, so the app marshals them onto the Tk loop.

Both libraries are imported lazily so the pure-logic tests don't need them.
"""
from __future__ import annotations

from typing import Callable, Optional

from . import ACCENT, __app_name__, __version__
from .logs import get_logger
from .paths import asset_path

log = get_logger()


def _load_icon_image():
    """The tray image: the bundled teal-ring icon, or a drawn fallback."""
    from PIL import Image, ImageDraw
    png = asset_path("flowspeak.png")
    try:
        if png and png.exists():
            return Image.open(str(png)).convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        log.debug("tray icon load: %s", exc)
    # Fallback: draw the concentric-ring mark.
    size = 64
    img = Image.new("RGBA", (size, size), (14, 16, 19, 255))
    d = ImageDraw.Draw(img)
    teal = tuple(int(ACCENT[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    d.ellipse([8, 8, 56, 56], outline=teal, width=5)
    d.ellipse([24, 24, 40, 40], fill=teal)
    return img


class Tray:
    def __init__(self,
                 on_settings: Callable[[], None],
                 on_history: Callable[[], None],
                 on_toggle_pause: Callable[[], None],
                 on_quit: Callable[[], None],
                 is_paused: Optional[Callable[[], bool]] = None):
        self.on_settings = on_settings
        self.on_history = on_history
        self.on_toggle_pause = on_toggle_pause
        self.on_quit = on_quit
        self.is_paused = is_paused or (lambda: False)
        self._icon = None

    def _build_menu(self):
        import pystray
        return pystray.Menu(
            pystray.MenuItem("Settings", lambda *_: self.on_settings(), default=True),
            pystray.MenuItem("Dictation history", lambda *_: self.on_history()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Pause dictation", lambda *_: self.on_toggle_pause(),
                             checked=lambda _item: self.is_paused()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"{__app_name__} v{__version__}", None, enabled=False),
            pystray.MenuItem("Quit", lambda *_: self.on_quit()),
        )

    def start(self) -> bool:
        """Create the icon and run its loop on a daemon thread."""
        try:
            import pystray
        except Exception as exc:  # noqa: BLE001
            log.error("pystray unavailable: %s", exc)
            return False
        try:
            self._icon = pystray.Icon(
                __app_name__, _load_icon_image(), __app_name__, self._build_menu())
            self._icon.run_detached()
            log.info("Tray icon started.")
            return True
        except Exception as exc:  # noqa: BLE001
            log.error("Could not start tray icon: %s", exc)
            # run_detached isn't supported on every backend; try a thread.
            try:
                import threading
                threading.Thread(target=self._icon.run, daemon=True).start()
                return True
            except Exception as exc2:  # noqa: BLE001
                log.error("Tray thread fallback failed: %s", exc2)
                return False

    def refresh(self) -> None:
        if self._icon is not None:
            try:
                self._icon.update_menu()
            except Exception as exc:  # noqa: BLE001
                log.debug("tray refresh: %s", exc)

    def notify(self, message: str, title: Optional[str] = None) -> None:
        if self._icon is not None:
            try:
                self._icon.notify(message, title or __app_name__)
            except Exception as exc:  # noqa: BLE001
                log.debug("tray notify: %s", exc)

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as exc:  # noqa: BLE001
                log.debug("tray stop: %s", exc)
            self._icon = None
