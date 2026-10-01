"""Optional "launch when I sign in" support (Windows).

Implemented with an HKCU \\...\\Run registry value pointing at the project's
run.bat (which sets its own working directory and launches the no-console
pythonw). Everything is best-effort: failures are logged, never raised, so the
app runs fine even on a locked-down machine.
"""
from __future__ import annotations

from pathlib import Path

from . import __app_name__
from .logs import get_logger

log = get_logger()

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _launch_command() -> str:
    root = _project_root()
    run_bat = root / "run.bat"
    if run_bat.exists():
        return f'"{run_bat}"'
    # Fallback: the current (pythonw) interpreter running the package.
    import sys
    exe = sys.executable or "pythonw.exe"
    return f'"{exe}" -m flowspeak'


def is_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, __app_name__)
        return True
    except FileNotFoundError:
        return False
    except Exception as exc:  # noqa: BLE001
        log.debug("autostart query: %s", exc)
        return False


def set_enabled(enabled: bool) -> bool:
    """Add or remove the autostart entry. Returns True on success."""
    try:
        import winreg
        if enabled:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
                winreg.SetValueEx(key, __app_name__, 0, winreg.REG_SZ, _launch_command())
            log.info("Autostart enabled.")
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                                    winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, __app_name__)
                log.info("Autostart disabled.")
            except FileNotFoundError:
                pass
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not change autostart: %s", exc)
        return False
