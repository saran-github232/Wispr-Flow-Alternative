"""Tiny logging helper — writes to %APPDATA%\\FlowSpeak\\flowspeak.log and,
in debug mode (FLOWSPEAK_DEBUG=1 or run-debug.bat), also to the console."""
from __future__ import annotations

import logging
import os
import sys

from .paths import log_path

_configured = False


def get_logger(name: str = "flowspeak") -> logging.Logger:
    global _configured
    logger = logging.getLogger("flowspeak")
    if not _configured:
        logger.setLevel(logging.DEBUG)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        try:
            fh = logging.FileHandler(log_path(), encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except Exception:
            pass  # never let logging kill the app
        if os.environ.get("FLOWSPEAK_DEBUG") or sys.stderr:
            sh = logging.StreamHandler()
            sh.setLevel(logging.DEBUG if os.environ.get("FLOWSPEAK_DEBUG") else logging.INFO)
            sh.setFormatter(fmt)
            logger.addHandler(sh)
        _configured = True
    return logger
