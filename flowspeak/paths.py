"""Filesystem paths and small shared helpers.

All user data lives under %APPDATA%\\FlowSpeak on Windows (and the XDG/home
equivalent elsewhere, so the pure-logic tests run on Linux CI too).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def app_data_dir() -> Path:
    """Return the per-user data directory, creating it if needed."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    d = Path(base) / "FlowSpeak"
    d.mkdir(parents=True, exist_ok=True)
    return d


def models_dir() -> Path:
    d = app_data_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return app_data_dir() / "config.json"


def stats_path() -> Path:
    return app_data_dir() / "stats.json"


def log_path() -> Path:
    return app_data_dir() / "flowspeak.log"


def asset_path(name: str) -> Path:
    """Path to a bundled asset (icons), robust to PyInstaller freezing."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "flowspeak" / "assets" / name
    return Path(__file__).resolve().parent / "assets" / name
